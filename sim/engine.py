"""GRIDRUSH evaluator -- deterministic, vectorised numpy, CONTRACT.md §2/§4.

    evaluate(region, portfolio) -> dict

Portfolio item (CONTRACT §4):
    {"site_id": "S03-2", "mode": "skip|firm|flex|battery", "mw": 4.5,
     "sla": 0.999|0.99, "battery_mwh": 0.0}

The grid physics comes from sim/curves.py (e, H) so the loop optimises exactly the
model that is scored here. The verifier at the end is independent of the
allocation logic: it recomputes per-substation load hour-by-hour from e + every
site's actual load and counts any excursion above cap - margin. Firm MW is never
curtailed (that is what firm means), so an over-subscribed substation shows up as
violations_mwh > 0 instead of being silently hidden.

Timing model (months to energize): firm -> T_firm (18-36), flex -> T_flex (5-10),
battery -> T_on (4-7, onsite battery is the fast path).
"""
import numpy as np

try:
    from .curves import site_curves
except ImportError:  # flat sys.path (python3 sim/engine.py, tests)
    from curves import site_curves

HORIZON_MONTHS = 36
DAYS = 365
HOURS_PER_YEAR = 24 * DAYS

# --- synthetic economics (sim/assumptions.md) -------------------------------
MARGIN_USD_PER_MW_MONTH = 0.10      # $M per MW-month of compute ($1.2M/MW-year)
USD_PER_MWH = MARGIN_USD_PER_MW_MONTH / 730.0   # $M per MWh  (730 h / month)
SLA_PENALTY_MULT = 5.0              # penalty = 5x margin per curtailed MWh over budget
CAPEX_BATTERY_POWER = 0.35          # $M / MW   (power conversion)
CAPEX_BATTERY_ENERGY = 0.25         # $M / MWh  (cells)
BATTERY_DOD = 0.90                  # usable depth of discharge
BATTERY_CYCLES_PER_DAY = 1.0        # one full cycle per day (8760/365 representative)
MIN_MW = 0.5
SLA_LEVELS = (0.9999, 0.999, 0.99)
# SLA is a priced choice (Lead addendum 2026-11-08, from the stage):
#   0.9999 -> 0.876 h/yr curtailment budget, revenue multiplier 1.25 (premium for 6 nines)
#   0.999  -> 8.76 h/yr, 1.00
#   0.99   -> 87.6 h/yr, 0.80
# net_value uses revenue-weighted MW-months; delivered_mwmonths stays unweighted.
SLA_REV_MULT = {0.9999: 1.25, 0.999: 1.00, 0.99: 0.80}
SLA_BUDGET_HOURS = {0.9999: 0.876, 0.999: 8.76, 0.99: 87.6}
MODES = ("skip", "firm", "flex", "battery")


def _battery_cover(deficit: np.ndarray, energy_mwh: float) -> np.ndarray:
    """Energy-limited battery cover of hourly deficits, worst hours first.

    deficit: (n_hours,) shortfall in MW at each curtailment hour (0 elsewhere).
    energy_mwh: usable energy available per day (one daily cycle).
    Returns covered MW per hour; the battery dispatches to the deepest deficits
    first inside each day, then the remaining deficit is curtailed.
    """
    if energy_mwh <= 0.0 or deficit.size == 0:
        return np.zeros_like(deficit)
    n_days = deficit.size // 24
    if n_days * 24 != deficit.size:  # defensive: pad to whole days
        pad = (-deficit.size) % 24
        deficit = np.concatenate([deficit, np.zeros(pad)])
        n_days = deficit.size // 24
    d = deficit.reshape(n_days, 24)
    order = np.argsort(-d, axis=1, kind="stable")
    d_sorted = np.take_along_axis(d, order, axis=1)
    cum = np.cumsum(d_sorted, axis=1)
    before = cum - d_sorted
    covered_sorted = np.minimum(d_sorted, np.maximum(0.0, energy_mwh - before))
    covered = np.empty_like(covered_sorted)
    np.put_along_axis(covered, order, covered_sorted, axis=1)
    out = covered.reshape(-1)
    if out.size != deficit.size:
        out = out[: deficit.size]
    return out


def _empty_result(region):
    return {
        "region": region,
        "score": 0.0,
        "delivered_mwmonths": 0.0,
        "rev_weighted_mwmonths": 0.0,
        "mw_at_month12": 0.0,
        "net_value_musd": 0.0,
        "violations_mwh": 0.0,
        "sla_breach_mwh": 0.0,
        "capex_musd": 0.0,
        "avail_by_site": {},
        "monthly_mw": [0.0] * HORIZON_MONTHS,
        "modes": {},
        "curtail_hours_by_site": {},
        "curtail_mwh_by_site": {},
        "energize_month_by_site": {},
    }


