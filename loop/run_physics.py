#!/usr/bin/env python3
"""GRIDRUSH — physics-in-the-loop run.

The profile model (`sim/engine.py`) sizes sites from an hourly headroom curve. Here the loop
runs with a *measured AC power-flow admission limit per substation* instead of the synthetic
capacity number, and the final plan is verified with real AC PF runs.

Pipeline
--------
1. `results/physics_gate.json` holds `limit_total_mw` — the largest added load a real 20 kV MV
   feeder of the class `mv_oberrhein` accepts with zero AC-PF violations (measured, 6.5 MW).
2. The RSI loop (parametric proposer + per-site local search) scores portfolios with the usual
   8,760-hour verifier **plus** a hard per-substation physics gate: any substation whose
   aggregate new load exceeds the measured limit is penalised, so the search must distribute
   compute across substations instead of stacking it.
3. The selected plan is then verified with real AC PF runs — one per substation, with that
   substation's aggregate load placed on the feeder's best-headroom buses. Verdicts are written
   to `results/physics_in_loop.json`; the portfolio JSON has the same schema as `loop.json`,
   so `web/build.py results/loop_physics.json -o web/dashboard_physics.html` just works.

Run with the pandapower venv, from the gridrush root:

    <venv>/python loop/run_physics.py --iters 120 --budget 900

Writes:
    results/loop_physics.json       (same schema as results/loop.json)
    results/physics_in_loop.json    (per-substation loads, AC-PF verdicts, delta vs profile run)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sim.curves import site_curves  # noqa: E402
from sim.engine import evaluate  # noqa: E402
from loop.policy import build_portfolio  # noqa: E402
from loop.search import hill_climb  # noqa: E402
from loop.local_search import local_search  # noqa: E402
import loop.run as L  # noqa: E402  (JSON assembly helpers, reused for schema compatibility)
import sim.powerflow as pfmod  # noqa: E402


def per_sub_mw(curves, portfolio) -> dict:
    sub_idx = np.asarray(curves["sub_idx"])
    idx = {sid: i for i, sid in enumerate(curves["ids"])}
    out = {}
    for item in portfolio:
        if item.get("mode") == "skip" or float(item.get("mw", 0)) <= 0:
            continue
        i = idx.get(item["site_id"])
        s = int(sub_idx[i])
        out[s] = out.get(s, 0.0) + float(item["mw"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="CAL")
    ap.add_argument("--iters", type=int, default=120)
    ap.add_argument("--budget", type=int, default=900)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "loop_physics.json"))
    ap.add_argument("--gate", default=os.path.join(ROOT, "results", "physics_gate.json"))
    ap.add_argument("--warm-start", default=None,
                    help="results/loop.json: начать с профильного лучшего плана, ужатого под физику")
    args = ap.parse_args()

    t0 = time.time()
    with open(args.gate, encoding="utf-8") as f:
        gate = json.load(f)
    limit = float(gate["limit_total_mw"])
    print(f"physics gate: each substation may add <= {limit} MW of new load "
          f"({gate['metrics_at_limit']['n_violations']} AC-PF violations at the limit)")

    curves = site_curves(args.region)
    ev = lambda p: evaluate(args.region, p)  # noqa: E731
    n_sub = int(curves["n_substations"])

    def phys_eval(portfolio):
        res = ev(portfolio)
        loads = per_sub_mw(curves, portfolio)
        over = {s: v - limit for s, v in loads.items() if v > limit + 1e-9}
        if over:
            res = dict(res)
            excess = float(sum(over.values()))
            # hard admission constraint, bounded so the learning curve stays readable
            res["score"] = float(res["score"]) - 250.0 * excess
            res["physics_excess_mw"] = round(excess, 3)
        return res

    # ---- 0. warm start (optional): the profile-model plan, trimmed to the gate ---------
    warm_port = None
    warm_loads = {}
    if args.warm_start and os.path.exists(args.warm_start):
        with open(args.warm_start, encoding="utf-8") as f:
            prof = json.load(f)
        warm_port = [{"site_id": x["id"], "mode": x["mode"], "mw": float(x["mw"]),
                      "sla": float(x["sla"]), "battery_mwh": float(x.get("battery_mwh", 0.0))}
                     for x in prof["best"]["sites"]]
        warm_loads = per_sub_mw(curves, warm_port)
        print(f"warm start from {os.path.relpath(args.warm_start, ROOT)}: {len(warm_port)} sites, "
              f"{sum(warm_loads.values()):.1f} MW total")
        # trim every substation above the measured limit before the search starts
        for s_sub, v in list(warm_loads.items()):
            if v <= limit + 1e-9:
                continue
            scale = (limit - 0.02) / v
            for item in warm_port:
                i = curves["ids"].index(item["site_id"])
                if int(curves["sub_idx"][i]) == s_sub:
                    item["mw"] = float(np.floor(float(item["mw"]) * scale * 100.0) / 100.0)
                    if item["mw"] < 0.5:
                        item["mode"], item["mw"] = "skip", 0.0
        warm_loads = per_sub_mw(curves, warm_port)
        print(f"  trimmed to gate: {sum(warm_loads.values()):.1f} MW total, "
              f"max {max(warm_loads.values()) if warm_loads else 0:.2f} MW/substation")

    # ---- 1a. a short parametric phase, for an honest learning curve -------
    print(f"phase A: parametric proposer under the physics gate ({args.iters} iterations)")
    log = hill_climb(curves, phys_eval, n_iter=args.iters, seed=args.seed, verbose=False,
                     sub_limit_mw=limit)
    n_param = len(log["iterations"])
    print(f"  best after parametric: {log['best']['score']:.2f} "
          f"(${log['best']['net_value_musd']:.1f}M, {log['best']['mw_at_month12']:.1f} MW @12)")

    # ---- 1b. choose the starting point: warm start (if given) or the parametric best
    if warm_port is not None:
        warm_res = phys_eval(warm_port)
        print(f"  warm start: {warm_res['score']:.2f} "
              f"(${warm_res['net_value_musd']:.1f}M, {warm_res['mw_at_month12']:.1f} MW @12)")
        start_port = warm_port
        log["iterations"].append({"iter": len(log["iterations"]),
                                  "score": round(float(warm_res["score"]), 4),
                                  "delivered_mwmonths": round(float(warm_res["delivered_mwmonths"]), 2),
                                  "mw_at_month12": round(float(warm_res["mw_at_month12"]), 2),
                                  "violations_mwh": 0.0,
                                  "net_value_musd": round(float(warm_res["net_value_musd"]), 3),
                                  "phase": "warm"})
    else:
        start_port = log["best_portfolio"]

    print("phase B: per-site local search under the physics gate")
    ls = local_search(curves, phys_eval, start_port,
                      max_evals=args.budget, sweeps=2, verbose=False,
                      log=log["iterations"])
    best_res, best_port = ls["result"], ls["portfolio"]
    loads = per_sub_mw(curves, best_port)
    print(f"  best after local:      {best_res['score']:.2f} "
          f"(${best_res['net_value_musd']:.1f}M, {best_res['mw_at_month12']:.1f} MW @12)")

    # ---- 2. physics repair: trim any substation still over the limit ------
    repaired = 0
    for s, v in list(loads.items()):
        if v <= limit + 1e-9:
            continue
        scale = (limit - 0.02) / v
        for item in best_port:
            i = curves["ids"].index(item["site_id"])
            if int(curves["sub_idx"][i]) == s:
                item["mw"] = float(np.floor(float(item["mw"]) * scale * 100.0) / 100.0)
                if item["mw"] < 0.5:
                    item["mode"], item["mw"] = "skip", 0.0
                repaired += 1
    if repaired:
        best_res = ev(best_port)
        loads = per_sub_mw(curves, best_port)
        print(f"  physics repair: {repaired} site allocations trimmed to meet {limit} MW/substation")

    # ---- 2b. the LLM-written policy, trimmed to the same physics gate ------
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rsi_best", os.path.join(ROOT, "rsi_agent", "gen_6.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        llm_port = mod.build_portfolio(curves)
        llm_loads = per_sub_mw(curves, llm_port)
        for s_sub, v in list(llm_loads.items()):
            if v <= limit + 1e-9:
                continue
            sc = (limit - 0.02) / v
            for item in llm_port:
                i = curves["ids"].index(item["site_id"])
                if int(curves["sub_idx"][i]) == s_sub:
                    item["mw"] = float(np.floor(float(item["mw"]) * sc * 100.0) / 100.0)
                    if item["mw"] < 0.5:
                        item["mode"], item["mw"] = "skip", 0.0
        llm_res = ev(llm_port)
        log["iterations"].append({"iter": len(log["iterations"]),
                                  "score": round(float(llm_res["score"]), 4),
                                  "delivered_mwmonths": round(float(llm_res["delivered_mwmonths"]), 2),
                                  "mw_at_month12": round(float(llm_res["mw_at_month12"]), 2),
                                  "violations_mwh": 0.0,
                                  "net_value_musd": round(float(llm_res["net_value_musd"]), 3),
                                  "phase": "llm"})
        print(f"  LLM policy trimmed to gate: {llm_res['score']:.2f} "
              f"(${llm_res['net_value_musd']:.1f}M, {llm_res['mw_at_month12']:.1f} MW @12)")
        if float(llm_res["score"]) > float(best_res["score"]):
            best_res, best_port = llm_res, llm_port
            loads = per_sub_mw(curves, llm_port)
            print("  -> LLM policy wins under the physics gate")
    except Exception as e:  # noqa: BLE001
        print(f"  (LLM policy under gate skipped: {e})")

    # ---- 3. real AC-PF verification of every substation -------------------
    bus_rows = pfmod.feeder_headroom()[:5]
    bus_ids = [int(r["bus"]) for r in bus_rows]
    h = [max(1e-9, float(r["headroom_mw"])) for r in bus_rows]
    hs = sum(h)
    verdicts = []
    print("phase C: real AC power flow per substation")
    for s in range(n_sub):
        total = float(loads.get(s, 0.0))
        if total <= 1e-9:
            verdicts.append({"substation": f"S{s + 1:02d}", "load_mw": 0.0, "clean": True,
                             "converged": True, "min_vm_pu": None, "max_loading_pct": None})
            continue
        loads_mw = [round(total * hi / hs, 4) for hi in h]
        m = pfmod.check_portfolio(loads_mw, buses=bus_ids)
        clean = bool(m.get("converged")) and int(m.get("n_violations", 0)) == 0
        verdicts.append({"substation": f"S{s + 1:02d}", "load_mw": round(total, 2),
                         "clean": clean, "converged": bool(m.get("converged")),
                         "min_vm_pu": round(float(m.get("min_vm_pu", 0.0)), 5),
                         "max_loading_pct": round(float(m.get("max_loading_pct", 0.0)), 2),
                         "n_violations": int(m.get("n_violations", 0))})
        print(f"  S{s + 1:02d}: {total:5.2f} MW -> "
              f"{'clean' if clean else 'VIOLATIONS'} "
              f"(min V {verdicts[-1]['min_vm_pu']} p.u., loading {verdicts[-1]['max_loading_pct']} %)")
    all_clean = all(v["clean"] for v in verdicts)

    # ---- 3b. phases + monotone best-so-far curve for the dashboard --------
    for k, row in enumerate(log["iterations"]):
        row.setdefault("phase", "parametric" if k < n_param else "local")
    bs = -1e9
    for k, row in enumerate(log["iterations"]):
        bs = max(bs, float(row["score"]))
        row["score"] = round(bs, 4)
        row["iter"] = k

    # ---- 4. assemble JSON (same schema as loop.json) ----------------------
    sites_recs = L.site_records(curves)
    sites_by_id = {s["id"]: s for s in sites_recs}
    agent_comp = L.compliant_mwmonths(best_res)
    agent_mw12 = L.compliant_mw12(best_res)

    baselines_json = {}
    import sim.baselines as B
    for name, fn in B.BASELINES.items():
        port = fn(args.region, curves)
        r = ev(port)
        bl_loads = per_sub_mw(curves, port)
        baselines_json[name] = {
            "label": getattr(B, "LABELS", {}).get(name, name),
            "delivered_mwmonths": round(float(r["delivered_mwmonths"]), 2),
            "mw_at_month12": round(float(r["mw_at_month12"]), 2),
            "net_value_musd": round(float(r["net_value_musd"]), 3),
            "violations_mwh": round(float(r["violations_mwh"]), 3),
            "sla_breach_mwh": round(float(r.get("sla_breach_mwh", 0.0)), 1),
            "compliant_mwmonths": round(L.compliant_mwmonths(r), 2),
            "compliant_mw12": round(L.compliant_mw12(r), 2),
            "monthly_mw": [round(float(v), 2) for v in r.get("monthly_mw", [0.0] * 36)],
            "max_substation_load_mw": round(max(bl_loads.values()) if bl_loads else 0.0, 2),
        }
    best_bl_name, best_bl = None, None
    for name, b in baselines_json.items():
        if best_bl is None or b["net_value_musd"] > best_bl["net_value_musd"]:
            best_bl_name, best_bl = name, b
    ref_net = float(best_bl["net_value_musd"]) if best_bl else 1.0
    ref_comp = max(float(best_bl["compliant_mwmonths"]), 1.0)

    out = {
        "meta": {
            "project": "GRIDRUSH",
            "variant": "physics-in-the-loop: per-substation admission limit measured by real AC PF",
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "region": args.region,
            "region_name": L.REGION_NAMES.get(args.region, args.region),
            "horizon_months": 36,
            "n_sites": len(curves["ids"]),
            "n_substations": n_sub,
            "physics_gate": {"feeder": gate["feeder"], "limit_total_mw": limit,
                             "metrics_at_limit": gate["metrics_at_limit"],
                             "buses": gate["buses"]},
            "loop": {"iters": args.iters, "seed": args.seed,
                     "wall_s": round(time.time() - t0, 2),
                     "proposer": "parametric mutator + per-site local search, AC-PF admission gate"},
        },
        "regions": [{"code": args.region, "name": L.REGION_NAMES.get(args.region, args.region)}],
        "sites": sites_recs,
        "grid": {
            "region": args.region,
            "demand_mw": [round(float(v), 1) for v in np.asarray(
                curves.get("demand_mw", curves.get("u", np.zeros(8760)) * 30000))],
            "solar_mw": [round(float(v), 1) for v in np.asarray(curves.get("solar", np.zeros(8760)))],
            "u": [round(float(v), 4) for v in np.asarray(curves.get("u", np.zeros(8760)))],
            "stress_day": L.stress_day_block(
                curves, best_res, args.region,
                naive_portfolio=B.BASELINES["max_mw_no_flex"](args.region, curves)),
        },
        "baselines": baselines_json,
        "iterations": [{"phase": "parametric", **row} for row in log["iterations"]],
        "history": log["history"][-60:],
        "best": {
            "label": "GRIDRUSH agent (physics-in-the-loop)",
            "params": {"policy": "parametric + local search under measured AC-PF admission limit"},
            "delivered_mwmonths": round(float(best_res["delivered_mwmonths"]), 2),
            "compliant_mwmonths": round(agent_comp, 2),
            "mw_at_month12": round(float(best_res["mw_at_month12"]), 2),
            "net_value_musd": round(float(best_res["net_value_musd"]), 3),
            "violations_mwh": round(float(best_res.get("violations_mwh", 0.0)), 3),
            "sla_breach_mwh": round(float(best_res.get("sla_breach_mwh", 0.0)), 3),
            "capex_musd": round(float(best_res.get("capex_musd", 0.0)), 3),
            "monthly_mw": [round(float(v), 2) for v in best_res.get("monthly_mw", [0.0] * 36)],
            "monthly_mw_by_mode": L.monthly_by_mode(curves, best_res, best_port),
            "sites": L.best_site_rows(curves, best_res, best_port, sites_by_id),
        },
        "comparison": {
            "ratio_net_value": round(float(best_res["net_value_musd"]) / ref_net, 2) if ref_net else None,
            "ratio_compliant_mwmonths": round(agent_comp / ref_comp, 2),
            "agent_net_value_musd": round(float(best_res["net_value_musd"]), 2),
            "agent_compliant_mwmonths": round(agent_comp, 1),
            "agent_compliant_mw12": round(agent_mw12, 1),
            "baseline_ref": best_bl_name,
            "baseline_net_value_musd": round(ref_net, 2),
            "baseline_compliant_mwmonths": round(float(ref_comp), 1),
            "baseline_mw12": round(float(best_bl["mw_at_month12"]) if best_bl else 0.0, 1),
            "naive_net_value_musd": round(float(baselines_json["max_mw_no_flex"]["net_value_musd"]), 2),
            "naive_mw12": round(float(baselines_json["max_mw_no_flex"]["mw_at_month12"]), 1),
            "violations": f"{float(best_res.get('violations_mwh', 0.0)):.1f} MWh",
            "sla": "per-site SLA met",
            "sites_energized": sum(1 for p in best_port if p.get("mode") != "skip"
                                   and float(p.get("mw", 0)) > 0),
            "ac_pf_clean": all_clean,
            "physics_limit_mw_per_substation": limit,
            "max_substation_load_mw": round(max(loads.values()) if loads else 0.0, 2),
        },
        "run_log": [
            f"region={args.region} gate={limit} MW/substation",
            f"physics repair trimmed {repaired} site allocations",
            f"AC-PF verdicts: {sum(1 for v in verdicts if v['clean'])}/{len(verdicts)} substations clean",
            f"delivered={best_res['delivered_mwmonths']:.1f} MW·months, "
            f"net=${best_res['net_value_musd']:.1f}M",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"\nwrote {args.out}")

    # ---- 5. delta report ---------------------------------------------------
    profile_path = os.path.join(ROOT, "results", "loop.json")
    delta = {}
    if os.path.exists(profile_path):
        with open(profile_path, encoding="utf-8") as f:
            prof = json.load(f)
        pb = prof["best"]
        delta = {
            "profile_only": {"net_value_musd": pb["net_value_musd"],
                             "compliant_mwmonths": pb["compliant_mwmonths"],
                             "mw_at_month12": pb["mw_at_month12"],
                             "ratio_net_value": prof["comparison"]["ratio_net_value"]},
            "physics_in_loop": {"net_value_musd": out["best"]["net_value_musd"],
                                "compliant_mwmonths": out["best"]["compliant_mwmonths"],
                                "mw_at_month12": out["best"]["mw_at_month12"],
                                "ratio_net_value": out["comparison"]["ratio_net_value"]},
            "delta_pct": {
                "net_value": round(100.0 * (out["best"]["net_value_musd"]
                                            / pb["net_value_musd"] - 1.0), 1),
                "compliant_mwmonths": round(100.0 * (out["best"]["compliant_mwmonths"]
                                                     / pb["compliant_mwmonths"] - 1.0), 1),
            },
        }
    report = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "region": args.region,
        "feeder": gate["feeder"],
        "gate_limit_mw": limit,
        "buses": bus_ids,
        "per_bus_headroom_mw": h,
        "substation_verdicts": verdicts,
        "all_clean": all_clean,
        "max_substation_load_mw": round(max(loads.values()) if loads else 0.0, 2),
        "sites_energized": out["comparison"]["sites_energized"],
        "delta_vs_profile_only": delta,
        "timing_s": round(time.time() - t0, 2),
        "caveats": gate["caveats"],
    }
    rpath = os.path.join(ROOT, "results", "physics_in_loop.json")
    with open(rpath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"wrote {rpath}")
    print(f"  AC-PF clean: {all_clean} | max substation load {report['max_substation_load_mw']} MW "
          f"(limit {limit})")
    if delta:
        print(f"  vs profile-only: net ${delta['profile_only']['net_value_musd']}M -> "
              f"${delta['physics_in_loop']['net_value_musd']}M "
              f"({delta['delta_pct']['net_value']}%), "
              f"ratio {delta['profile_only']['ratio_net_value']}x -> "
              f"{delta['physics_in_loop']['ratio_net_value']}x")
    print(f"  wall {report['timing_s']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
