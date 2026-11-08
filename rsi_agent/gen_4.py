"""gen_4: EXACT optimum of the flex-only design space (DP over cumulative MW).

gen_3's tier fill leaves slack when a tier boundary only partially fits a site
(e.g. S02-3 with max_mw=0.5 "eats" a whole site slot in tier B and the rest of
that tier is lost). Instead of constructing, solve the substation exactly.

Key fact (verified against sim.engine): with the engine's allocation order
(T_eff, id), a site's curtailed hours depend only on the CUMULATIVE MW of the
sites allocated before/at it:
    avail_i = 1 - #{h : H_sub[h] < P_i} / 8760,   P_i = sum_{j<=i} mw_j
and its SLA is free, so the best compatible price multiplier is
    k=0 -> 99.99% x1.25,  k<=8 -> 99.9% x1.00,  k<=87 -> 99.0% x0.80.
Reward  0.10 * mult * mw * (36-T) * avail  is then a function of P only, so a DP
over P in the 88 breakpoints sorted(H_sub)[k] (k<=87) with the constraint
mw_i = P_i - P_{i-1} <= max_mw_i gives the exact per-substation optimum.
Substations are independent -> the whole problem is solved exactly.
Battery would only add violations (verifier counts covered MW as load) and firm
is dominated by flex@99.99% (same physics, T_firm 18-36 vs T_flex 5-10).
"""
from __future__ import annotations

import numpy as np

from loop.policy import REV_PER_MW_MONTH, repair_portfolio

HOR = 36.0
MIN_MW = 0.5
HOURS = 8760


def _opt_sub(H, order, T, mx):
    Rs = np.sort(H)
    kmax = min(87, Rs.size - 1)
    Q = [0.0] + [float(Rs[k]) for k in range(0, kmax + 1)]
    Q = sorted(set(Q))
    n = len(Q)
    kk = np.array([int(np.searchsorted(Rs, q, side="left")) for q in Q])
    avail = 1.0 - kk / HOURS
    mult = np.where(kk <= 0, 1.25, np.where(kk <= 8, 1.00, np.where(kk <= 87, 0.80, 0.0)))
    Qa = np.array(Q)

    NEG = -1e18
    dp = np.full(n, NEG)
    dp[0] = 0.0
    parents = []
    for i in order:
        c = REV_PER_MW_MONTH * max(0.0, HOR - T[i])
        new = np.full(n, NEG)
        par = np.full(n, -1, dtype=int)
        for j in range(n):
            if dp[j] <= NEG / 2:
                continue
            # skip this site
            if dp[j] > new[j]:
                new[j], par[j] = dp[j], j
            # allocate so that cumulative becomes Q[l]
            for l in range(j + 1, n):
                m = Qa[l] - Qa[j]
                if m > mx[i] + 1e-12:
                    break
                if m < MIN_MW:
                    continue
                v = dp[j] + c * mult[l] * m * avail[l]
                if v > new[l]:
                    new[l], par[l] = v, j
        dp = new
        parents.append(par)

    j = int(np.argmax(dp))
    best_val = float(dp[j])
    mw = {}
    for idx in range(len(order) - 1, -1, -1):
        p = int(parents[idx][j])
        mw[order[idx]] = float(Qa[j] - Qa[p])
        j = p
    return best_val, mw


def build_portfolio(curves: dict) -> list[dict]:
    ids = list(curves["ids"])
    n = len(ids)
    H_sub = np.asarray(curves["H_sub"], dtype=float)
    sub_idx = np.asarray(curves["sub_idx"])
    max_mw = np.asarray(curves["max_mw"], dtype=float)
    T_flex = np.asarray(curves["T_flex"], dtype=float)

    portfolio = [{"site_id": ids[i], "mode": "skip", "mw": 0.0, "sla": 0.999,
                  "battery_mwh": 0.0} for i in range(n)]

    for s in range(H_sub.shape[0]):
        rows = [i for i in range(n) if int(sub_idx[i]) == s]
        if not rows:
            continue
        rows.sort(key=lambda i: (T_flex[i], ids[i]))
        H = H_sub[s]
        _v, mw = _opt_sub(H, rows, T_flex, max_mw)
        # map the exact prefix back to (mw, sla): sla from the cumulative position
        Rs = np.sort(H)
        cum = 0.0
        for i in rows:
            m = float(np.floor(mw.get(i, 0.0) * 100.0) / 100.0)
            if m < MIN_MW:
                continue
            cum += m
            k = int((Rs < cum - 1e-9).sum())
            sla = 0.9999 if k <= 0 else (0.999 if k <= 8 else 0.99)
            portfolio[i] = {"site_id": ids[i], "mode": "flex", "mw": m,
                            "sla": float(sla), "battery_mwh": 0.0}

    return repair_portfolio(curves, portfolio)
