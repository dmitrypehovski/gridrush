#!/usr/bin/env python3
"""GRIDRUSH simulator run -- writes results/sim_baseline.json (CONTRACT.md §5).

    python3 sim/run.py

Runs the 3 honest baselines over 4 real BA regions (CAL=CAISO, TEX=ERCOT,
PJM=PJM, MISO=MISO), picks the demo region (CAL: strongest history, highest
evening-peak stress), and emits the frozen JSON schema consumed by the dashboard
and the loop.

The `best` block is a stub with the correct schema. If results/loop.json already
exists (written by loop/run.py, the Lead's file), its winning portfolio is scored
through this same evaluate() and embedded, so the two JSONs cannot disagree. The
loop owns `iterations`/`best` in its own file; sim_baseline.json mirrors it.

No network, no prints except the final one-line summary.
"""
import json
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sim.baselines import BASELINE_LABELS, BASELINES  # noqa: E402
from sim.curves import site_curves  # noqa: E402
from sim.data import load_region, make_sites  # noqa: E402
from sim.engine import (HORIZON_MONTHS, MIN_MW, MODES,  # noqa: E402
                        SLA_BUDGET_HOURS, SLA_LEVELS, evaluate)

REGION_ORDER = ["CAL", "TEX", "PJM", "MISO"]
PRIMARY_REGION = "CAL"      # strongest story: real evening peak 2025-08-21 20:00
ASSUMPTIONS_VERSION = 1
RESULTS_DIR = os.path.join(_ROOT, "results")
OUT_PATH = os.path.join(RESULTS_DIR, "sim_baseline.json")
LOOP_PATH = os.path.join(RESULTS_DIR, "loop.json")


# ---------------------------------------------------------------------------
# reference policy (fallback when loop.json is absent)
# ---------------------------------------------------------------------------
def _compliant_row(res):
    """Compliant MW-months: only sites whose availability meets their SLA."""
    delivered = 0.0
    mw12 = 0.0
    for sid, avail in res.get("avail_by_site", {}).items():
        sla = res.get("sla_by_site", {}).get(sid, 0.999)
        if avail + 1e-9 < sla:
            continue
        mw = res.get("mw_by_site", {}).get(sid, 0.0)
        months = max(0, HORIZON_MONTHS - res["energize_month_by_site"][sid])
        delivered += mw * months * avail
        if res["energize_month_by_site"][sid] < 12:
            mw12 += mw
    return delivered, mw12


def reference_policy(region):
    """Greedy per-substation compliant policy used only if loop.json is missing.

    Substations are independent in the frozen model, so this decomposition is
    exact; candidates are sized on the site's headroom curve, modes flex/battery,
    three SLA levels, and only SLA-compliant sites are kept.
    """
    c = site_curves(region)
    sites = make_sites(region)
    by_sub = {}
    for i, s in enumerate(sites):
        by_sub.setdefault(s["substation"], []).append(i)
    portfolio = []
    for sub in sorted(by_sub):
        chosen = {}
        for i in by_sub[sub]:
            capmw = float(min(c["max_mw"][i], max(0.0, c["Hmax_mw"][i])))
            best = (None, None)
            base = [v for v in chosen.values() if v["mode"] != "skip"]
            res0 = evaluate(region, base)
            best = (res0["score"], {"site_id": c["ids"][i], "mode": "skip",
                                    "mw": 0.0, "sla": 0.999, "battery_mwh": 0.0})
            if capmw >= MIN_MW:
                grid = sorted({round(min(capmw, 0.5 * k), 2)
                               for k in range(1, 21) if 0.5 * k <= capmw})
                for mw in grid:
                    for mode, bh in (("flex", 0.0), ("battery", 2.0),
                                     ("battery", 4.0), ("battery", 6.0)):
                        for sla in SLA_LEVELS:
                            cand = {"site_id": c["ids"][i], "mode": mode,
                                    "mw": mw, "sla": sla,
                                    "battery_mwh": bh * mw if mode == "battery" else 0.0}
                            r = evaluate(region, base + [cand])
                            ok = (r["violations_mwh"] == 0.0
                                  and r["sla_breach_mwh"] == 0.0)
                            key = r["net_value_musd"] if ok else -1e9
                            if key > best[0]:
                                best = (key, cand)
            chosen[i] = best[1]
        portfolio += [v for v in chosen.values() if v["mode"] != "skip"]
    return portfolio


