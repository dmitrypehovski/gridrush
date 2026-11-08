"""gen_1: exact per-substation greedy over (mode, mw, SLA).

Idea (vs. parametric gen_0): the substation headroom curve H_sub[s] is the only
scarcity, and substations are independent. For one site, value is
    0.10 * rev_mult * mw * (36 - T) * avail
with avail = 1 - #{h : cap_left[h] < mw}/8760, which is a step function of mw.
So the optimum for a site sits exactly at a breakpoint of the sorted cap_left
curve, i.e. mw = sorted(cap_left)[k] for k <= budget_hours(SLA). We enumerate
those breakpoints for all three SLA levels (and a few battery targets), take the
max-value option, then deplete cap_left exactly like sim.engine does.
Battery: sized to cover the worst day's deficit (daily DoD budget), capex =
0.35/MW + 0.25/MWh, energize at T_on.
"""
from __future__ import annotations

import numpy as np

from loop.policy import (SLA_LEVELS, REV_PER_MW_MONTH, BAT_CAPEX_MW,
                         BAT_CAPEX_MWH, repair_portfolio)

HORIZON = 36.0
MIN_MW = 0.5


def _bat_mwh(deficit: np.ndarray) -> float:
    days = min(365, deficit.size // 24)
    if days <= 0:
        return float(deficit.sum()) / 0.9
    d = deficit[: days * 24].reshape(days, 24)
    return float(d.sum(axis=1).max()) / 0.90


def build_portfolio(curves: dict) -> list[dict]:
    ids = list(curves["ids"])
    n = len(ids)
    H = np.asarray(curves["H"], dtype=float)
    H_sub = np.asarray(curves["H_sub"], dtype=float)
    sub_idx = np.asarray(curves["sub_idx"])
    max_mw = np.asarray(curves["max_mw"], dtype=float)
    T_flex = np.asarray(curves["T_flex"], dtype=float)
    T_on = np.asarray(curves["T_on"], dtype=float)

    portfolio = [{"site_id": ids[i], "mode": "skip", "mw": 0.0, "sla": 0.999,
                  "battery_mwh": 0.0} for i in range(n)]

    S = H_sub.shape[0]
    for s in range(S):
        rows = list(np.flatnonzero(sub_idx == s))
        if not rows:
            continue
        # engine serves flex/battery in (T_eff, id) order -> early sites own the
        # scarce low-headroom hours, so they should get first pick.
        rows.sort(key=lambda i: (T_flex[i], ids[i]))
        cap_left = H_sub[s].copy()
        for i in rows:
            mw_cap = float(max_mw[i])
            if mw_cap < MIN_MW or float(cap_left.max()) < MIN_MW:
                continue
            R = cap_left
            R_sorted = np.sort(R)
            mon_flex = max(0.0, HORIZON - float(T_flex[i]))
            mon_on = max(0.0, HORIZON - float(T_on[i]))

            best_v = 0.0  # skip
            best = None

            # ---- flex: enumerate breakpoints per SLA level
            for sla, budget_h, mult in SLA_LEVELS:
                kmax = int(np.floor(min(budget_h, 8759.0)))
                # breakpoints: sorted cap values at k = 0..kmax, clipped by nameplate
                for k in range(0, min(kmax, R_sorted.size - 1) + 1):
                    mw = float(min(R_sorted[k], mw_cap))
                    if mw < MIN_MW:
                        continue
                    kk = int(np.searchsorted(R_sorted, mw, side="left"))
                    if kk > kmax:
                        continue
                    avail = 1.0 - kk / 8760.0
                    v = REV_PER_MW_MONTH * mult * mw * mon_flex * avail
                    if v > best_v:
                        best_v, best = v, ("flex", mw, float(sla), 0.0)

            if best is None:
                continue
            mode, mw, sla, bmwh = best
            portfolio[i] = {"site_id": ids[i], "mode": mode,
                            "mw": float(np.floor(mw * 100.0) / 100.0),
                            "sla": sla, "battery_mwh": round(bmwh, 2)}
            # deplete exactly like sim.engine.evaluate
            load = np.minimum(portfolio[i]["mw"], np.maximum(0.0, cap_left))
            cap_left = cap_left - load

    return repair_portfolio(curves, portfolio)