def evaluate(region: str, portfolio: list) -> dict:
    """Score a portfolio against the frozen model. See module docstring."""
    c = site_curves(region)
    ids = c["ids"]
    index = {sid: i for i, sid in enumerate(ids)}
    n = c["n_sites"]
    S = c["n_substations"]

    # ---- 1. parse portfolio into arrays ------------------------------------
    mw = np.zeros(n)
    bat_mwh = np.zeros(n)
    sla = np.full(n, 0.999)
    mode_req = ["skip"] * n
    for item in portfolio or []:
        i = index.get(str(item.get("site_id", "")))
        if i is None:
            continue
        m = str(item.get("mode", "skip")).lower()
        if m not in MODES or m == "skip":
            continue
        try:
            mw_i = float(item.get("mw", 0.0) or 0.0)
        except (TypeError, ValueError):
            mw_i = 0.0
        if not np.isfinite(mw_i) or mw_i <= 0.0:
            continue
        try:
            bat_i = float(item.get("battery_mwh", 0.0) or 0.0)
        except (TypeError, ValueError):
            bat_i = 0.0
        bat_i = bat_i if np.isfinite(bat_i) and bat_i > 0 else 0.0
        try:
            sla_i = float(item.get("sla", 0.999))
        except (TypeError, ValueError):
            sla_i = 0.999
        sla_i = min(SLA_LEVELS, key=lambda s: abs(s - sla_i))
        mode_req[i] = m
        mw[i] = mw_i
        bat_mwh[i] = bat_i
        sla[i] = sla_i

    # clamp to physical ceiling: nameplate and best-hour headroom
    mw = np.minimum(mw, c["max_mw"])
    mw = np.minimum(mw, np.maximum(0.0, c["Hmax_mw"]))
    mw = np.where(mw >= MIN_MW - 1e-12, mw, 0.0)

    mode = [m if mw[i] > 0.0 else "skip" for i, m in enumerate(mode_req)]
    active = np.array([m != "skip" for m in mode], dtype=bool)
    T_eff = np.zeros(n, dtype=np.int64)
    for i in np.flatnonzero(active):
        m = mode[i]
        if m == "firm":
            T_eff[i] = c["T_firm"][i]
        elif m == "flex":
            T_eff[i] = c["T_flex"][i]
        else:
            T_eff[i] = c["T_on"][i]

    # ---- 2. allocate substation capacity hour-by-hour ---------------------
    cap = c["cap_mw"]
    e = c["e"]
    limit = cap * (1.0 - c["margin_frac"])          # cap - margin
    firm_total = np.zeros(S)
    for i in np.flatnonzero(active):
        if mode[i] == "firm":
            firm_total[c["sub_idx"][i]] += mw[i]
    cap_left = (c["H_sub"] - firm_total[:, None]).copy()   # remaining headroom (S, H)

    load = np.zeros((n, c["n_hours"]))
    flex_order = sorted(
        (i for i in np.flatnonzero(active) if mode[i] in ("flex", "battery")),
        key=lambda i: (int(T_eff[i]), ids[i]),
    )
    for i in flex_order:
        s = c["sub_idx"][i]
        li = np.minimum(mw[i], np.maximum(0.0, cap_left[s]))
        load[i] = li
        cap_left[s] = cap_left[s] - li

    firm_mask = np.array([active[i] and mode[i] == "firm" for i in range(n)])
    load[firm_mask] = mw[firm_mask][:, None]

    # ---- 3. battery cover (per-site, daily energy budget) ------------------
    deficit = np.zeros((n, c["n_hours"]))
    deficit[~firm_mask] = mw[~firm_mask][:, None] - load[~firm_mask]
    deficit = np.clip(deficit, 0.0, None)
    covered = np.zeros_like(load)
    for i in np.flatnonzero(active):
        if mode[i] == "battery" and bat_mwh[i] > 0.0:
            daily = BATTERY_DOD * BATTERY_CYCLES_PER_DAY * bat_mwh[i]
            covered[i] = _battery_cover(deficit[i], daily)
    load_final = load + covered
    deficit_final = np.clip(mw[:, None] - load_final, 0.0, None)

    # ---- 4. independent verifier (hour-by-hour, not policy aware) ----------
    # Grid draw per site is `load` (battery discharge serves the site behind the
    # meter and does not add to the substation draw). `load_final` is what the
    # site actually serves and only drives availability.
    total = e.copy()
    for i in np.flatnonzero(active):
        total[c["sub_idx"][i]] += load[i]
    violation_h = np.clip(total - limit[:, None] - 1e-6, 0.0, None)  # 1e-6 MW float slack
    violations_mwh = float(violation_h.sum())

    # ---- 5. availability / SLA --------------------------------------------
    curtail_hours = (deficit_final > 1e-9).sum(axis=1).astype(np.float64)
    curtail_mwh = deficit_final.sum(axis=1)
    avail = 1.0 - curtail_hours / float(c["n_hours"])

    breach_mwh_total = 0.0
    breach_by_site = {}
    for i in np.flatnonzero(active):
        if mode[i] == "firm":
            continue
        # SLA breach is defined on availability (CONTRACT §2: avail = 1 - curt_h/8760),
        # so hours over the budget are the breach; MW*h over budget = mw * excess hours.
        budget_h = SLA_BUDGET_HOURS[sla[i]]
        breach_annual = mw[i] * max(0.0, float(curtail_hours[i]) - budget_h)
        years = max(0, HORIZON_MONTHS - int(T_eff[i])) / 12.0
        breach_mwh_total += breach_annual * years
        breach_by_site[ids[i]] = breach_annual * years

    # ---- 6. metrics --------------------------------------------------------
    months_active = np.maximum(0, HORIZON_MONTHS - T_eff).astype(np.float64)
    mwmonths = mw * months_active * np.where(active, avail, 0.0)
    delivered = float(mwmonths.sum())
    rev_mult = np.array([SLA_REV_MULT[float(sla[i])] if active[i] else 0.0
                         for i in range(n)])
    rev_weighted = float((mwmonths * rev_mult).sum())
    capex = float(((CAPEX_BATTERY_POWER * mw + CAPEX_BATTERY_ENERGY * bat_mwh)
                   * (np.array(mode, dtype=object) == "battery")).sum())
    sla_penalty = SLA_PENALTY_MULT * USD_PER_MWH * breach_mwh_total
    net = MARGIN_USD_PER_MW_MONTH * rev_weighted - capex - sla_penalty
    score = net - 10.0 * violations_mwh - 5.0 * sla_penalty

    monthly = np.zeros(HORIZON_MONTHS)
    for i in np.flatnonzero(active):
        start = int(T_eff[i])                       # first month with full power
        if start < HORIZON_MONTHS:
            monthly[start:] += mw[i]
    mw_at_month12 = float(monthly[11])

    res = {
        "region": c["region"],
        "score": round(float(score), 6),
        "delivered_mwmonths": round(delivered, 6),
        "rev_weighted_mwmonths": round(rev_weighted, 6),
        "mw_at_month12": round(mw_at_month12, 6),
        "net_value_musd": round(float(net), 6),
        "violations_mwh": round(violations_mwh, 6),
        "sla_breach_mwh": round(float(breach_mwh_total), 6),
        "capex_musd": round(capex, 6),
        "avail_by_site": {ids[i]: round(float(avail[i]), 6)
                          for i in np.flatnonzero(active)},
        "monthly_mw": [round(float(v), 4) for v in monthly],
        "modes": {ids[i]: str(mode[i]) for i in range(n)},
        "curtail_hours_by_site": {ids[i]: round(float(curtail_hours[i]), 3)
                                  for i in np.flatnonzero(active)},
        "curtail_mwh_by_site": {ids[i]: round(float(curtail_mwh[i]), 3)
                               for i in np.flatnonzero(active)},
        "energize_month_by_site": {ids[i]: int(T_eff[i])
                                   for i in np.flatnonzero(active)},
        "sla_by_site": {ids[i]: float(sla[i]) for i in np.flatnonzero(active)},
        "mw_by_site": {ids[i]: round(float(mw[i]), 4) for i in np.flatnonzero(active)},
        "battery_mwh_by_site": {ids[i]: round(float(bat_mwh[i]), 4)
                                for i in np.flatnonzero(active)},
        "sla_penalty_musd": round(float(sla_penalty), 6),
    }
    return res


# ---------------------------------------------------------------------------
# light-weight helper used by run.py / tests / loop
# ---------------------------------------------------------------------------
def summarize(result: dict) -> dict:
    """Compact scalar view of an evaluate() result (for logs / JSON rows)."""
    keys = ("delivered_mwmonths", "mw_at_month12", "net_value_musd",
            "violations_mwh", "sla_breach_mwh", "capex_musd", "score")
    out = {k: result.get(k, 0.0) for k in keys}
    out["n_active"] = sum(1 for m in result.get("modes", {}).values() if m != "skip")
    return out
