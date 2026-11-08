"""gen_6: gen_5 exact DP + repair-friendly MW (final).

gen_4 bug, worth recording: the DP's candidate prefixes were only the headroom
breakpoints sorted(H_sub)[k]. On a substation whose min headroom (10.5 MW) is
larger than the first site's nameplate max_mw (5.5 MW) there is no candidate at
5.5, so the DP could not allocate anything at all and returned the empty
portfolio (score 115 -> a hard lesson: 115 was the "allocate nothing" score).

Fix: prefixes must also include constraint boundaries — the cumulative nameplate
prefix sums, and breakpoint values relative to them (a + sorted(H)[k]). Keep all
prefixes with <= 87 curtailed hours (still SLA 99.0% or better).

Model facts (verified against sim.engine, see gen_2/gen_3 docstrings):
  avail_i = 1 - #{h : H_sub[h] < P_i}/8760 with P_i the cumulative MW prefix in
  engine order (T_eff, id); best compatible SLA price gives
  k=0 -> x1.25, k<=8 -> x1.00, k<=87 -> x0.80. Substations independent -> DP is
  the exact optimum of the whole flex-only space.
"""
from __future__ import annotations

import numpy as np

from loop.policy import REV_PER_MW_MONTH, repair_portfolio

HOR = 36.0
MIN_MW = 0.5
HOURS = 8760


def _prefix_set(Rs, mx_order):
    kmax = min(87, Rs.size - 1)
    base = [0.0] + [float(Rs[k]) for k in range(0, kmax + 1)]
    partial = []
    acc = 0.0
    for m in mx_order:
        acc += float(m)
        partial.append(acc)
    extra = []
    for a in [0.0] + partial:
        for k in (0, 8, 87):
            if k <= kmax:
                extra.append(a + float(Rs[k]))
    Q = base + partial + extra
    Q = [q for q in Q if q <= float(Rs[kmax]) + 1e-9]
    # NB: no rounding here! prefix must stay <= Rs[k] to keep k=#{H<prefix} exact
    return np.unique(np.asarray(Q, dtype=float))


def _opt_sub(H, order, T, mx):
    Rs = np.sort(H)
    Q = np.array(_prefix_set(Rs, [mx[i] for i in order]))
    n = Q.size
    kk = np.searchsorted(Rs, Q, side="left").astype(int)
    avail = 1.0 - kk / HOURS
    mult = np.where(kk <= 0, 1.25, np.where(kk <= 8, 1.00, np.where(kk <= 87, 0.80, 0.0)))

    NEG = -1e18
    dp = np.full(n, NEG)
    dp[0] = 0.0
    parents = []
    for i in order:
        c = REV_PER_MW_MONTH * max(0.0, HOR - T[i])
        w = c * mult * avail             # value per MW at prefix level l
        new = dp.copy()                  # "skip this site" keeps the prefix
        par = np.arange(n)
        for l in range(1, n):
            if w[l] <= 0.0:
                continue
            lo = max(0, int(np.searchsorted(Q, Q[l] - mx[i], side="left")))
            # site nameplate floor: mw_i >= MIN_MW (evaluate() zeroes smaller items)
            hi = int(np.searchsorted(Q, Q[l] - MIN_MW, side="right"))
            hi = min(hi, l)
            if lo >= hi:
                continue
            cand = dp[lo:hi] + w[l] * (Q[l] - Q[lo:hi])
            a = int(np.argmax(cand))
            k = lo + a
            v = float(cand[a])
            if v > new[l] + 1e-12:
                new[l], par[l] = v, k
        dp = new
        parents.append(par)

    j = int(np.argmax(dp))
    best_val = float(dp[j])
    mw = {i: 0.0 for i in order}
    for idx in range(len(order) - 1, -1, -1):
        p = int(parents[idx][j])
        mw[order[idx]] = float(Q[j] - Q[p])
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

    for item in portfolio:
        if item["mw"] > 0.0:
            item["mw"] = round(item["mw"] + 0.0049, 4)
    return repair_portfolio(curves, portfolio)
