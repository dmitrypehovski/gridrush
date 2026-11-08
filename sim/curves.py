"""GRIDRUSH site curves -- single source of truth for e/H used by evaluate() and the loop.

CONTRACT.md §2:
    e[S,h] = lf[S] * cap_mw[S] * u[h]
    H[i,h] = cap_mw[S(i)] - e[S(i),h] - margin*cap_mw[S(i)]      (margin = 2%)

`site_curves(region)` is cached: sim/engine.py, sim/baselines.py, sim/run.py and
loop/ all read the same arrays, so a portfolio built by the loop is scored on
exactly the physics it was built for.

API (added at Lead's request, additive to CONTRACT §4 -- evaluate() unchanged):
    site_curves(region) -> dict with arrays:
      ids      (n,)      list[str]      site ids, index order used everywhere
      sub_idx  (n,)      int            substation index of each site
      sub_ids  (S,)      list[str]      substation ids
      max_mw   (n,)      float          per-site nameplate ceiling
      cap_mw   (S,)      float          substation capacity
      lf       (S,)      float          substation loading factor
      e        (S,8760)  float          existing substation load
      H        (n,8760)  float          free headroom per site (same row per substation)
      Hmax_mw  (n,)      float          max_h H[i,h]
      Hmin_mw  (n,)      float          min_h H[i,h]  (firm budget w/o curtailment)
      T_firm/T_flex/T_on (n,) int       months to energize per mode
      fiber    (n,)      bool
      permit_days (n,)   int
      stress_hours (n,)  int            hours where H[i,h] < max_mw[i]
      u        (8760,)   float          normalised demand shape
      margin_frac float
"""
import functools

import numpy as np

try:  # package import (sim.engine, loop):  from sim.curves import site_curves
    from .data import GRID_MARGIN_FRAC, load_region, make_sites
except ImportError:  # direct script / flat sys.path: from curves import site_curves
    from data import GRID_MARGIN_FRAC, load_region, make_sites


@functools.lru_cache(maxsize=None)
def _site_curves_cached(region):
    reg = load_region(region)
    sites = make_sites(region)
    n = len(sites)
    sub_names = sorted({s["substation"] for s in sites})
    sub_pos = {name: k for k, name in enumerate(sub_names)}
    S = len(sub_names)

    u = np.asarray(reg["u"], dtype=np.float64)
    cap = np.zeros(S, dtype=np.float64)
    lf = np.zeros(S, dtype=np.float64)
    e = np.zeros((S, u.size), dtype=np.float64)

    ids = [s["id"] for s in sites]
    sub_idx = np.zeros(n, dtype=np.int64)
    max_mw = np.zeros(n, dtype=np.float64)
    T_firm = np.zeros(n, dtype=np.int64)
    T_flex = np.zeros(n, dtype=np.int64)
    T_on = np.zeros(n, dtype=np.int64)
    fiber = np.zeros(n, dtype=bool)
    permit = np.zeros(n, dtype=np.int64)

    for k, s in enumerate(sites):
        j = sub_pos[s["substation"]]
        sub_idx[k] = j
        cap[j] = s["cap_mw"]
        lf[j] = s["lf"]
        max_mw[k] = s["max_mw"]
        T_firm[k] = s["T_firm"]
        T_flex[k] = s["T_flex"]
        T_on[k] = s["T_on"]
        fiber[k] = s["fiber"]
        permit[k] = s["permit_days"]

    e = lf[:, None] * cap[:, None] * u[None, :]
    H_sub = cap[:, None] - e - GRID_MARGIN_FRAC * cap[:, None]
    H = H_sub[sub_idx, :].copy()
    Hmax = H.max(axis=1)
    Hmin = H.min(axis=1)
    # Grid stress hours: hours in the tightest 2% of the regional demand shape
    # (u >= p98(u)). That is the "flex-worthy" window measured on the real 2025
    # EIA-930 data (159-177 h/BA/year in the data spike); solar is never used here.
    # Computed from the demand shape, not from nameplate vs headroom, so it stays a
    # property of the interconnection window and not of a particular portfolio.
    stress_hours = np.full(n, int((u >= np.percentile(u, 98)).sum()), dtype=np.int64)

    return {
        "region": reg["region"],
        "ids": ids,
        "sub_idx": sub_idx,
        "sub_ids": sub_names,
        "max_mw": max_mw,
        "cap_mw": cap,
        "lf": lf,
        "e": e,
        "H": H,
        "H_sub": H_sub,
        "Hmax_mw": Hmax,
        "Hmin_mw": Hmin,
        "T_firm": T_firm,
        "T_flex": T_flex,
        "T_on": T_on,
        "fiber": fiber,
        "permit_days": permit,
        "stress_hours": stress_hours,
        "u": u,
        "margin_frac": GRID_MARGIN_FRAC,
        "n_hours": int(u.size),
        "n_sites": n,
        "n_substations": S,
    }


def site_curves(region: str) -> dict:
    """Cached curves dict for a region (see module docstring). Do not mutate."""
    return _site_curves_cached(region)


def index_of(curves) -> dict:
    """site_id -> array index mapping (cached per curves object id)."""
    return {sid: i for i, sid in enumerate(curves["ids"])}
