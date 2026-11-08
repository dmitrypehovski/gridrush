#!/usr/bin/env python3
"""GRIDRUSH — physics gate: how much load one real MV feeder can actually take.

The profile model in `sim/engine.py` sizes sites from an hourly headroom curve (the shape of
data a utility publishes: PG&E ICA gives 576 hourly values per line section). This module
replaces that *assumption* with a measured AC power-flow limit, so the optimizer can be run
with real physics as an admission constraint instead of as a post-hoc check.

Run with the pandapower venv (see sim/POWERFLOW.md), from the gridrush root:

    <venv>/python sim/physics_gate.py

Writes `results/physics_gate.json`:
  {"feeder", "buses", "per_bus_headroom_mw", "limit_total_mw", "clean_by_total": [...],
   "first_violation_total_mw", "metrics_at_limit", "timing", "caveats"}

The single number the rest of the pipeline cares about is `limit_total_mw`: the largest total
added load, spread over the feeder's best-headroom buses in proportion to their headroom, that
still passes AC power flow with zero violations (bus voltage 0.94–1.06 p.u., every line and
transformer at or below 100 % of rating).
"""
from __future__ import annotations

import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")

try:
    import sim.powerflow as pfmod  # noqa: E402
except ImportError:  # direct execution: python sim/physics_gate.py
    import powerflow as pfmod  # type: ignore  # noqa: E402


def _loads_for(total_mw: float, bus_rows: list[dict]) -> tuple[list[float], list[int]]:
    """Spread a total MW over buses in proportion to their own headroom."""
    h = [max(1e-9, float(r["headroom_mw"])) for r in bus_rows]
    s = sum(h)
    loads = [round(total_mw * hi / s, 4) for hi in h]
    return loads, [int(r["bus"]) for r in bus_rows]


def main() -> int:
    t0 = time.time()
    state = pfmod._ensure_feeder()  # noqa: SLF001 - intentional reuse of the measured feeder
    bus_rows = pfmod.feeder_headroom()[:5]  # best-headroom load-centre buses
    buses = [int(r["bus"]) for r in bus_rows]
    per_bus = [float(r["headroom_mw"]) for r in bus_rows]

    # clean / not-clean curve over total added load (used as a chart and a sanity check)
    clean_by_total = []
    total = 4.0
    limit = 0.0
    while total <= 16.0 + 1e-9:
        loads, bs = _loads_for(total, bus_rows)
        m = pfmod.check_portfolio(loads, buses=bs)
        ok = bool(m.get("converged")) and int(m.get("n_violations", 0)) == 0
        clean_by_total.append({"total_mw": round(total, 2), "clean": ok,
                               "min_vm": round(float(m.get("min_vm_pu", 0.0)), 5),
                               "max_loading_pct": round(float(m.get("max_loading_pct", 0.0)), 2),
                               "n_violations": int(m.get("n_violations", 0))})
        if ok:
            limit = total
        total = round(total + 0.5, 2)

    # bisection for the exact limit (monotone: if it is clean at x, it is clean below x)
    lo, hi = limit, min(16.0, limit + 0.5)
    for _ in range(12):
        mid = 0.5 * (lo + hi)
        loads, bs = _loads_for(mid, bus_rows)
        m = pfmod.check_portfolio(loads, buses=bs)
        ok = bool(m.get("converged")) and int(m.get("n_violations", 0)) == 0
        if ok:
            lo = mid
        else:
            hi = mid
    limit = round(lo, 3)

    loads, bs = _loads_for(limit, bus_rows)
    at_limit = pfmod.check_portfolio(loads, buses=bs)
    loads_over, bs_over = _loads_for(round(limit + 0.5, 2), bus_rows)
    first_bad = pfmod.check_portfolio(loads_over, buses=bs_over)

    out = {
        "feeder": "mv_oberrhein",
        "feeder_note": ("real 20 kV German MV network shipped with pandapower; 179 buses, "
                        "181 lines, 2 x 25 MVA 110/20 kV transformers, served load 37.1 MW"),
        "buses": buses,
        "per_bus_headroom_mw": per_bus,
        "loads_at_limit_mw": loads,
        "limit_total_mw": limit,
        "clean_by_total": clean_by_total,
        "metrics_at_limit": {
            "converged": bool(at_limit.get("converged")),
            "min_vm_pu": round(float(at_limit.get("min_vm_pu", 0.0)), 5),
            "max_loading_pct": round(float(at_limit.get("max_loading_pct", 0.0)), 2),
            "n_violations": int(at_limit.get("n_violations", 0)),
        },
        "first_violation": {
            "total_mw": round(limit + 0.5, 2),
            "n_violations": int(first_bad.get("n_violations", 0)),
            "max_loading_pct": round(float(first_bad.get("max_loading_pct", 0.0)), 2),
            "min_vm_pu": round(float(first_bad.get("min_vm_pu", 0.0)), 5),
        },
        "violation_definition": ("bus |V| outside 0.94-1.06 p.u. or any line/transformer "
                                 "loading above 100 % of rating; new loads cos(phi)=0.98"),
        "timing_s": {"total": round(time.time() - t0, 2)},
        "caveats": [
            "one real feeder; the 8 synthetic substations of the hackathon model are treated as "
            "8 independent MV feeders of this class, each with the measured limit",
            "limit is total added load spread over the 5 best-headroom buses in proportion to "
            "their headroom; a different bus mix gives a slightly different number",
            "reported for the hackathon demo, not a connection study",
        ],
    }
    os.makedirs(RESULTS, exist_ok=True)
    path = os.path.join(RESULTS, "physics_gate.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {path}")
    print(f"  limit_total_mw = {limit} MW   (at limit: min V {out['metrics_at_limit']['min_vm_pu']} p.u., "
          f"max loading {out['metrics_at_limit']['max_loading_pct']} %)")
    print(f"  first violation at {out['first_violation']['total_mw']} MW: "
          f"{out['first_violation']['n_violations']} violations")
    print(f"  wall {out['timing_s']['total']} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
