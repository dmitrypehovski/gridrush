"""GRIDRUSH — parameterized policy: what to connect, and how.

The policy takes per-site headroom curves plus site features and returns a portfolio:
[{"site_id", "mode": "skip|firm|flex|battery", "mw", "sla", "battery_mwh"}]

It does NOT price the portfolio — sim.engine.evaluate() is the source of truth.
The policy is a heuristic over 9 parameters in [0,1], searched by the loop.

Core model idea (CONTRACT §2):
- firm capacity is capped by the MINIMUM headroom in the year (no curtailment allowed) -> it is
  small, and you wait 18-36 months for it;
- flex / step-up can take MANY MW after 5-10 months, but must reduce load in stress hours;
  how many hours a year is acceptable is the site SLA;
- SLA is a priced choice: 99.99% (0.88 h/yr) pays a x1.25 premium, 99.9% x1.0,
  99% (87.6 h/yr) x0.8 ("you get a premium for six nines" — from the stage);
- a battery covers the deficit in stress hours, but costs capex.

So the policy is a trade: on calm sites take 99.99% and many MW; on congested ones
either fewer MW at a high SLA, or 99% and fast months.
"""

from __future__ import annotations

import numpy as np

PARAM_NAMES = [
    "target_frac",   # fraction of the site max_mw we target
    "sla_bias",      # SLA preference shift (lower = greedier about availability)
    "speed_w",       # weight on connection speed (earlier = more valuable)
    "firm_w",        # premium for firm (no curtailment) / reliability
    "battery_w",     # willingness to pay for a battery
    "risk_w",        # penalty for curtailment risk beyond the SLA price
    "size_w",        # preference for larger sites
    "wait_w",        # penalty for long waits (on top of speed)
    "sub_order",     # substation order: 0 = most headroom first, 1 = least stress first
]

D = len(PARAM_NAMES)

# Real economics (see CONTRACT §1), in $M.
REV_PER_MW_MONTH = 0.10
BAT_CAPEX_MW = 0.35
BAT_CAPEX_MWH = 0.25
HORIZON = 36.0

# (sla, allowed curtailment hours per year, compute-price multiplier)
SLA_LEVELS = [(0.9999, 0.876, 1.25), (0.999, 8.76, 1.00), (0.99, 87.6, 0.80)]
SLA_BY_INDEX = {lvl[0]: lvl for lvl in SLA_LEVELS}


def decode(p: np.ndarray) -> dict:
    """[0,1]^D -> meaningful parameters."""
    p = np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
    return {
        "target_frac": 0.30 + 0.70 * p[0],
        "sla_bias": -1.0 + 2.0 * p[1],     # >0 -> prefers a high SLA
        "speed_w": -1.0 + 2.0 * p[2],
        "firm_w": -0.5 + 1.5 * p[3],
        "battery_w": -1.0 + 2.0 * p[4],
        "risk_w": p[5],
        "size_w": -0.5 + 1.0 * p[6],
        "wait_w": -0.5 + 1.0 * p[7],
        "sub_order": p[8],
    }


def _site_priority(curves: dict, i: int, par: dict) -> float:
    Hmax = float(np.max(curves["H"][i]))
    mw = float(curves["max_mw"][i])
    hmax_n = min(Hmax / 10.0, 1.0)
    size_n = min(mw / 10.0, 1.0)
    wait_firm_n = min(curves["T_firm"][i] / 36.0, 1.0)
    wait_flex_n = min(curves["T_flex"][i] / 12.0, 1.0)
    stress_n = min(float(curves["stress_hours"][i]) / 400.0, 1.0)
    return (1.2 * hmax_n + 0.8 * size_n - 0.9 * wait_flex_n - 0.5 * wait_firm_n
            - 0.7 * stress_n + 0.3 * par["speed_w"] - 0.4 * par["wait_w"])