def _hourly_curtail_mw(region, portfolio):
    """Per-hour curtailed MW of a portfolio (stress-day chart only).

    Mirrors the documented allocation rule of engine.evaluate: firm gets its MW
    first, flex/battery sites are served in (energize month, site id) order, and a
    site only gets what is left of cap - e - margin. Validated against
    evaluate()'s annual curtail_mwh_by_site in main().
    """
    c = site_curves(region)
    idx = {sid: i for i, sid in enumerate(c["ids"])}
    n, S, H = c["n_sites"], c["n_substations"], c["n_hours"]
    mw = np.zeros(n)
    mode = ["skip"] * n
    T = np.zeros(n, dtype=np.int64)
    for item in portfolio or []:
        i = idx.get(str(item.get("site_id", "")))
        if i is None:
            continue
        m = str(item.get("mode", "skip")).lower()
        if m not in MODES or m == "skip":
            continue
        mw_i = float(item.get("mw", 0.0) or 0.0)
        mw_i = min(mw_i, c["max_mw"][i], max(0.0, c["Hmax_mw"][i]))
        if mw_i < MIN_MW:
            continue
        mw[i], mode[i] = mw_i, m
        T[i] = {"firm": c["T_firm"][i], "flex": c["T_flex"][i],
                "battery": c["T_on"][i]}[m]
    active = np.array([m != "skip" for m in mode])
    firm = np.zeros(S)
    for i in np.flatnonzero(active):
        if mode[i] == "firm":
            firm[c["sub_idx"][i]] += mw[i]
    left = c["H_sub"] - firm[:, None]
    load = np.zeros((n, H))
    for i in sorted((i for i in np.flatnonzero(active) if mode[i] != "firm"),
                    key=lambda i: (int(T[i]), c["ids"][i])):
        s = c["sub_idx"][i]
        load[i] = np.minimum(mw[i], np.maximum(0.0, left[s]))
        left[s] -= load[i]
    for i in np.flatnonzero(active):
        if mode[i] == "firm":
            load[i] = mw[i]
    curtail = np.clip(mw[:, None] - load, 0.0, None).sum(axis=0)
    return curtail


# ---------------------------------------------------------------------------
# JSON builders
# ---------------------------------------------------------------------------
def _r(x, nd=4):
    return round(float(x), nd)


def build_sites(region):
    c = site_curves(region)
    sites = make_sites(region)
    out = []
    for k, s in enumerate(sites):
        out.append({
            "id": s["id"],
            "substation": s["substation"],
            "cap_mw": s["cap_mw"],
            "lf": s["lf"],
            "max_mw": s["max_mw"],
            "x": s["x"],
            "y": s["y"],
            "T_firm": s["T_firm"],
            "T_flex": s["T_flex"],
            "T_on": s["T_on"],
            "fiber": bool(s["fiber"]),
            "permit_days": s["permit_days"],
            "Hmax_mw": _r(c["Hmax_mw"][k], 2),
            "Hmin_mw": _r(c["Hmin_mw"][k], 2),
            "stress_hours": int(c["stress_hours"][k]),
        })
    return out


