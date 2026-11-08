"""gen_3: TIER construction per substation + coordinate ascent.

gen_2 (exact coordinate ascent from gen_1's greedy) hit a *coordination* local
optimum: e.g. on S04 one site held 3.49 MW at 99.99% and another 5.99 MW at 99%;
moving 1 MW from the 99% site to a fresh site at 99.99% is a strict improvement
(+~1.3 $M) but needs a 2-site move, so single-site ascent never finds it.

Insight: the headroom curve defines three *tiers* of capacity, each with its own
price multiplier:
    tier A: MW served in every hour      -> SLA 99.99%, x1.25  (capacity = min H)
    tier B: MW served except <= 8 h/yr   -> SLA 99.9%,  x1.00  (capacity = 8th lowest H)
    tier C: MW served except <= 87 h/yr  -> SLA 99.0%,  x0.80  (capacity = 87th lowest H)
Within a substation, MW in a higher tier is strictly more valuable, and the tier
capacity should go to the sites that energize earliest (T_flex). So: fill tier A
across sites in T order (respecting max_mw), then tier B, then tier C, one tier
per site; then coordinate-ascent polish. We try several tier-boundary choices
(kA, kB, kC) and keep the best per substation.
"""
from __future__ import annotations

import numpy as np

from loop.policy import REV_PER_MW_MONTH, repair_portfolio

HOR = 36.0
MIN_MW = 0.5
MULT = {0.9999: 1.25, 0.999: 1.00, 0.99: 0.80}
KMAX = {0.9999: 0, 0.999: 8, 0.99: 87}
SLA_CHOICES = (0.9999, 0.999, 0.99)
COARSE_KS = (0, 1, 2, 3, 5, 8, 12, 20, 30, 45, 60, 75, 87)


def _sub_val(H, order, mw, sla, T, mx):
    cap = H.copy()
    tot = 0.0
    for i in order:
        m = mw.get(i, 0.0)
        if m <= 0.0:
            continue
        m = min(m, mx[i])
        load = np.minimum(m, np.maximum(0.0, cap))
        k = int(((m - load) > 1e-9).sum())
        av = 1.0 - k / 8760.0
        if av < sla[i] - 1e-9:
            return -1e9
        tot += REV_PER_MW_MONTH * MULT[sla[i]] * m * (HOR - T[i]) * av
        cap = cap - load
    return tot


def _residual(H, order, mw, mx, upto):
    cap = H.copy()
    for i in order:
        if i == upto:
            break
        m = min(mw.get(i, 0.0), mx[i])
        if m > 0:
            cap = cap - np.minimum(m, np.maximum(0.0, cap))
    return cap


def _candidates(H, order, mw, sla, mx, i):
    R = _residual(H, order, mw, mx, i)
    Rs = np.sort(R)
    out = [(0.0, sla.get(i, 0.9999))]
    n = Rs.size
    seen = set()
    for lvl in SLA_CHOICES:
        kmax = min(KMAX[lvl], n - 1)
        ks = [k for k in COARSE_KS if k <= kmax]
        cur = mw.get(i, 0.0)
        if cur > 0:
            kc = int(np.searchsorted(Rs, cur, side="left"))
            ks += [kc - 1, kc, kc + 1]
        for k in ks:
            if k < 0 or k > kmax:
                continue
            m = float(np.floor(min(float(Rs[k]), mx[i]) * 100.0) / 100.0)
            if m < MIN_MW:
                continue
            key = (round(m, 2), lvl)
            if key in seen:
                continue
            seen.add(key)
            out.append((m, float(lvl)))
    return out


def _ascent(H, order, mw, sla, T, mx, n_sweeps=3):
    for _ in range(n_sweeps):
        improved = False
        for i in order:
            cur_v = _sub_val(H, order, mw, sla, T, mx)
            bv, bc = cur_v, (mw.get(i, 0.0), sla.get(i, 0.9999))
            for m, lvl in _candidates(H, order, mw, sla, mx, i):
                mw[i], sla[i] = m, lvl
                v = _sub_val(H, order, mw, sla, T, mx)
                if v > bv + 1e-9:
                    bv, bc = v, (m, lvl)
            mw[i], sla[i] = bc
            if bv > cur_v + 1e-9:
                improved = True
        if not improved:
            break
    return mw, sla


def _tier_fill(H, order, T, mx, kA, kB, kC):
    Rs = np.sort(H)
    n = Rs.size
    cum = [float(Rs[min(kA, n - 1)]), float(Rs[min(kB, n - 1)]),
           float(Rs[min(kC, n - 1)])]
    # keep boundaries monotone
    for j in range(1, 3):
        cum[j] = max(cum[j], cum[j - 1])
    mw, sla = {}, {}
    prev = 0.0
    ptr = 0
    for lvl, c in zip(SLA_CHOICES, cum):
        inc = max(0.0, c - prev)
        prev = max(prev, c)
        while inc >= MIN_MW and ptr < len(order):
            i = order[ptr]
            take = float(np.floor(min(mx[i], inc) * 100.0) / 100.0)
            ptr += 1
            if take < MIN_MW:
                continue
            mw[i], sla[i] = take, float(lvl)
            inc -= take
    return mw, sla


def _optimize_sub(H, order, T, mx):
    best_val, best = -1e9, None
    starts = []
    for kA in (0, 1, 2):
        for kB in (4, 8, 12, 20):
            for kC in (60, 87):
                mw, sla = _tier_fill(H, order, T, mx, kA, kB, kC)
                starts.append((mw, sla))
    # plus the "one big site" starts, in case a substation with few sites prefers it
    for kC in (0, 8, 87):
        mw, sla = _tier_fill(H, order, T, mx, 0, 0, kC)
        starts.append((mw, sla))
    for mw0, sla0 in starts:
        mw, sla = dict(mw0), dict(sla0)
        v0 = _sub_val(H, order, mw, sla, T, mx)
        if v0 < best_val - 1e-9:
            # still polish promising-ish starts only (cheap)
            pass
        mw, sla = _ascent(H, order, mw, sla, T, mx, n_sweeps=3)
        v = _sub_val(H, order, mw, sla, T, mx)
        if v > best_val:
            best_val, best = v, (dict(mw), dict(sla))
    return best_val, best[0], best[1]


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
        _v, mw, sla = _optimize_sub(H_sub[s], rows, T_flex, max_mw)
        for i in rows:
            m = float(np.floor(mw.get(i, 0.0) * 100.0) / 100.0)
            if m < MIN_MW:
                continue
            portfolio[i] = {"site_id": ids[i], "mode": "flex", "mw": m,
                            "sla": float(sla.get(i, 0.9999)), "battery_mwh": 0.0}

    return repair_portfolio(curves, portfolio)
