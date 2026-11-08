#!/usr/bin/env python3
"""GRIDRUSH engine tests -- fast, deterministic, no network.

    python3 sim/test_engine.py

8 checks: data shape / u-normalisation, site determinism, empty portfolio,
firm over-subscription, flex curtailment, availability formula, battery effect,
SLA breach definition, determinism and the <100 ms evaluate() budget.
"""
import os
import sys
import time

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sim.curves import site_curves  # noqa: E402
from sim.data import load_region, make_sites  # noqa: E402
from sim.engine import (HORIZON_MONTHS, SLA_BUDGET_HOURS,  # noqa: E402
                        evaluate)

REGION = "CAL"
PASS = []


def check(name, cond, detail=""):
    if not cond:
        raise AssertionError("%s FAILED %s" % (name, detail))
    PASS.append(name)


def main():
    t_all = time.perf_counter()
    reg = load_region(REGION)
    c = site_curves(REGION)
    sites = make_sites(REGION)

    # 1. data: 8760 hours, u = demand / p95, stress day = peak-demand day
    check("1 load_region shape",
          len(reg["demand_mw"]) == 8760 and len(reg["u"]) == 8760,
          "hours=%d" % len(reg["demand_mw"]))
    check("1 u normalised by p95",
          abs(float(np.max(reg["demand_mw"])) / float(np.percentile(reg["demand_mw"], 95))
              - float(np.max(reg["u"]))) < 1e-9)
    peak_idx = int(np.argmax(reg["demand_mw"]))
    peak_day = str(reg["local_time"][peak_idx])[:10]
    check("1 stress_day is the peak-demand day", reg["stress_day"] == peak_day,
          "%s vs %s" % (reg["stress_day"], peak_day))
    check("1 no NaN in demand/u", not np.isnan(reg["demand_mw"]).any()
          and not np.isnan(reg["u"]).any())

    # 2. deterministic sites: seed 7 -> identical structures
    sites_b = make_sites(REGION)
    check("2 make_sites deterministic", sites == sites_b)
    check("2 site grid 8x5",
          len(sites) == 40 and len({s["substation"] for s in sites}) == 8,
          "n=%d subs=%d" % (len(sites), len({s["substation"] for s in sites})))
    check("2 site fields",
          all(k in sites[0] for k in ("id", "substation", "cap_mw", "lf", "max_mw",
                                      "T_firm", "T_flex", "T_on", "fiber",
                                      "permit_days", "x", "y")))
    check("2 site size 0.5-10 MW",
          all(0.5 <= s["max_mw"] <= 10.0 for s in sites))
    check("2 timelines", all(18 <= s["T_firm"] <= 36 and 5 <= s["T_flex"] <= 10
                             and s["T_on"] > s["T_flex"] for s in sites))

    # 3. empty portfolio -> all zeros, zero violations
    r0 = evaluate(REGION, [])
    check("3 empty portfolio zero",
          r0["delivered_mwmonths"] == 0 and r0["violations_mwh"] == 0
          and r0["net_value_musd"] == 0 and r0["mw_at_month12"] == 0
          and all(v == 0 for v in r0["monthly_mw"]))

    # 4. existing load alone never breaches; firm over-subscription does
    check("4 empty grid is compliant", r0["violations_mwh"] == 0)
    rows = np.flatnonzero(c["sub_idx"] == 0)
    Hmin = float(np.min(c["H_sub"][0]))
    safe = [{"site_id": c["ids"][i], "mode": "firm", "mw": max(0.5, Hmin / rows.size),
             "sla": 0.999, "battery_mwh": 0.0} for i in rows]
    r_safe = evaluate(REGION, safe)
    over = [dict(p, mw=p["mw"] * 4.0) for p in safe]
    r_over = evaluate(REGION, over)
    check("4 firm within headroom -> 0 violations", r_safe["violations_mwh"] == 0,
          "viol=%s" % r_safe["violations_mwh"])
    check("4 firm over-subscription -> violations", r_over["violations_mwh"] > 0,
          "viol=%s" % r_over["violations_mwh"])
    check("4 safe firm is fully available",
          all(abs(a - 1.0) < 1e-12 for a in r_safe["avail_by_site"].values()))

    # 5. flex may over-subscribe the substation: curtailment, never violations
    flex = [{"site_id": c["ids"][i], "mode": "flex", "mw": float(c["max_mw"][i]),
             "sla": 0.999, "battery_mwh": 0.0} for i in range(c["n_sites"])]
    rf = evaluate(REGION, flex)
    check("5 flex over-subscription -> 0 violations", rf["violations_mwh"] == 0,
          "viol=%s" % rf["violations_mwh"])
    check("5 flex does curtail (avail < 1 on some site)",
          any(a < 1.0 - 1e-9 for a in rf["avail_by_site"].values()))

    # 6. avail = 1 - curtailed_hours/8760 and battery reduces curtailed hours
    for sid, avail in rf["avail_by_site"].items():
        ch = rf["curtail_hours_by_site"][sid]
        assert abs(avail - (1.0 - ch / 8760.0)) < 1e-6, sid
    check("6 avail formula", True)
    wide = [{"site_id": c["ids"][i], "mode": "flex",
             "mw": float(c["max_mw"][i]) * 2.0,  # clamped to Hmax
             "sla": 0.99, "battery_mwh": 0.0} for i in range(10)]
    r_wide = evaluate(REGION, wide)
    bat = [dict(p, mode="battery", battery_mwh=p["mw"] * 6.0) for p in wide]
    r_bat = evaluate(REGION, bat)
    cur_flex = sum(r_wide["curtail_hours_by_site"].values())
    cur_bat = sum(r_bat["curtail_hours_by_site"].values())
    check("6 battery reduces curtailment hours", cur_bat < cur_flex,
          "flex=%s bat=%s" % (cur_flex, cur_bat))
    check("6 battery costs capex",
          r_bat["capex_musd"] > 0.0 and r_wide["capex_musd"] == 0.0,
          "bat=%.2f flex=%.2f" % (r_bat["capex_musd"], r_wide["capex_musd"]))

    # 7. SLA breach: hours over budget are the breach (99.99% budget = 0.876 h)
    # site on the most-loaded substation (S08): nameplate headroom is constrained
    # in the evening peak, so a flex site at nameplate curtails.
    wid = "S08-1"
    wi = c["ids"].index(wid)
    mw_sla = float(min(c["max_mw"][wi], c["Hmax_mw"][wi]))
    tight = [{"site_id": wid, "mode": "flex", "mw": mw_sla,
              "sla": 0.9999, "battery_mwh": 0.0}]
    loose = [dict(p, sla=0.99) for p in tight]
    r_tight = evaluate(REGION, tight)
    r_loose = evaluate(REGION, loose)
    check("7 99.99% SLA breaches on curtailment",
          r_tight["curtail_hours_by_site"][wid] > 1.0
          and r_tight["sla_breach_mwh"] > 0,
          "curt_h=%s breach=%s" % (r_tight["curtail_hours_by_site"][wid],
                                   r_tight["sla_breach_mwh"]))
    check("7 99% SLA more forgiving",
          r_loose["sla_breach_mwh"] < r_tight["sla_breach_mwh"])
    check("7 zero violations in both", r_tight["violations_mwh"] == 0
          and r_loose["violations_mwh"] == 0)

    # 8. determinism + performance
    r_a = evaluate(REGION, flex)
    r_b = evaluate(REGION, flex)
    check("8 evaluate deterministic", r_a == r_b)
    full = [{"site_id": c["ids"][i], "mode": ("flex" if i % 2 else "battery"),
             "mw": float(c["max_mw"][i]), "sla": (0.999 if i % 3 else 0.9999),
             "battery_mwh": 0.0 if i % 2 else float(c["max_mw"][i]) * 4.0}
            for i in range(c["n_sites"])]
    evaluate(REGION, full)  # warm caches
    t0 = time.perf_counter()
    for _ in range(5):
        evaluate(REGION, full)
    ms = (time.perf_counter() - t0) / 5.0 * 1000.0
    check("8 evaluate < 100 ms (40 sites x 8760 h)", ms < 100.0, "%.1f ms" % ms)
    check("8 monthly_mw length", len(r_a["monthly_mw"]) == HORIZON_MONTHS)
    check("8 monthly_mw monotone in energize month",
          r_a["monthly_mw"][0] <= r_a["monthly_mw"][-1] + 1e-9)

    print("PASS %d/%d checks in %.2fs (evaluate %.1f ms)"
          % (len(PASS), len(PASS), time.perf_counter() - t_all, ms))
    for name in PASS:
        print("  ok  %s" % name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
