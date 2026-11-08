"""gen_8: exact per-substation DP over the TRUE reachable prefix set (no lattice loss).

Why gen_6 was not exact
-----------------------
gen_6 solved the right problem but on a *candidate lattice* Q = {Rs[k]} u
{partial nameplate sums} u {partial + Rs[k]}.  The DP value of site i depends only
on its own cumulative prefix p (avail = 1 - #{H < p}/8760), so for a fixed previous
prefix the best mw of a site is attained at a *tier upper bound*:
    p + max_mw, or Rs[0]-eps, Rs[8]-eps, Rs[87]-eps (or p+MIN_MW if a bound is
    below the 0.5 MW floor).
Therefore the reachable optimal prefix set is closed under "breakpoint + nameplate
chain" (p -> p + max_mw with p a breakpoint), which gen_6's Q did not contain.
gen_8 carries the reachable set explicitly through the DP (<= ~600 states/sub), so
the result is the exact optimum of the flex-only space.

Second loss in gen_6: floor(x*100)/100 + 0.0049 -> every site lost up to ~0.01 MW,
and repair_portfolio floors to 0.01 again.  At ~3.1 $M/MW of value this is real
money (measured: DP predicted 280.276 vs 279.908 delivered).  gen_8 keeps 4-dec
precision, sits eps=1e-3 MW *below* every tier boundary (so the engine's
hour-count can only come out lower than our estimate) and replaces
repair_portfolio with an exact engine replica (same float sequence) plus a shave
loop.  No rounding offset needed.
"""
from __future__ import annotations

import numpy as np

from loop.policy import REV_PER_MW_MONTH

HOR = 36.0
MIN_MW = 0.5
HOURS = 8760
EPS = 1e-3          # sit this far below a tier boundary (safe vs float rounding)
NEG = -1e18


def _tier(k: int) -> float:
    return 1.25 if k <= 0 else (1.00 if k <= 8 else 0.80)


def _sla_for_k(k: int) -> float:
    return 0.9999 if k <= 0 else (0.999 if k <= 8 else 0.99)


def _sim_avail(H_sub, mws):
    """Exact replica of the engine's flex allocation (no firm, no battery)."""
    cap_left = np.asarray(H_sub, dtype=float).copy()
    out = []
    for mw in mws:
        load = np.minimum(mw, np.maximum(0.0, cap_left))
        deficit = np.clip(mw - load, 0.0, None)
        out.append(1.0 - float((deficit > 1e-9).sum()) / HOURS)
        cap_left = cap_left - load
    return out


def _opt_sub(H, order, T, mx):
    """Exact DP.  Returns (value, {site_index: mw})."""
    Rs = np.sort(np.asarray(H, dtype=float))
    kmax = min(87, Rs.size - 1)
    top = float(Rs[kmax]) - EPS                     # nothing above this is admissible
    bounds = []
    for k in (0, 8, 87):
        if k <= kmax:
            b = float(Rs[k]) - EPS
            if b >= MIN_MW:
                bounds.append(b)

    states = {0.0: 0.0}
    levels = []                                     # one parent map per site
    for i in order:
        c = REV_PER_MW_MONTH * max(0.0, HOR - float(T[i]))
        mxi = float(mx[i])
        new, par = {}, {}
        for p, v in states.items():
            cands = [p, p + MIN_MW]                 # skip / smallest legal block
            if p + mxi <= top + 1e-12:
                cands.append(p + mxi)
            for b in bounds:
                if b >= p + MIN_MW - 1e-9 and b <= p + mxi + 1e-9:
                    cands.append(b)
            for q in cands:
                if q > top + 1e-12:
                    continue
                mw = q - p
                if mw > 0.0 and mw < MIN_MW - 1e-12:
                    continue
                if mw > mxi + 1e-12:
                    continue
                if q <= p:                              # mw == 0 -> no value
                    if v > new.get(q, NEG) + 1e-12:
                        new[q], par[q] = v, (p, 0.0)
                    continue
                k = int(np.searchsorted(Rs, q, side="left"))   # #{H < q}
                val = c * _tier(k) * (1.0 - k / HOURS) * mw
                v2 = v + val
                if v2 > new.get(q, NEG) + 1e-12:
                    new[q], par[q] = v2, (p, mw)
        states = new
        levels.append(par)

    j = max(states, key=lambda q: states[q])
    best = float(states[j])
    mw = {i: 0.0 for i in order}
    for idx in range(len(order) - 1, -1, -1):
        p, m = levels[idx][j]
        mw[order[idx]] = float(m)
        j = p
    return best, mw


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
        _v, mw = _opt_sub(H_sub[s], rows, T_flex, max_mw)
        mws = [round(float(mw.get(i, 0.0)), 4) for i in rows]
        mws = [m if m >= MIN_MW else 0.0 for m in mws]
        H = H_sub[s]
        for _attempt in range(40):
            avails = _sim_avail(H, mws)
            changed = False
            for k, i in enumerate(rows):
                if mws[k] <= 0.0:
                    continue
                cum = float(sum(mws[: k + 1]))
                kk = int(np.searchsorted(np.sort(H), cum, side="left"))
                sla = _sla_for_k(kk)
                if avails[k] < sla - 1e-12:         # be safe, shave 1 mm
                    mws[k] = round(max(0.0, mws[k] - 0.001), 4)
                    changed = True
            if not changed:
                break
        for k, i in enumerate(rows):
            if mws[k] <= 0.0:
                continue
            cum = float(sum(mws[: k + 1]))
            kk = int(np.searchsorted(np.sort(H), cum, side="left"))
            portfolio[i] = {"site_id": ids[i], "mode": "flex",
                            "mw": float(mws[k]), "sla": float(_sla_for_k(kk)),
                            "battery_mwh": 0.0}
    return portfolio
