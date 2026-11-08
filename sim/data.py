"""GRIDRUSH data layer.

Real: hourly 2025 demand / solar by US BA (EIA-930, public domain).
Synthetic (documented in sim/assumptions.md): substation capacities, loading factors,
candidate site sizes, interconnection timelines, geometry.

API (frozen, CONTRACT.md §4):
    load_region(region) -> dict
    make_sites(region, n_substations=8, per_substation=5, seed=7) -> list[dict]
"""
import functools
import os

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(_HERE), "data")
_HOURLY_CSV = os.path.join(DATA_DIR, "us_grid_hourly_2025.csv")
_SUMMARY_CSV = os.path.join(DATA_DIR, "us_grid_summary_2025.csv")

# region code -> BA code in the EIA-930 extract + human name + map bounding box
REGIONS = {
    "CAL": {"ba": "CISO", "name": "CAISO", "bbox": (-124.40, -114.10, 32.50, 42.00)},
    "TEX": {"ba": "ERCO", "name": "ERCOT", "bbox": (-106.60, -93.50, 25.80, 36.50)},
    "PJM": {"ba": "PJM", "name": "PJM", "bbox": (-84.80, -74.00, 37.00, 42.30)},
    "MISO": {"ba": "MISO", "name": "MISO", "bbox": (-97.50, -84.00, 37.00, 47.50)},
}

_ALIASES = {
    "CAL": "CAL", "CISO": "CAL", "CAISO": "CAL",
    "TEX": "TEX", "ERCO": "TEX", "ERCOT": "TEX",
    "PJM": "PJM", "MIDA": "PJM",
    "MISO": "MISO", "MIDW": "MISO",
}

N_HOURS = 8760

# Synthetic grid parameters (see sim/assumptions.md for sources/rationale).
SUB_CAP_RANGE_MW = (8.0, 60.0)      # substation capacity
LF_RANGE = (0.45, 0.82)             # raw loading factor (fraction of cap at p95 load)
MAX_MW_RANGE = (0.5, 10.0)          # per-site nameplate, hackathon scenario
GRID_MARGIN_FRAC = 0.02             # operating margin held on every substation
T_FIRM_RANGE = (18, 36)             # months, interconnection queue (MISO 18-36)
T_FLEX_RANGE = (5, 10)              # months, firm service step-up / ERCOT batch study
T_ON_EXTRA_RANGE = (1, 3)           # battery does NOT jump the queue: T_on = T_flex + 1..3


def _norm_region(region):
    key = str(region).strip().upper()
    if key not in _ALIASES:
        raise ValueError("unknown region %r (known: %s)" % (region, sorted(_ALIASES)))
    return _ALIASES[key]


@functools.lru_cache(maxsize=None)
def _load_all():
    """Load the hourly CSV once; return {ba: DataFrame sorted by local time}."""
    usecols = ["ba", "region", "local_time_end", "demand_mw", "solar_mw"]
    df = pd.read_csv(_HOURLY_CSV, usecols=usecols)
    df["local_time_end"] = pd.to_datetime(df["local_time_end"], format="%Y-%m-%d %H:%M")
    out = {}
    for ba, g in df.groupby("ba", sort=False):
        g = g.sort_values("local_time_end").reset_index(drop=True)
        out[str(ba)] = g
    return out


