#!/usr/bin/env python3
"""Generate web/sample_run.json for the GRIDRUSH dashboard (offline dev data).

Purpose: while sim/ and loop/ are still empty, the dashboard needs plausible data
strictly per the CONTRACT.md §5 schema. Real shapes come from data/us_grid_hourly_2025.csv
(EIA-930, CISO/CAISO, 2025); site geometry and interconnection timelines are synthetic,
as in the contract. No external networks or libraries, stdlib only.

Usage:
    python3 web/make_sample.py [--region CAL] [--out web/sample_run.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from datetime import datetime, timezone
from pathlib import Path

WEB = Path(__file__).resolve().parent
GRIDRUSH = WEB.parent
DATA_CSV = GRIDRUSH / "data" / "us_grid_hourly_2025.csv"
SUMMARY_CSV = GRIDRUSH / "data" / "us_grid_summary_2025.csv"

REGION_CODES = {
    "CAL": "CISO",
    "TEX": "ERCO",
    "PJM": "PJM",
    "MISO": "MISO",
}

# --- synthetic substations -------------------------------------------------
# (id, cap_mw, headroom_fraction_at_peak, lf derived) — headroom_fraction < 0
# means the substation is already overloaded at the peak hour: skip only.
SUBSTATIONS = [
    ("S01", 42.0, 0.120),
    ("S02", 55.0, 0.030),
    ("S03", 18.0, -0.010),   # fully loaded — "many distribution areas are"
    ("S04", 60.0, 0.180),    # already fully loaded" (Arham, talk)
    ("S05", 30.0, 0.080),
    ("S06", 24.0, 0.020),
    ("S07", 36.0, 0.220),
    ("S08", 20.0, 0.060),
]

# Agent plans per substation: modes, and how many times the requested MW
# exceeds free headroom at the peak hour (>1 => flexible sites curtail).
PLANS = {
    "S01": {"modes": ["flex", "flex", "battery"], "factor": 1.06},
    "S02": {"modes": ["flex"], "factor": 1.04},
    "S03": {"modes": [], "factor": 0.0},
    "S04": {"modes": ["firm", "flex", "flex", "battery"], "factor": 1.05},
    "S05": {"modes": ["flex", "flex", "battery"], "factor": 1.04},
    "S06": {"modes": ["flex"], "factor": 1.02},
    "S07": {"modes": ["firm", "flex", "flex", "battery"], "factor": 1.06},
    "S08": {"modes": ["flex"], "factor": 1.03},
}

CENTER = {
    "S01": (-122.35, 37.78),
    "S02": (-121.95, 37.55),
    "S03": (-121.55, 37.90),
    "S04": (-121.95, 38.35),
    "S05": (-121.30, 38.10),
    "S06": (-120.80, 37.40),
    "S07": (-120.35, 38.05),
    "S08": (-119.85, 37.55),
}


def load_region_rows(region_code: str):
    ba = REGION_CODES[region_code]
    rows = []
    with DATA_CSV.open(newline="") as f:
        for row in csv.DictReader(f):
            if row["ba"] != ba:
                continue
            if not row["demand_mw"] or not row["solar_mw"]:
                continue
            rows.append(row)
    if len(rows) != 8760:
        raise SystemExit(f"expected 8760 rows for {ba}, got {len(rows)}")
    return rows


def p95(values):
    return sorted(values)[int(len(values) * 0.95)]


def round2(x):
    return round(float(x), 2)


def make_sites(rng: random.Random):
    """40 sites: 8 substations x 5. Geometry is synthetic but parameterized."""
    sites = []
    for sid, cap, frac in SUBSTATIONS:
        # derive lf from the desired peak-hour headroom: Hmax = 0.98*cap - lf*cap*u_peak
        u_peak = 43860.0 / 33796.0  # CISO peak / p95 — shared by the regional shape
        lf = max(0.55, min(0.98, (0.98 - frac) / u_peak))
        hmax = max(0.0, (0.98 - lf * u_peak) * cap)
        cx, cy = CENTER[sid]
        for k in range(5):
            max_mw = round(rng.uniform(0.5, 10.0), 1)
            sites.append(
                {
                    "id": f"{sid}-{k + 1}",
                    "substation": sid,
                    "cap_mw": cap,
                    "lf": round(lf, 3),
                    "max_mw": max_mw,
                    "T_firm": rng.randint(18, 36),
                    "T_flex": rng.randint(5, 10),
                    "T_on": rng.randint(4, 7),
                    "Hmax_mw": round2(hmax),
                    "x": round(cx + rng.uniform(-0.055, 0.055), 4),
                    "y": round(cy + rng.uniform(-0.045, 0.045), 4),
                    # recomputed by the hourly simulation below
                    "stress_hours": 0,
                }
            )
    return sites


def pick_portfolio(sites, rng: random.Random):
    """Portfolio of the "best policy": per substation take the largest sites,
    total MW limited to Hmax * factor (flexible sites curtail at the peak)."""
    by_sub = {}
    for s in sites:
        by_sub.setdefault(s["substation"], []).append(s)
    portfolio = []
    for sid, plan in PLANS.items():
        if not plan["modes"]:
            continue
        cand = sorted(by_sub[sid], key=lambda s: -s["max_mw"])
        cap = cand[0]["cap_mw"]
        lf = cand[0]["lf"]
        hmax = cand[0]["Hmax_mw"]
        if hmax <= 0.05:
            continue
        # total request per substation: headroom * factor, capped by max_mw
        budget = min(hmax * plan["factor"], sum(s["max_mw"] for s in cand))
        modes = plan["modes"]
        total_max = sum(cand[i]["max_mw"] for i in range(len(modes)))
        for i, mode in enumerate(modes):
            s = cand[i]
            share = s["max_mw"] / total_max if total_max else 1
            mw = max(0.5, min(s["max_mw"], round(budget * share, 1)))
            item = {
                "site_id": s["id"],
                "mode": mode,
                "mw": mw,
                "sla": 0.999,
                "battery_mwh": 0.0,
                "energize_month": s["T_firm"] if mode == "firm" else (s["T_on"] if mode == "battery" else s["T_flex"]),
            }
            if mode == "battery":
                item["battery_mwh"] = round(mw * rng.uniform(3.5, 6.5), 1)
            if mode == "firm":
                # firm is never curtailed: it must fit the minimum headroom
                item["mw"] = max(0.5, min(item["mw"], s["Hmax_mw"]))
            portfolio.append(item)
    # safety: firm load must not exceed the substation Hmax
    firm_by_sub = {}
    for p in portfolio:
        if p["mode"] == "firm":
            firm_by_sub.setdefault(p["site_id"].split("-")[0], 0.0)
            firm_by_sub[p["site_id"].split("-")[0]] += p["mw"]
    hmax_by_sub = {s["substation"]: s["Hmax_mw"] for s in sites}
    for p in portfolio:
        if p["mode"] == "firm":
            sid = p["site_id"].split("-")[0]
            if firm_by_sub[sid] > hmax_by_sub[sid] + 1e-9:
                p["mw"] = round(max(0.5, p["mw"] * hmax_by_sub[sid] / firm_by_sub[sid]), 1)
    return portfolio


def simulate(sites, portfolio, u_hours):
    """Hourly simulation of the representative year (8760 h): curtailment, availability,
    stress day. Returns per-site stats and arrays for the stress day."""
    site_by_id = {s["id"]: s for s in sites}
    by_sub = {}
    for p in portfolio:
        sid = site_by_id[p["site_id"]]["substation"]
        by_sub.setdefault(sid, []).append(p)

    curt_hours = {p["site_id"]: 0 for p in portfolio}
    curt_mwh = {p["site_id"]: 0.0 for p in portfolio}
    bat_energy = {p["site_id"]: p.get("battery_mwh", 0.0) for p in portfolio}

    # max headroom for stress_hours: count hours when the substation is stressed
    sub_stress_hours = {}
    violation_mwh = 0.0
    curt_by_hour = [0.0] * 8760  # for the stress day / diagnostics

    for h, u in enumerate(u_hours):
        for sid, items in by_sub.items():
            cap = site_by_id[items[0]["site_id"]]["cap_mw"]
            lf = site_by_id[items[0]["site_id"]]["lf"]
            avail = 0.98 * cap - lf * cap * u
            requested = sum(p["mw"] for p in items)
            if avail - requested < 0:
                sub_stress_hours[sid] = sub_stress_hours.get(sid, 0) + 1
            deficit = requested - avail
            if deficit <= 1e-9:
                continue
            # battery covers the deficit up to its annual budget, then flex curtails
            bats = [p for p in items if p["mode"] == "battery"]
            for p in bats:
                if deficit <= 1e-9:
                    break
                take = min(deficit, p["mw"], bat_energy[p["site_id"]])
                if take > 1e-9:
                    take = max(0.0, take)
                    bat_energy[p["site_id"]] -= take
                    deficit -= take
            # remaining deficit is shed by flexible sites proportionally
            flex = [p for p in items if p["mode"] in ("flex", "battery")]
            flex_total = sum(p["mw"] for p in flex)
            if deficit > 1e-9 and flex_total > 0:
                for p in flex:
                    cut = min(p["mw"], deficit * p["mw"] / flex_total)
                    if cut > 0.02:
                        curt_hours[p["site_id"]] += 1
                        curt_mwh[p["site_id"]] += cut
                    deficit -= cut
            # firm load is never curtailed; any deficit is a violation
            if deficit > 1e-6:
                violation_mwh += deficit
            curt_by_hour[h] += max(0.0, requested - avail) if deficit < 0 else 0.0

    # stress day: 2025-08-22, local hours
    stress = None
    return {
        "curt_hours": curt_hours,
        "curt_mwh": curt_mwh,
        "bat_energy": bat_energy,
        "violation_mwh": violation_mwh,
        "sub_stress_hours": sub_stress_hours,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--region", default="CAL", help="CAL (default) — headline region in sample")
    ap.add_argument("--out", default=str(WEB / "sample_run.json"))
    args = ap.parse_args()
    if args.region not in REGION_CODES:
        raise SystemExit(f"unknown region {args.region}; choose from {list(REGION_CODES)}")

    rng = random.Random(7)
    rows = load_region_rows(args.region)
    demand = [round(float(r["demand_mw"]), 1) for r in rows]
    solar = [round(float(r["solar_mw"]), 1) for r in rows]
    u = [d / p95(demand) for d in demand]
    u = [round(x, 5) for x in u]

    sites = make_sites(rng)
    portfolio = pick_portfolio(sites, rng)
    sim = simulate(sites, portfolio, u)

    # --- portfolio metrics -----------------------------------------------------
    site_by_id = {s["id"]: s for s in sites}
    best_sites = []
    delivered = 0.0
    mw12 = 0.0
    capex = 0.0
    sla_breach_mwh = 0.0
    min_avail = 1.0
    mode_totals = {"firm": 0.0, "flex": 0.0, "battery": 0.0}
    for p in portfolio:
        s = site_by_id[p["site_id"]]
        curt_h = sim["curt_hours"][p["site_id"]]
        avail = 1.0 - curt_h / 8760.0
        # SLA: a flexible site curtailing more than 8.76 h/yr drops to 99.0%
        sla = 0.999 if curt_h <= 8.76 else 0.99
        budget_h = (1.0 - sla) * 8760.0
        breach_h = max(0.0, curt_h - budget_h)
        breach_mwh = breach_h * p["mw"]
        sla_breach_mwh += breach_mwh
        if p["mode"] == "battery":
            capex += 0.35 * p["mw"] + 0.25 * p.get("battery_mwh", 0.0)
        if p["mode"] == "firm":
            capex += 0.05 * p["mw"]  # synthetic: engineering studies so firm is not a "free" cheat
        t = p["energize_month"]
        delivered += p["mw"] * max(0, 36 - t) * avail
        if t <= 12:
            mw12 += p["mw"]
        min_avail = min(min_avail, avail)
        mode_totals[p["mode"]] += p["mw"]
        best_sites.append(
            {
                "id": p["site_id"],
                "mode": p["mode"],
                "mw": round2(p["mw"]),
                "sla": sla,
                "battery_mwh": round2(p.get("battery_mwh", 0.0)),
                "energize_month": t,
                "curtail_hours": round(curt_h, 1),
                "avail": round(avail, 5),
                "curtail_mwh": round2(sim["curt_mwh"][p["site_id"]]),
            }
        )
    # monthly_mw: total MW running in each month (36)
    monthly_by_mode = {"firm": [0.0] * 36, "flex": [0.0] * 36, "battery": [0.0] * 36}
    for p in portfolio:
        for m in range(36):
            if m + 1 >= p["energize_month"]:
                monthly_by_mode[p["mode"]][m] += p["mw"]
    monthly = [
        round(sum(monthly_by_mode[mo][m] for mo in monthly_by_mode), 2)
        for m in range(36)
    ]
    delivered = sum(p["mw"] for p in portfolio) * 0  # placeholder, replaced below
    # delivered, weighted by contractual availability
    delivered = sum(
        b["mw"] * max(0, 36 - b["energize_month"]) * b["avail"] for b in best_sites
    )
    net_value = 0.10 * delivered - capex - 5.0 * sla_breach_mwh

    # --- baselines ------------------------------------------------------------
    def baseline_metrics(mode_pick, label, max_frac=1.0):
        chosen = []
        for s in sites:
            if s["Hmax_mw"] <= 0.2:
                continue
            chosen.append(s)
        chosen.sort(key=mode_pick)
        # all-firm: per substation up to min(Hmax, sum max_mw)
        per_sub = {}
        for s in chosen:
            per_sub.setdefault(s["substation"], []).append(s)
        delivered_b = 0.0
        mw12_b = 0.0
        for sid, ss in per_sub.items():
            hmax = ss[0]["Hmax_mw"]
            used = 0.0
            for s in ss:
                w = min(s["max_mw"], max(0.5, hmax - used))
                if w < 0.5:
                    break
                used += w
                t = s["T_firm"]
                delivered_b += w * max(0, 36 - t) * 0.999
                if t <= 12:
                    mw12_b += w
                if used >= hmax:
                    break
        net_b = 0.10 * delivered_b - 0.05 * used if False else 0.10 * delivered_b - 0.05 * sum(
            min(s["max_mw"], s["Hmax_mw"]) for s in sites if s["Hmax_mw"] > 0.2
        )
        return {
            "label": label,
            "delivered_mwmonths": round(delivered_b, 1),
            "mw_at_month12": round(mw12_b, 2),
            "net_value_musd": round(0.10 * delivered_b, 2),
            "violations_mwh": 0.0,
            "ratio": 1.0,
        }

    baselines = {
        "all_firm_greedy": baseline_metrics(
            lambda s: (-s["Hmax_mw"], s["T_firm"]), "All firm, biggest headroom first"
        ),
        "queue_order": baseline_metrics(
            lambda s: (s["T_firm"], -s["max_mw"]), "Firm in interconnection-queue order"
        ),
        "max_mw_no_flex": baseline_metrics(
            lambda s: (-s["max_mw"], s["T_firm"]), "Max MW, no flexibility"
        ),
    }
    best_baseline = max(baselines.values(), key=lambda b: b["delivered_mwmonths"])
    for b in baselines.values():
        b["ratio"] = round(b["delivered_mwmonths"] / best_baseline["delivered_mwmonths"], 3)
    ratio_mwmonths = delivered / max(1e-9, best_baseline["delivered_mwmonths"])
    ratio_mw12 = mw12 / max(0.5, best_baseline["mw_at_month12"])

    # --- iterations: how the agent learned -------------------------------------
    n_iter = 160
    iterations = []
    best_score = -999.0
    first_score = None
    rng2 = random.Random(11)
    for i in range(n_iter):
        progress = 1.0 - math.exp(-i / 23.0)
        target = net_value * (0.35 + 0.65 * progress)
        noise = rng2.gauss(0, 3.2) * (1.0 - 0.5 * progress)
        score = target + noise
        if i == 0:
            score = target * 0.55 - 6.0  # starting policy: violations + a poor portfolio
        is_best = score > best_score + 1e-9
        best_score = max(best_score, score)
        delivered_i = delivered * (0.45 + 0.55 * progress) + rng2.gauss(0, 4)
        violations_i = max(0.0, 14.0 * (1.0 - progress) - 2.0) if i < 22 else 0.0
        iterations.append(
            {
                "iter": i,
                "score": round(score, 3),
                "delivered_mwmonths": round(max(0.0, delivered_i), 2),
                "violations_mwh": round(violations_i, 3),
                "best": is_best,
            }
        )
        if first_score is None:
            first_score = score
    # last point = the final policy
    iterations[-1]["score"] = round(net_value, 3)
    iterations[-1]["delivered_mwmonths"] = round(delivered, 2)
    iterations[-1]["best"] = True

    # --- stress day ----------------------------------------------------------
    stress_rows = [r for r in rows if r["local_time_end"].startswith("2025-08-22")]
    stress_rows.sort(key=lambda r: r["local_time_end"])
    u_day = [float(r["demand_mw"]) / 33796.0 for r in stress_rows]
    demand_day = [round(float(r["demand_mw"]), 1) for r in stress_rows]
    solar_day = [round(max(0.0, float(r["solar_mw"])), 1) for r in stress_rows]
    cap_factor = [round(max(0.0, float(r["solar_mw"])) / 18912.0, 3) for r in stress_rows]
    headroom_day = []
    curtail_day = []
    for i, uu in enumerate(u_day):
        free = 0.0
        requested = 0.0
        for sid, items in {
            sid: [p for p in portfolio if site_by_id[p["site_id"]]["substation"] == sid]
            for sid in {s["substation"] for s in sites}
        }.items():
            cap = site_by_id[items[0]["site_id"]]["cap_mw"] if items else 0.0
            lf = site_by_id[items[0]["site_id"]]["lf"] if items else 0.0
            free += 0.98 * cap - lf * cap * uu
            requested += sum(p["mw"] for p in items)
        headroom_day.append(round(free - requested, 2))
        curtail_day.append(round(max(0.0, requested - free), 2))
    stress = {
        "date": "2025-08-22",
        "local_hours": [int(r["local_time_end"][11:13]) for r in stress_rows],
        "demand_mw": demand_day,
        "solar_mw": solar_day,
        "cap_factor": cap_factor,
        "headroom_mw": headroom_day,
        "curtailment_mw": curtail_day,
    }

    # stress_hours for top-level sites (hours the substation is stressed)
    for s in sites:
        s["stress_hours"] = sim["sub_stress_hours"].get(s["substation"], 0)

    # --- regions for the header -------------------------------------------------
    regions = []
    with SUMMARY_CSV.open(newline="") as f:
        for row in csv.DictReader(f):
            regions.append(
                {
                    "code": row["region"],
                    "name": row["ba_name"],
                    "ba": row["ba"],
                    "peak_mw": float(row["peak_demand_mw"]),
                    "peak_hour_utc": row["peak_hour_utc"],
                }
            )

    total_mw = sum(p["mw"] for p in portfolio)
    payload = {
        "meta": {
            "project": "GRIDRUSH",
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "SAMPLE — synthetic site geometry, real EIA-930 demand/solar shapes",
            "region": args.region,
            "horizon_months": 36,
            "n_sites": len(sites),
            "n_substations": len(SUBSTATIONS),
            "assumptions_version": 1,
        },
        "regions": regions,
        "sites": sites,
        "grid": {
            "region": args.region,
            "demand_mw": demand,
            "solar_mw": solar,
            "u": u,
            "stress_day": stress,
        },
        "baselines": baselines,
        "iterations": iterations,
        "best": {
            "label": "GRIDRUSH agent",
            "params": {
                "search": "simulated annealing",
                "iterations": n_iter,
                "max_curtail_hours": 90,
            },
            "delivered_mwmonths": round(delivered, 1),
            "mw_at_month12": round(mw12, 2),
            "net_value_musd": round(net_value, 2),
            "violations_mwh": round(sim["violation_mwh"], 3),
            "sla_breach_mwh": round(sla_breach_mwh, 2),
            "capex_musd": round(capex, 2),
            "monthly_mw": monthly,
            "monthly_mw_by_mode": {k: [round(v, 2) for v in arr] for k, arr in monthly_by_mode.items()},
            "sites": best_sites,
        },
        "comparison": {
            "ratio_mwmonths": round(ratio_mwmonths, 2),
            "ratio_mw12": round(ratio_mw12, 2),
            "violations": f"{round(sim['violation_mwh'])} MWh",
            "sla": f"{min_avail * 100:.2f}% min site availability",
            "baseline_label": best_baseline["label"],
            "baseline_delivered_mwmonths": best_baseline["delivered_mwmonths"],
            "baseline_mw_at_month12": best_baseline["mw_at_month12"],
        },
        "run_log": [
            f"iter 0 score=-18.42 violations=14.0 MWh (seed policy)",
            f"iter 22 first feasible portfolio: violations=0.0 MWh",
            f"iter {n_iter - 1} best score={net_value:.2f} USD M",
            f"final: {total_mw:.1f} MW across {len(portfolio)} sites, ratio={ratio_mwmonths:.2f}x",
            "SAMPLE DATA: replace with results/loop.json via web/build.py",
        ],
    }

    out = Path(args.out)
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
    print(
        f"  sites={len(sites)} portfolio={len(portfolio)} total_mw={total_mw:.1f} "
        f"delivered={delivered:.0f} mwmo mw12={mw12:.1f} net=${net_value:.1f}M "
        f"ratio={ratio_mwmonths:.2f}x ratio12={ratio_mw12:.2f}x"
    )
    print(f"  min_avail={min_avail:.4f} sla_breach={sla_breach_mwh:.2f} MWh viol={sim['violation_mwh']:.4f}")
    print(f"  curtail hours/site: {[b['curtail_hours'] for b in best_sites]}")


if __name__ == "__main__":
    main()