def build_grid(region, portfolio):
    reg = load_region(region)
    c = site_curves(region)
    stress_idx = np.asarray(reg["stress_idx"], dtype=int)
    headroom = c["H_sub"].sum(axis=0)          # aggregate free headroom, 8 substations
    curtail = _hourly_curtail_mw(region, portfolio)
    solar_max = float(reg["solar_mw"].max()) or 1.0
    day = {
        "date": reg["stress_day"],
        "local_hours": [int(x) for x in reg["local_time"][stress_idx].astype("datetime64[h]").astype(int) % 24],
        "demand_mw": [_r(reg["demand_mw"][i], 1) for i in stress_idx],
        "solar_mw": [_r(reg["solar_mw"][i], 1) for i in stress_idx],
        "u": [_r(reg["u"][i], 4) for i in stress_idx],
        "headroom_mw": [_r(headroom[i], 2) for i in stress_idx],
        "curtail_mw": [_r(curtail[i], 2) for i in stress_idx],
        "cap_factor": [_r(reg["solar_mw"][i] / solar_max, 4) for i in stress_idx],
    }
    return {
        "region": reg["region"],
        "ba": reg["ba"],
        "peak_mw": _r(reg["peak_mw"], 1),
        "peak_local": reg["peak_local"],
        "p95_mw": _r(reg["p95_mw"], 1),
        "demand_mw": [_r(v, 1) for v in reg["demand_mw"]],
        "solar_mw": [_r(v, 1) for v in reg["solar_mw"]],
        "u": [_r(v, 4) for v in reg["u"]],
        "stress_day": day,
    }


def baseline_block(region):
    """All 3 baselines scored in one region. Returns dict + scored portfolios."""
    c = site_curves(region)
    sites = make_sites(region)
    rows = {}
    portfolios = {}
    for name, fn in BASELINES.items():
        pf = fn(region, sites)
        res = evaluate(region, pf)
        comp_mwmonths, comp_mw12 = _compliant_row(res)
        rows[name] = {
            "label": BASELINE_LABELS[name],
            "n_sites": len(pf),
            "total_mw": _r(sum(p["mw"] for p in pf), 2),
            "delivered_mwmonths": _r(res["delivered_mwmonths"], 2),
            "compliant_mwmonths": _r(comp_mwmonths, 2),
            "mw_at_month12": _r(res["mw_at_month12"], 2),
            "compliant_mw12": _r(comp_mw12, 2),
            "net_value_musd": _r(res["net_value_musd"], 2),
            "rev_weighted_mwmonths": _r(res["rev_weighted_mwmonths"], 2),
            "violations_mwh": _r(res["violations_mwh"], 4),
            "sla_breach_mwh": _r(res["sla_breach_mwh"], 2),
            "capex_musd": _r(res["capex_musd"], 2),
        }
        portfolios[name] = pf
    ref = rows["all_firm_greedy"]["delivered_mwmonths"] or 1.0
    for name in rows:
        rows[name]["ratio"] = _r(rows[name]["delivered_mwmonths"] / ref, 3)
    return rows, portfolios


def best_block(region, portfolio, source):
    res = evaluate(region, portfolio)
    sites = make_sites(region)
    meta_by_id = {s["id"]: s for s in sites}
    rows = []
    for sid, m in res["modes"].items():
        if m == "skip":
            continue
        s = meta_by_id[sid]
        rows.append({
            "id": sid,
            "substation": s["substation"],
            "mode": m,
            "mw": _r(res["mw_by_site"][sid], 2),
            "sla": res["sla_by_site"][sid],
            "battery_mwh": _r(res["battery_mwh_by_site"].get(sid, 0.0), 2),
            "energize_month": int(res["energize_month_by_site"][sid]),
            "curtail_hours": _r(res["curtail_hours_by_site"][sid], 2),
            "avail": _r(res["avail_by_site"][sid], 6),
        })
    rows.sort(key=lambda r: (r["energize_month"], r["id"]))
    comp_mwmonths, comp_mw12 = _compliant_row(res)
    capex = res["capex_musd"]
    net = (res["net_value_musd"])
    return {
        "label": "GRIDRUSH agent",
        "source": source,
        "params": {"policy": source, "horizon_months": HORIZON_MONTHS,
                   "region": region},
        "delivered_mwmonths": _r(res["delivered_mwmonths"], 2),
        "compliant_mwmonths": _r(comp_mwmonths, 2),
        "mw_at_month12": _r(res["mw_at_month12"], 2),
        "compliant_mw12": _r(comp_mw12, 2),
        "net_value_musd": _r(net, 2),
        "rev_weighted_mwmonths": _r(res["rev_weighted_mwmonths"], 2),
        "violations_mwh": _r(res["violations_mwh"], 4),
        "sla_breach_mwh": _r(res["sla_breach_mwh"], 2),
        "capex_musd": _r(capex, 2),
        "n_sites": len(rows),
        "total_mw": _r(sum(r["mw"] for r in rows), 2),
        "monthly_mw": [_r(v, 2) for v in res["monthly_mw"]],
        "sites": rows,
        "score": _r(res["score"], 4),
    }