@functools.lru_cache(maxsize=None)
def _load_region_cached(region):
    code = _norm_region(region)
    meta = REGIONS[code]
    ba = meta["ba"]
    all_ba = _load_all()
    if ba not in all_ba:
        raise ValueError("BA %r for region %r missing from dataset" % (ba, code))
    g = all_ba[ba]
    if len(g) != N_HOURS:
        raise ValueError("BA %s has %d hours, expected %d" % (ba, len(g), N_HOURS))

    demand = pd.Series(g["demand_mw"].to_numpy(dtype=float))
    # short holes in the EIA-930 feed (incl. ERCOT's full 2025-12-05 NaN day) ->
    # linear time interpolation, then edge fill.
    demand = demand.interpolate(limit_direction="both").ffill().bfill()

    demand_mw = demand.to_numpy(dtype=float)
    # ---- repair corrupt single-hour demand spikes -------------------------
    # 7 rows in the extract are corrupted (e.g. CISO 2025-07-31 14:00 = 11,819 MW
    # between 29,881/29,886 MW). Rule: a point whose |delta| to BOTH neighbours is
    # > 8000 MW/h while the neighbours agree within 3000 MW/h is replaced by the
    # neighbour mean. Applied iteratively so adjacent corrupt rows unwind.
    for _ in range(4):
        prev_d = np.abs(demand_mw[1:-1] - demand_mw[:-2])
        next_d = np.abs(demand_mw[1:-1] - demand_mw[2:])
        neigh = np.abs(demand_mw[:-2] - demand_mw[2:])
        bad = (prev_d > 8000.0) & (next_d > 8000.0) & (neigh < 3000.0)
        if not bad.any():
            break
        mid = 0.5 * (demand_mw[:-2][bad] + demand_mw[2:][bad])
        demand_mw[1:-1][bad] = mid
    # solar in this extract is non-physical around the day boundary (negative /
    # spiky); it is only used for the dashboard stress-day chart, never for
    # capacity or stress-hours, and is clipped at 0.
    solar = pd.Series(g["solar_mw"].to_numpy(dtype=float)).fillna(0.0).clip(lower=0.0)
    solar_mw = solar.to_numpy(dtype=float)
    p95 = float(np.percentile(demand_mw, 95))
    u = demand_mw / p95

    local_time = g["local_time_end"]
    peak_idx = int(np.argmax(demand_mw))
    peak_ts = local_time.iloc[peak_idx]
    stress_date = peak_ts.strftime("%Y-%m-%d")
    day_mask = (local_time.dt.strftime("%Y-%m-%d") == stress_date).to_numpy()
    day_idx = np.flatnonzero(day_mask)
    # keep chronological order inside the stress day
    day_idx = day_idx[np.argsort(local_time.iloc[day_idx].to_numpy())]
    # if the peak day is incomplete, fall back to a full 24h window around the peak
    if len(day_idx) != 24:
        start = max(0, min(N_HOURS - 24, peak_idx - 12))
        day_idx = np.arange(start, start + 24)
        stress_date = local_time.iloc[day_idx[0]].strftime("%Y-%m-%d")

    month_hours = {}
    months = local_time.dt.month.to_numpy()
    for m in range(1, 13):
        month_hours[m] = np.flatnonzero(months == m).astype(np.int64)

    u_max = float(u.max())
    # Existing load alone must never violate the substation limit (empty portfolio =>
    # zero violations): lf * u[h] <= 1 - margin  =>  lf <= (1 - margin) / u_max.
    lf_cap = (1.0 - GRID_MARGIN_FRAC) / u_max
    lf_lo, lf_hi = LF_RANGE
    lf_max = min(lf_hi, lf_cap)
    if lf_max < lf_lo + 0.05:  # pathological region; keep a usable spread
        lf_lo, lf_max = 0.30, lf_cap

    return {
        "region": code,
        "ba": ba,
        "eia_region": str(g["region"].iloc[0]),   # EIA-930 region column: CAL/TEX/MIDA/MIDW
        "name": meta["name"],
        "bbox": meta["bbox"],
        "hours": np.arange(N_HOURS, dtype=np.int64),
        "demand_mw": demand_mw,
        "solar_mw": solar_mw,
        "u": u,
        "p95_mw": p95,
        "u_max": u_max,
        "lf_range": (float(lf_lo), float(lf_max)),
        "stress_day": stress_date,
        "month_hours": month_hours,
        "local_time": local_time.to_numpy(),
        "stress_idx": day_idx.astype(np.int64),
        "peak_mw": float(demand_mw.max()),
        "peak_local": peak_ts.strftime("%Y-%m-%d %H:%M"),
        "peak_utc": pd.to_datetime(
            all_ba[ba]["local_time_end"].iloc[peak_idx]
        ).isoformat(),
    }


