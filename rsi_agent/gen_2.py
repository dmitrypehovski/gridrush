"""gen_2: per-substation EXACT optimiser (flex only).

Learned from gen_1 (and from the engine source):
  * battery is a trap: sim.engine adds the battery-covered MW to the substation
    load in the independent verifier (total += load_final), so any hour with a
    deficit is a violation. Battery therefore only "works" at mw <= min(H_sub),
    where flex@99.99% is already better (T_on = T_flex + 1). Zero batteries.
  * firm is dominated by flex@99.99%: same "never curtailed" physics (mw <=
    min headroom), same x1.25 premium, but T_firm is 18-36 vs T_flex 5-10.

Because substations share nothing but their own headroom, the score decomposes
into 8 independent sub-problems. For a given allocation order (= engine order:
(T_eff, id)), a site's value is
    0.10 * mult(sla) * mw * (36 - T) * avail(mw),  avail = 1 - #{h: cap_left[h] < mw}/8760,
which is maximised at a breakpoint of the residual headroom curve: mw =
sorted(cap_left)[k], k <= allowed curtailed hours of that SLA. So we do exact
coordinate ascent over (mw, sla) on those breakpoints, with restarts.
"""
from __future__ import annotations

import numpy as np

from loop.policy import REV_PER_MW_MONTH, repair_portfolio

HOR = 36.0
MIN_MW = 0.5
MULT = {0.9999: 1.25, 0.999: 1.00, 0.99: 0.80}
KMAX = {0.9999: 0, 0.999: 8, 0.99: 87}          # allowed curtailment hours / year
SLA_CHOICES = (0.9999, 0.999, 0.99)
COARSE_KS = (0, 1, 2, 3, 5, 8, 12, 20, 30, 45, 60, 75, 87)


def _sub_val(H, order, mw, sla, T, mx):
    """Exact substation net value ($M) for flex-only allocation, -1e9 if SLA broken."""
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
    """Residual headroom curve before site `upto` starts (engine-identical)."""
    cap = H.copy()
    for i in order:
        if i == upto:
            break
        m = min(mw.get(i, 0.0), mx[i])
        if m > 0:
            cap = cap - np.minimum(m, np.maximum(0.0, cap))
    return cap


def _candidates(H, order, mw, sla, T, mx, i):
    """Breakpoint MW candidates for site i, all SLA levels, plus skip."""
    R = _residual(H, order, mw, mx, i)
    Rs = np.sort(R)
    out = [(0.0, sla.get(i, 0.9999))]
    n = Rs.size
    seen = set()
    for lvl in SLA_CHOICES:
        kmax = min(KMAX[lvl], n - 1)
        ks = [k for k in COARSE_KS if k <= kmax]
        # also the k matching the site's current mw, +-1 for local polish
        cur = mw.get(i, 0.0)
        if cur > 0:
            kc = int(np.searchsorted(Rs, cur, side="left"))
            ks += [kc - 1, kc, kc + 1]
        for k in ks:
            if k < 0 or k > kmax:
                continue
            m = min(float(Rs[k]), mx[i])
            m = float(np.floor(m * 100.0) / 100.0)
            if m < MIN_MW:
                continue
            key = (round(m, 2), lvl)
            if key in seen:
                continue
            seen.add(key)
            out.append((m, float(lvl)))
    return out


def _optimize_sub(H, rows, T, mx, seed=0, n_sweeps=3):
    """Coordinate ascent on one substation. rows are sorted by allocation order."""
    rng = np.random.default_rng(seed)
    best_val, best = -1e9, None
    starts = [None, None, "random"]          # greedy, then jittered, then random
    for st in starts:
        mw, sla = {}, {}
        if st is None:                        # greedy by value along the order
            for i in rows:
                mw[i], sla[i] = 0.0, 0.9999
            for i in rows:
                bv, bc = 0.0, (0.0, 0.9999)
                for m, lvl in _candidates(H, rows, mw, sla, T, mx, i):
                    mw[i], sla[i] = m, lvl
                    v = _sub_val(H, rows, mw, sla, T, mx)
                    if v > bv:
                        bv, bc = v, (m, lvl)
                mw[i], sla[i] = bc
        elif st == "random":
            for i in rows:
                mw[i], sla[i] = 0.0, float(rng.choice(SLA_CHOICES))
            for i in rows:
                if rng.random() < 0.5:
                    # random breakpoint within the SLA budget
                    R = _residual(H, rows, mw, mx, i)
                    Rs = np.sort(R)
                    lvl = float(rng.choice(SLA_CHOICES))
                    k = int(rng.integers(0, min(KMAX[lvl], Rs.size - 1) + 1))
                    m = min(float(Rs[k]), mx[i])
                    if m >= MIN_MW:
                        mw[i], sla[i] = float(np.floor(m * 100.0) / 100.0), lvl
        else:                                 # jitter around greedy-ish init
            for i in rows:
                mw[i] = 0.0
                sla[i] = float(rng.choice(SLA_CHOICES))
        for _ in range(n_sweeps):
            improved = False
            for i in rows:
                cur_v = _sub_val(H, rows, mw, sla, T, mx)
                bv, bc = cur_v, (mw.get(i, 0.0), sla.get(i, 0.9999))
                for m, lvl in _candidates(H, rows, mw, sla, T, mx, i):
                    mw[i], sla[i] = m, lvl
                    v = _sub_val(H, rows, mw, sla, T, mx)
                    if v > bv + 1e-9:
                        bv, bc = v, (m, lvl)
                mw[i], sla[i] = bc
                if bv > cur_v + 1e-9:
                    improved = True
            if not improved:
                break
        v = _sub_val(H, rows, mw, sla, T, mx)
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
        # exact engine allocation order for flex
        rows.sort(key=lambda i: (T_flex[i], ids[i]))
        v, mw, sla = _optimize_sub(H_sub[s], rows, T_flex, max_mw, seed=s,
                                   n_sweeps=3)
        for i in rows:
            m = float(np.floor(mw.get(i, 0.0) * 100.0) / 100.0)
            if m < MIN_MW:
                continue
            portfolio[i] = {"site_id": ids[i], "mode": "flex", "mw": m,
                            "sla": float(sla.get(i, 0.9999)), "battery_mwh": 0.0}

    return repair_portfolio(curves, portfolio)