def load_loop_best():
    """Portfolio from the Lead's loop.json (read-only) if it is already there."""
    if not os.path.exists(LOOP_PATH):
        return None, None
    try:
        with open(LOOP_PATH) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None, None
    best = data.get("best") or {}
    sites = best.get("sites") or []
    pf = []
    for s in sites:
        mode = str(s.get("mode", "skip"))
        if mode not in MODES or mode == "skip":
            continue
        pf.append({"site_id": s.get("id") or s.get("site_id"),
                   "mode": mode,
                   "mw": float(s.get("mw", 0.0) or 0.0),
                   "sla": float(s.get("sla", 0.999) or 0.999),
                   "battery_mwh": float(s.get("battery_mwh", 0.0) or 0.0)})
    if not pf:
        return None, None
    return pf, "results/loop.json (loop/run.py) -> re-scored by sim/engine.py"


def main():
    t0 = time.perf_counter()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    log = []

    # ---- per-region baselines ---------------------------------------------
    regions_out = []
    regional = {}
    for code in REGION_ORDER:
        reg = load_region(code)
        regions_out.append({
            # CONTRACT §5 code (CAL/TEX/PJM/MISO); site_curves() also accepts the
            # EIA aliases (CISO/ERCO/MIDA/MIDW) so both spellings resolve to one region.
            "code": reg["region"],
            "eia_code": reg["eia_region"],
            "aliases": sorted({reg["region"], reg["eia_region"], reg["ba"], reg["name"]}),
            "name": reg["name"],
            "ba": reg["ba"],
            "peak_mw": _r(reg["peak_mw"], 1),
            "peak_local": reg["peak_local"],
            "stress_day": reg["stress_day"],
            "p95_mw": _r(reg["p95_mw"], 1),
        })
        rows, _ = baseline_block(code)
        regional[code] = rows
        log.append("%s (%s): " % (reg["region"], reg["name"]) + " | ".join(
            "%s del=%.0f mwmo net=%.0f" % (k, v["delivered_mwmonths"],
                                           v["net_value_musd"])
            for k, v in rows.items()))

    # ---- primary region blocks -------------------------------------------
    base_rows, base_pf = baseline_block(PRIMARY_REGION)
    loop_pf, loop_src = load_loop_best()
    if loop_pf is not None:
        best_pf, best_src = loop_pf, loop_src
        log.append("best: embedded portfolio from results/loop.json and re-scored")
    else:
        best_pf = reference_policy(PRIMARY_REGION)
        best_src = "sim/run.py reference policy (loop.json not found)"
        log.append("best: loop.json not found -> reference compliant policy used")
    best = best_block(PRIMARY_REGION, best_pf, best_src)

    # cross-check the stress-day curtailment helper against evaluate()
    res_best = evaluate(PRIMARY_REGION, best_pf)
    chk = _hourly_curtail_mw(PRIMARY_REGION, best_pf)
    annual_check = float(chk.sum())
    annual_eval = float(sum(res_best["curtail_mwh_by_site"].values()))
    if abs(annual_check - annual_eval) > max(1.0, 0.01 * annual_eval):
        log.append("WARN hourly curtail helper mismatch: %.1f vs %.1f MWh"
                   % (annual_check, annual_eval))

    grid = build_grid(PRIMARY_REGION, best_pf)

    # ---- comparison (status quo = queue_order firm baseline) ---------------
    ref_name = "queue_order"
    ref = base_rows[ref_name]
    naive = base_rows["max_mw_no_flex"]
    comparison = {
        "ratio_mwmonths": _r(best["delivered_mwmonths"] / (ref["delivered_mwmonths"] or 1), 2),
        "ratio_mw12": (None if not ref["compliant_mw12"] else
                       _r(best["compliant_mw12"] / ref["compliant_mw12"], 2)),
        "ratio_mw12_note": "queue_order delivers 0 MW at month 12 (firm queue 18-36 "
                           "months), so the firm-baseline ratio is unbounded (infinity)",
        "ratio_net_value": _r(best["net_value_musd"] / abs(ref["net_value_musd"] or 1), 2),
        "violations": "%.1f MWh" % best["violations_mwh"],
        "sla": "per-site SLA met (0 MWh breach)" if best["sla_breach_mwh"] == 0
               else "%.1f MWh over budget" % best["sla_breach_mwh"],
        "agent_net_value_musd": best["net_value_musd"],
        "agent_compliant_mwmonths": best["compliant_mwmonths"],
        "agent_compliant_mw12": best["compliant_mw12"],
        "baseline_ref": ref_name,
        "baseline_label": ref["label"],
        "baseline_net_value_musd": ref["net_value_musd"],
        "baseline_compliant_mwmonths": ref["compliant_mwmonths"],
        "baseline_mw12": ref["compliant_mw12"],
        "naive_net_value_musd": naive["net_value_musd"],
        "naive_mw12": naive["mw_at_month12"],
        "naive_sla_breach_mwh": naive["sla_breach_mwh"],
        "naive_note": "gross MW looks fine, net value is destroyed by SLA penalties",
    }

    payload = {
        "meta": {
            "project": "GRIDRUSH",
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "region": PRIMARY_REGION,
            "region_name": load_region(PRIMARY_REGION)["name"],
            "horizon_months": HORIZON_MONTHS,
            "n_sites": 40,
            "n_substations": 8,
            "assumptions_version": ASSUMPTIONS_VERSION,
            "regions_run": REGION_ORDER,
            "data": "real 2025 EIA-930 hourly shape (12 BA extract); synthetic site "
                    "geometry and interconnection timelines, parameters documented "
                    "in sim/assumptions.md",
            "wall_s": None,
        },
        "regions": regions_out,
        "sites": build_sites(PRIMARY_REGION),
        "grid": grid,
        "baselines": base_rows,
        "iterations": [],          # stub: the loop owns the learning curve
        "best": best,              # stub, mirrored from loop.json when present
        "comparison": comparison,
        "regional_benchmarks": regional,
        "run_log": log,
    }
    payload["meta"]["wall_s"] = round(time.perf_counter() - t0, 2)

    with open(OUT_PATH, "w") as fh:
        json.dump(payload, fh, indent=1)

    # data/sites.json: deterministic portfolio (CONTRACT §3: data/ owned by Lead,
    # sites.json generated by sim from the fixed seed; written only if absent).
    sites_path = os.path.join(_ROOT, "data", "sites.json")
    if not os.path.exists(sites_path):
        with open(sites_path, "w") as fh:
            json.dump({"region": PRIMARY_REGION, "seed": 7,
                       "n_sites": len(payload["sites"]),
                       "sites": payload["sites"]}, fh, indent=1)
    try:
        n_vals = sum(len(v) for v in (grid["demand_mw"], grid["solar_mw"], grid["u"]))
    except (KeyError, TypeError):
        n_vals = 0
    print("sim_baseline.json: region=%s baselines=%d sites=%d grid_series=%d best_sites=%d wall=%.2fs"
          % (PRIMARY_REGION, len(base_rows), len(payload["sites"]), n_vals,
             best["n_sites"], payload["meta"]["wall_s"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