def load_region(region: str) -> dict:
    """Real 2025 hourly shape for one region (CAL/TEX/PJM/MISO)."""
    return dict(_load_region_cached(region))


def make_sites(region: str, n_substations: int = 8, per_substation: int = 5,
               seed: int = 7) -> list:
    """Deterministic synthetic portfolio of candidate sites for a region.

    Same seed => same capacities/timelines/offsets in every region; only the map
    coordinates follow the region bounding box. lf is mapped into the feasible
    band [LF_RANGE.lo, min(LF_RANGE.hi, (1-margin)/u_max)] so the existing load
    never breaches the substation limit on its own.
    """
    # Real-data override: data/sites_<region>_real.json is built from PG&E's public GRIP
    # portal by sim/real_sites.py (real substations, ratings, 2026 loadings, coordinates).
    # Enable with GRIDRUSH_SITES=real; the schema matches exactly what this function returns.
    import os as _os
    if _os.environ.get("GRIDRUSH_SITES") == "real":
        real_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
                                  "data", f"sites_{region}_real.json")
        if _os.path.exists(real_path):
            import json as _json
            with open(real_path, encoding="utf-8") as _f:
                _d = _json.load(_f)
            return _d["sites"]

    reg = load_region(region)
    lf_lo, lf_hi = reg["lf_range"]
    bbox = reg["bbox"]
    # Raw draws are region independent (same site "personality" across regions);
    # only the final lf scaling and the x/y jitter depend on the region.
    rng = np.random.RandomState(seed)
    caps = rng.uniform(SUB_CAP_RANGE_MW[0], SUB_CAP_RANGE_MW[1], n_substations)
    lf_raw = rng.uniform(0.0, 1.0, (n_substations, per_substation))
    max_mw = rng.uniform(MAX_MW_RANGE[0], MAX_MW_RANGE[1],
                         (n_substations, per_substation))
    max_mw = np.round(max_mw * 2.0) / 2.0  # 0.5 MW granularity
    t_firm = rng.randint(T_FIRM_RANGE[0], T_FIRM_RANGE[1] + 1,
                         (n_substations, per_substation))
    t_flex = rng.randint(T_FLEX_RANGE[0], T_FLEX_RANGE[1] + 1,
                         (n_substations, per_substation))
    t_on = t_flex + rng.randint(T_ON_EXTRA_RANGE[0], T_ON_EXTRA_RANGE[1] + 1,
                                (n_substations, per_substation))
    fiber = rng.rand(n_substations, per_substation) < 0.7
    permit = rng.randint(20, 121, (n_substations, per_substation))
    sub_x = rng.uniform(bbox[0], bbox[1], n_substations)
    sub_y = rng.uniform(bbox[2], bbox[3], n_substations)
    jx = rng.uniform(-0.22, 0.22, (n_substations, per_substation))
    jy = rng.uniform(-0.22, 0.22, (n_substations, per_substation))

    lf = lf_lo + lf_raw * (lf_hi - lf_lo)
    sites = []
    for s in range(n_substations):
        for k in range(per_substation):
            sites.append({
                "id": "S%02d-%d" % (s + 1, k + 1),
                "substation": "S%02d" % (s + 1),
                "cap_mw": round(float(caps[s]), 1),
                "lf": round(float(lf[s, k]), 3),
                "max_mw": round(float(max_mw[s, k]), 1),
                "T_firm": int(t_firm[s, k]),
                "T_flex": int(t_flex[s, k]),
                "T_on": int(t_on[s, k]),
                "fiber": bool(fiber[s, k]),
                "permit_days": int(permit[s, k]),
                "x": round(float(sub_x[s] + jx[s, k]), 3),
                "y": round(float(sub_y[s] + jy[s, k]), 3),
            })
    return sites


def write_sites_json(path: str, region: str = "CAL", **kwargs) -> list:
    """Convenience writer for data/sites.json (Lead owns data/, this is opt-in)."""
    import json
    sites = make_sites(region, **kwargs)
    payload = {"region": _norm_region(region), "seed": kwargs.get("seed", 7),
               "n_sites": len(sites), "sites": sites}
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1)
    return sites
