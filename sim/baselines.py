"""GRIDRUSH honest baselines (CONTRACT.md §4/§7) -- not strawmen.

Each baseline is a *reasonable* interconnection strategy an operator could actually
run; the agent policy has to beat real strategies, not a dummy.

    BASELINES = {"all_firm_greedy": fn, "queue_order": fn, "max_mw_no_flex": fn}
    fn(region, sites) -> list[portfolio item]

1. all_firm_greedy -- "wait for firm, take everything the grid will ever give":
   every site requests firm service, biggest best-hour headroom first, capped by the
   substation's tightest-hour firm budget (firm MW is never curtailed). Waits
   T_firm (18-36 months). Legitimate conservative strategy: zero curtailment,
   zero SLA risk, but slow and small.
2. queue_order -- same firm strategy, but the queue is served shortest-T_firm first.
   A real ISOs queue discipline; strictly better than random/greedy ordering.
3. max_mw_no_flex -- "sign everything non-firm at nameplate": flex at max feasible
   MW for every site, no battery, no curtailment discipline, accepts the SLA hit.
   Maximises gross MW early, pays for it in availability/SLA penalties.
"""
import numpy as np

try:
    from .curves import site_curves
except ImportError:
    from curves import site_curves

MIN_MW = 0.5


def _firm_portfolio(region, sites, order_key):
    """Firm allocation under the per-substation tightest-hour budget."""
    c = site_curves(region)
    n = c["n_sites"]
    Hmax = c["Hmax_mw"]
    Hmin = c["Hmin_mw"]
    sub_idx = c["sub_idx"]
    max_mw = c["max_mw"]
    S = c["n_substations"]
    ids = c["ids"]

    # firm budget of a substation = headroom in its tightest hour (firm cannot curtail)
    remaining = np.zeros(S)
    for j in range(S):
        rows = np.flatnonzero(sub_idx == j)
        if rows.size:
            remaining[j] = max(0.0, float(Hmin[rows[0]]))

    order = sorted(range(n), key=lambda i: order_key(i, c))
    portfolio = []
    for i in order:
        s = int(sub_idx[i])
        room = float(min(max_mw[i], Hmax[i], remaining[s]))
        if room < MIN_MW:
            continue
        room = np.floor(room * 10.0) / 10.0  # 0.1 MW granularity
        if room < MIN_MW:
            continue
        remaining[s] -= room
        portfolio.append({"site_id": ids[i], "mode": "firm", "mw": float(room),
                          "sla": 0.999, "battery_mwh": 0.0})
    return portfolio


def all_firm_greedy(region, sites):
    """Every site requests firm service at max MW, first-come-first-served by site id.

    Honest conservative strategy: zero curtailment, zero SLA risk, but the
    tightest-hour firm budget forces the substation to shed the tail of the queue,
    and every MW waits T_firm (18-36 months). Big and slow, or small and slow.
    """
    def key(i, c):
        return (c["ids"][i],)
    return _firm_portfolio(region, sites, key)


def queue_order(region, sites):
    """Firm, shortest interconnection queue (smallest T_firm) served first."""
    def key(i, c):
        return (int(c["T_firm"][i]), -float(c["Hmax_mw"][i]), c["ids"][i])
    return _firm_portfolio(region, sites, key)


def max_mw_no_flex(region, sites):
    """Non-firm (flex) at max feasible MW, no battery, no curtailment discipline.

    Signs every site at the best-hour headroom (bounded by the substation's own
    capacity so the portfolio stays physically sane), energizes fast at T_flex,
    and simply eats the curtailment: gross MW is maximal, availability and SLA
    are not managed.
    """
    c = site_curves(region)
    n = c["n_sites"]
    S = c["n_substations"]
    sub_idx = c["sub_idx"]
    remaining = c["cap_mw"].astype(float).copy()
    order = sorted(range(n), key=lambda i: (int(c["T_flex"][i]), c["ids"][i]))
    portfolio = []
    for i in order:
        s = int(sub_idx[i])
        mw = float(min(c["max_mw"][i], c["Hmax_mw"][i], remaining[s]))
        mw = np.floor(mw * 10.0) / 10.0
        if mw < MIN_MW:
            continue
        remaining[s] -= mw
        portfolio.append({"site_id": c["ids"][i], "mode": "flex", "mw": mw,
                          "sla": 0.999, "battery_mwh": 0.0})
    return portfolio


BASELINES = {
    "all_firm_greedy": all_firm_greedy,
    "queue_order": queue_order,
    "max_mw_no_flex": max_mw_no_flex,
}

BASELINE_LABELS = {
    "all_firm_greedy": "All firm, biggest headroom first",
    "queue_order": "Firm, shortest queue (T_firm) first",
    "max_mw_no_flex": "Flex at max MW, no battery / no SLA discipline",
}