def _flex_option(R_sorted: np.ndarray, target: float, par: dict, sla_level: tuple) -> dict:
    """Flex option for a SPECIFIC SLA level.

    Returns {"mw","sla","budget","avail","k_hours"} or {} if infeasible.
    """
    sla, budget_h, rev_mult = sla_level
    # sla_bias > 0 -> shrink the allowed curtailment (we fear risk)
    bias = 0.5 + 0.5 * par["sla_bias"]
    eff_budget = budget_h * bias
    nb = int(np.clip(np.floor(eff_budget), 0, len(R_sorted) - 1))
    cap_mw = float(R_sorted[nb]) if nb > 0 else 0.0
    mw = float(min(target, max(0.0, cap_mw)))
    if mw < 0.5:
        return {}
    k_hours = int(np.searchsorted(R_sorted, mw, side="left"))  # #{R < mw}
    avail = max(0.0, 1.0 - k_hours / 8760.0)
    return {"mw": mw, "sla": sla, "budget": budget_h, "avail": avail,
            "k_hours": k_hours, "rev_mult": rev_mult}


def build_portfolio(curves: dict, params: np.ndarray | dict,
                    sub_limit_mw: float | None = None) -> list[dict]:
    """Builds the portfolio greedily per substation with a shared headroom remainder.

    `sub_limit_mw` — optional hard cap on the TOTAL new load on a substation.
    When set, the builder never exceeds it, so a physical constraint (e.g. the measured
    AC power-flow limit of a feeder) acts inside the policy instead of being punished
    afterwards. Default None — previous behaviour.
    """
    par = decode(params) if not isinstance(params, dict) else params
    n = len(curves["ids"])
    sub_idx = np.asarray(curves["sub_idx"])
    H = np.asarray(curves["H"], dtype=float)
    max_mw = np.asarray(curves["max_mw"], dtype=float)
    T_firm = np.asarray(curves["T_firm"])
    T_flex = np.asarray(curves["T_flex"])
    T_on = np.asarray(curves["T_on"])

    portfolio: list[dict] = [{"site_id": curves["ids"][i], "mode": "skip", "mw": 0.0,
                              "sla": 0.999, "battery_mwh": 0.0} for i in range(n)]
    target_frac = float(par["target_frac"])
    min_mw = 0.5

    subs = np.unique(sub_idx)
    sub_heads = {int(s): H[np.where(sub_idx == s)[0][0]].copy() for s in subs}
    if par["sub_order"] >= 0.5:
        subs_sorted = sorted(subs, key=lambda s: -np.mean(sub_heads[int(s)]))
    else:
        subs_sorted = sorted(subs, key=lambda s: -np.max(sub_heads[int(s)]))
    sub_rank = {int(s): r for r, s in enumerate(subs_sorted)}

    order = sorted(range(n), key=lambda i: (sub_rank[int(sub_idx[i])], -_site_priority(curves, i, par)))
    remaining = {int(s): sub_heads[int(s)].copy() for s in subs}
    alloc_total = {int(s): 0.0 for s in subs}

    for i in order:
        s = int(sub_idx[i])
        R = remaining[s]
        if np.max(R) < min_mw:
            continue
        target = float(max_mw[i]) * target_frac
        if sub_limit_mw is not None:
            room = float(sub_limit_mw) - alloc_total[s]
            target = min(target, max(0.0, room))
        if target < min_mw:
            continue
        R_sorted = np.sort(R)

        # --- FIRM: no curtailment, maximum is the minimum headroom over the year.
        # 0.02 MW margin so rounding cannot produce a violation in the independent verifier.
        firm_mw = float(min(target, max(0.0, R_sorted[0] - 0.02)))
        firm_mw = float(np.floor(firm_mw * 100.0) / 100.0)
        v_firm = -1e9
        if firm_mw >= min_mw:
            mon = max(0.0, HORIZON - float(T_firm[i]))
            v_firm = REV_PER_MW_MONTH * 1.25 * firm_mw * mon   # firm = 99.99%, premium
            v_firm *= 1.0 + par["speed_w"] * (mon / HORIZON)
            v_firm += par["firm_w"] * firm_mw * 2.0

        # --- FLEX: per SLA level; the step-up speed counts
        v_flex, flex_mw, flex_sla, flex_avail = -1e9, 0.0, 0.999, 1.0
        mon_flex = max(0.0, HORIZON - float(T_flex[i]))
        for lvl in SLA_LEVELS:
            rev_mult = lvl[2]
            opt = _flex_option(R_sorted, target, par, lvl)
            if not opt:
                continue
            # recompute value for this SLA (in _flex_option it is averaged — make it explicit)
            mw = opt["mw"]
            v = REV_PER_MW_MONTH * rev_mult * mw * mon_flex / HORIZON
            v *= 1.0 + par["speed_w"] * (mon_flex / HORIZON)
            v *= 1.0 + 0.25 * par["size_w"] * (mw / max(float(max_mw[i]), 1e-6))
            v -= par["risk_w"] * (1.0 - opt["avail"]) * 40.0 * mw
            if v > v_flex:
                v_flex, flex_mw, flex_sla, flex_avail = v, mw, opt["sla"], opt["avail"]

        # --- BATTERY: target MW, deficit covered by the battery (at the cheapest SLA)
        bat_mw = float(min(target, max(0.0, float(np.max(R)))))
        # engine: the battery has a DAILY energy budget (0.9 * bat_mwh), not annual.
        # So size it for the hardest day.
        gap = np.clip(bat_mw - R, 0.0, None)
        days = min(365, len(gap) // 24)
        daily_gap = gap[: days * 24].reshape(days, 24).sum(axis=1) if days else gap.sum()
        deficit_mwh = float(np.max(daily_gap)) / 0.90
        bat_capex = (BAT_CAPEX_MW * bat_mw + BAT_CAPEX_MWH * deficit_mwh) * (
            0.6 + 1.4 * max(0.0, -par["battery_w"]))
        mon_on = max(0.0, HORIZON - float(T_on[i]))
        v_bat = -1e9
        # A battery only makes sense if it actually covers the stress hours that would
        # otherwise break 99.99%. Otherwise it is flex with extra capex — not taken.
        if bat_mw >= min_mw and deficit_mwh > 0.5:
            v_bat = REV_PER_MW_MONTH * 1.25 * bat_mw * mon_on
            v_bat *= 1.0 + par["speed_w"] * (mon_on / HORIZON)
            v_bat -= bat_capex

        options = [("skip", 0.0, 0.0, 0.999, 0.0),
                   ("firm", firm_mw, v_firm, 0.9999, 0.0),
                   ("flex", flex_mw, v_flex, flex_sla, 0.0),
                   ("battery", bat_mw, v_bat, 0.9999, deficit_mwh)]
        mode, mw, _v, sla, bmwh = max(options, key=lambda o: o[2])
        if mode == "skip" or mw < min_mw:
            continue
        if mode == "battery" and bmwh <= 0.5:
            mode, bmwh = "flex", 0.0   # battery covers nothing -> plain flex

        portfolio[i] = {"site_id": curves["ids"][i], "mode": mode, "mw": float(np.floor(mw * 100.0) / 100.0),
                        "sla": float(sla), "battery_mwh": round(float(bmwh), 2)}
        alloc_total[s] += portfolio[i]["mw"]
        if mode == "firm":
            remaining[s] = np.maximum(0.0, R - portfolio[i]["mw"])
        else:  # flex/battery: take everything available in stress hours
            remaining[s] = np.where(R < portfolio[i]["mw"], 0.0, R - portfolio[i]["mw"])

    return repair_portfolio(curves, portfolio)


def _cover_daily(deficit: np.ndarray, daily_budget: float) -> np.ndarray:
    """Local copy of the engine logic: daily battery budget, deepest hours first."""
    if daily_budget <= 0:
        return np.zeros_like(deficit)
    n_days = deficit.size // 24
    d = deficit[: n_days * 24].reshape(n_days, 24)
    order = np.argsort(-d, axis=1, kind="stable")
    d_sorted = np.take_along_axis(d, order, axis=1)
    cum = np.cumsum(d_sorted, axis=1)
    before = cum - d_sorted
    covered_sorted = np.minimum(d_sorted, np.maximum(0.0, daily_budget - before))
    covered = np.empty_like(covered_sorted)
    np.put_along_axis(covered, order, covered_sorted, axis=1)
    out = np.zeros_like(deficit)
    out[: n_days * 24] = covered.reshape(-1)
    return out


def _avail_given(curves, sub_rows, k, mw, cap_left, bat_mwh) -> tuple[float, np.ndarray]:
    """Site availability for a given MW (mimics the engine allocation order)."""
    s = sub_rows[k]
    load = np.minimum(mw, np.maximum(0.0, cap_left[s]))
    deficit = np.clip(mw - load, 0.0, None)
    if bat_mwh > 0:
        deficit = np.clip(deficit - _cover_daily(deficit, 0.90 * bat_mwh), 0.0, None)
    avail = 1.0 - float((deficit > 1e-9).sum()) / 8760.0
    return avail, load


def repair_portfolio(curves: dict, portfolio: list[dict], verbose: bool = False) -> list[dict]:
    """Checks its own plan and shrinks MW until every site SLA holds.

    Mandatory step: the substation is shared, so two flex sites compete for headroom
    in stress hours. Without repair the plan is optimistic and part of MW is unsellable.
    Order matches the engine (by energize month) so forecast == verification.
    """
    ids = list(curves["ids"])
    sub_rows = np.asarray(curves["sub_idx"])
    H_sub = np.asarray(curves["H_sub"], dtype=float)
    S = H_sub.shape[0]
    T = {}
    for k, item in enumerate(portfolio):
        mode = item["mode"]
        if mode == "firm":
            T[k] = float(curves["T_firm"][k])
        elif mode == "flex":
            T[k] = float(curves["T_flex"][k])
        else:
            T[k] = float(curves["T_on"][k])

    firm_total = np.zeros(S)
    for k, item in enumerate(portfolio):
        if item["mode"] == "firm":
            firm_total[sub_rows[k]] += item["mw"]
    # firm must not exceed the substation minimum headroom
    for s in range(S):
        rows = np.flatnonzero(sub_rows == s)
        if rows.size:
            hmin = float(H_sub[s].min())
            if firm_total[s] > hmin:
                # shrink firm sites on this substation proportionally
                scale = max(0.0, hmin - 0.02) / max(firm_total[s], 1e-9)
                for k, item in enumerate(portfolio):
                    if item["mode"] == "firm" and sub_rows[k] == s:
                        item["mw"] = float(np.floor(item["mw"] * scale * 100.0) / 100.0)
                firm_total[s] = sum(item["mw"] for k, item in enumerate(portfolio)
                                    if item["mode"] == "firm" and sub_rows[k] == s)

    cap_left = H_sub - firm_total[:, None]
    flex = [(k, it) for k, it in enumerate(portfolio) if it["mode"] in ("flex", "battery")]
    flex.sort(key=lambda kv: (T[kv[0]], ids[kv[0]]))
    repaired = 0
    for k, item in flex:
        s = int(sub_rows[k])
        mw_hi = float(item["mw"])
        bat = float(item.get("battery_mwh", 0.0))
        sla = float(item["sla"])
        lo, hi, best = 0.0, mw_hi, 0.0
        for _ in range(16):
            mid = 0.5 * (lo + hi)
            avail, _ = _avail_given(curves, sub_rows, k, mid, cap_left, bat)
            if avail >= sla - 1e-9:
                best, lo = mid, mid
            else:
                hi = mid
        if best < 0.5:
            item["mode"], item["mw"], item["battery_mwh"] = "skip", 0.0, 0.0
            repaired += 1
            continue
        new_mw = float(np.floor(best * 100.0) / 100.0)
        if new_mw < item["mw"] - 1e-9:
            repaired += 1
        item["mw"] = new_mw
        _, load = _avail_given(curves, sub_rows, k, new_mw, cap_left, bat)
        cap_left[s] = cap_left[s] - load
    if verbose and repaired:
        print(f"  repair: {repaired} sites adjusted to meet SLA")
    return portfolio


def params_to_json(params) -> dict:
    par = decode(params) if not isinstance(params, dict) else params
    return {k: (round(float(v), 4) if isinstance(v, (int, float, np.floating)) else v)
            for k, v in par.items()}
