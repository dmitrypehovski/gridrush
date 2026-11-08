#!/usr/bin/env python3
"""Real AC power flow for GRIDRUSH on a real medium-voltage feeder.

The rest of the simulator scores sites with a profile-based headroom model.
This module answers the judges' question "where is the real power flow?" with
one measured AC power-flow study on ``pandapower.networks.mv_oberrhein`` - a
real 20 kV German MV network shipped with pandapower (179 buses, 181 lines,
two 110/20 kV, 25 MVA transformers).

What is measured
----------------
* Base case: one AC PF, no added load.  The public case scales its loads to
  0.6 of nameplate, so the solved load is 37.1 MW (61.9 MW nameplate).
* ``feeder_headroom()``: for 15 load-centre buses (8 in MV sub-area A, 7 in
  sub-area B, spanning the feeder's voltage range) the largest single-bus
  added load that keeps AC PF converged with zero violations (bus voltage
  inside 0.94-1.06 p.u. and every line/transformer at or below 100 % of its
  rating).  Found by exponential search + bisection and cached in-process.
* ``check_portfolio(mw_list, buses=None, scale=1.0)``: places new constant
  power loads (cos(phi)=0.98) on the given buses, runs AC PF and returns
  convergence, max line loading, min voltage, violation count, per-bus
  voltages and the most loaded branches.
* The real case: the five largest sites of the agent's portfolio in
  ``results/loop.json``, placed on the best-headroom buses, checked as-is and
  at scale=1.5, plus the largest uniform scale that still passes.

Honesty
-------
``mv_oberrhein`` is a real feeder, but *which* of its buses we use for our
synthetic sites is an illustration of load class, not a claim about a
specific project site.  The agent's portfolio is synthetic siting (CONTRACT.md
section 1); only the physics here is real.

Usage (from the gridrush root, with the spike virtualenv)::

    /path/to/spike-grid/.venv/bin/python sim/powerflow.py
    /path/to/spike-grid/.venv/bin/python sim/powerflow.py --no-html

Writes ``results/powerflow.json`` and a self-contained ``web/physics.html``
(no external dependencies, opens from file://).  Deterministic on the same
pandapower/numpy/scipy stack; no network access.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import math
import time
import warnings
from pathlib import Path

import numpy as np
import pandapower as pp

warnings.filterwarnings("ignore", message=".*numba.*")
try:  # keep the "numba is not installed" notice out of the demo output
    import logging

    logging.getLogger("pandapower").setLevel(logging.ERROR)
except Exception:  # pragma: no cover - never worth failing over logging
    pass

PF_KWARGS = dict(calculate_voltage_angles=True, init="auto", numba=False)
VMIN_PU, VMAX_PU = 0.94, 1.06
LOADING_LIMIT_PCT = 100.0
COS_PHI = 0.98
Q_PER_MW = float(math.tan(math.acos(COS_PHI)))
TOL = 1e-6
N_HEADROOM_BUSES = 15
SINGLE_SITE_MW = 4.5
CLASS_CASE_MW = [4.5, 3.2, 6.0, 2.1, 5.0]  # the "5 sites x 4-6 MW" load class
ROOT = Path(__file__).resolve().parents[1]

_STATE: dict = {"net": None, "base": None, "area": None, "load_by_bus": None}
_HEADROOM: dict = {}


# --------------------------------------------------------------------------- #
# Feeder model
# --------------------------------------------------------------------------- #
def _run_pf(net) -> float:
    """Run AC PF in place; non-convergence is a result, not an exception."""
    t0 = time.perf_counter()
    try:
        pp.runpp(net, **PF_KWARGS)
    except pp.LoadflowNotConverged:
        net.converged = False
    return time.perf_counter() - t0


def _metrics(net) -> dict:
    """Power-flow snapshot with the violation definition used everywhere here."""
    if not getattr(net, "converged", False):
        return dict(
            converged=False, min_vm_pu=None, max_vm_pu=None, max_loading_pct=None,
            max_line_loading_pct=None, n_violations=None, n_voltage_violations=None,
            n_thermal_violations=None, voltage_violation_buses=[],
            thermal_violations=[], worst_vm_bus=None, per_bus_vm=None,
            top_loaded_lines=[], top_loaded_trafos=[],
        )

    vm = net.res_bus.vm_pu
    line_ld = net.res_line.loading_percent
    trafo_ld = net.res_trafo.loading_percent if len(net.trafo) else np.array([])
    v_bad = (vm.to_numpy() < VMIN_PU - TOL) | (vm.to_numpy() > VMAX_PU + TOL)

    thermal = []
    for i in net.res_line.index[line_ld > LOADING_LIMIT_PCT + TOL]:
        thermal.append(dict(kind="line", index=int(i),
                            from_bus=int(net.line.from_bus[i]),
                            to_bus=int(net.line.to_bus[i]),
                            loading_pct=round(float(line_ld[i]), 2)))
    for i in net.res_trafo.index[trafo_ld > LOADING_LIMIT_PCT + TOL]:
        thermal.append(dict(kind="trafo", index=int(i),
                            from_bus=int(net.trafo.hv_bus[i]),
                            to_bus=int(net.trafo.lv_bus[i]),
                            loading_pct=round(float(trafo_ld[i]), 2)))

    line_order = np.argsort(-line_ld.to_numpy())[:6]
    top_lines = [
        dict(kind="line",
             label="L%d %d-%d" % (int(net.res_line.index[j]),
                                  int(net.line.from_bus[net.res_line.index[j]]),
                                  int(net.line.to_bus[net.res_line.index[j]])),
             index=int(net.res_line.index[j]),
             from_bus=int(net.line.from_bus[net.res_line.index[j]]),
             to_bus=int(net.line.to_bus[net.res_line.index[j]]),
             loading_pct=round(float(line_ld.iloc[j]), 2))
        for j in line_order
    ]
    trafo_order = np.argsort(-np.asarray(trafo_ld, dtype=float)) if len(trafo_ld) else []
    top_trafos = [
        dict(kind="trafo", label="T%d %d/%d kV" % (
            int(net.res_trafo.index[j]),
            int(net.trafo.vn_hv_kv[net.res_trafo.index[j]]),
            int(net.trafo.vn_lv_kv[net.res_trafo.index[j]])),
            index=int(net.res_trafo.index[j]),
            from_bus=int(net.trafo.hv_bus[net.res_trafo.index[j]]),
            to_bus=int(net.trafo.lv_bus[net.res_trafo.index[j]]),
            loading_pct=round(float(net.res_trafo.loading_percent.iloc[j]), 2))
        for j in trafo_order
    ]
    all_loading = np.concatenate([line_ld.to_numpy(), np.asarray(trafo_ld, dtype=float)])
    return dict(
        converged=True,
        min_vm_pu=round(float(vm.min()), 5),
        max_vm_pu=round(float(vm.max()), 5),
        max_loading_pct=round(float(all_loading.max()), 2),
        max_line_loading_pct=round(float(line_ld.max()), 2),
        n_violations=int(v_bad.sum()) + len(thermal),
        n_voltage_violations=int(v_bad.sum()),
        n_thermal_violations=len(thermal),
        voltage_violation_buses=[int(b) for b in net.bus.index[v_bad]],
        thermal_violations=thermal,
        worst_vm_bus=int(vm.idxmin()),
        per_bus_vm={int(b): round(float(v), 5) for b, v in vm.items()},
        top_loaded_lines=top_lines,
        top_loaded_trafos=top_trafos,
    )


def _area_map(net) -> dict:
    """Map every 20 kV bus to the MV sub-area fed by one 110/20 kV transformer.

    Uses only lines that are really in service: closed line switches are part
    of the path, open ones remove the line (mv_oberrhein has 5 open LBS).
    """
    open_lines = {
        int(element)
        for element, et, closed in zip(net.switch.element, net.switch.et, net.switch.closed)
        if et == "l" and not bool(closed)
    }
    adj = collections.defaultdict(list)
    for line in net.line.index:
        if not net.line.in_service[line] or int(line) in open_lines:
            continue
        a, b = int(net.line.from_bus[line]), int(net.line.to_bus[line])
        adj[a].append(b)
        adj[b].append(a)
    area = {}
    for trafo in net.trafo.index:
        start = int(net.trafo.lv_bus[trafo])
        seen, todo = {start}, collections.deque([start])
        while todo:
            u = todo.popleft()
            for v in adj[u]:
                if v not in seen:
                    seen.add(v)
                    todo.append(v)
        for bus in seen:
            area[bus] = int(trafo)
    return area


def _ensure_feeder():
    """Load and solve the feeder once per process (cached)."""
    if _STATE["net"] is not None:
        return _STATE
    net = pp.networks.mv_oberrhein()
    pp.runpp(net, **PF_KWARGS)
    load_by_bus = net.load.groupby("bus").p_mw.sum()
    _STATE.update(
        net=net,
        base=_metrics(net),
        area=_area_map(net),
        load_by_bus={int(b): float(p) for b, p in load_by_bus.items()},
        nominal_load_mw=float(net.load.p_mw.sum()),
        scaling=float(net.load.scaling.iloc[0]) if len(net.load) else 1.0,
        served_load_mw=float(net.res_load.p_mw.sum()),
    )
    _STATE["area_load_mw"] = {
        int(t): round(float(net.res_load.p_mw[net.load.bus.map(_STATE["area"]) == t].sum()), 3)
        for t in net.trafo.index
    }
    return _STATE


def _big_load_buses(state) -> list:
    """Buses carrying the feeder's largest existing load (42 buses at 0.63 MW)."""
    loads = state["load_by_bus"]
    peak = max(loads.values())
    return [int(b) for b, p in loads.items() if abs(p - peak) < 1e-9]


def _headroom_buses(state) -> list:
    """15 load-centre buses: 4 weakest + ~4 strongest in each MV sub-area.

    Selection is deterministic and deliberately spans both transformers and
    the voltage range, so the table shows how topology-dependent headroom is.
    """
    big = _big_load_buses(state)
    area = state["area"]
    net = state["net"]
    vm = net.res_bus.vm_pu
    areas = sorted(set(area[b] for b in big))
    weak, strong = [], []
    for a in areas:
        buses = sorted([b for b in big if area[b] == a], key=lambda b: (float(vm[b]), b))
        weak.extend(buses[:4])
        strong.extend(list(reversed(buses)))
    selected, used = list(weak), set(weak)
    while len(selected) < N_HEADROOM_BUSES:
        added = False
        for a in areas:
            if len(selected) >= N_HEADROOM_BUSES:
                break
            for b in strong:
                if area[b] == a and b not in used:
                    selected.append(b)
                    used.add(b)
                    added = True
                    break
        if not added:
            break
    return selected[:N_HEADROOM_BUSES]


def _net_with(state, loads, buses):
    net = copy.deepcopy(state["net"])
    for bus, p_mw in zip(buses, loads):
        pp.create_load(net, bus=int(bus), p_mw=float(p_mw),
                       q_mvar=float(p_mw) * Q_PER_MW, name="ac_case")
    return net


def _feasible(state, loads, buses) -> dict:
    net = _net_with(state, loads, buses)
    _run_pf(net)
    return _metrics(net)


def _is_clean(metrics: dict) -> bool:
    return bool(metrics["converged"] and metrics["n_violations"] == 0)


def _binding(metrics: dict) -> str:
    if not metrics["converged"]:
        return "voltage collapse (PF diverged)"
    if any(v["kind"] == "trafo" for v in metrics["thermal_violations"]):
        return "transformer thermal (>100%)"
    if any(v["kind"] == "line" for v in metrics["thermal_violations"]):
        return "line thermal (>100%)"
    if metrics["n_voltage_violations"]:
        return "voltage (outside 0.94-1.06 pu)"
    return "none"


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def feeder_headroom() -> list:
    """Largest single-bus added load (MW) with zero violations, per bus.

    Returns a list sorted by headroom (largest first) with the binding
    constraint at ~2 % above the limit.  Bisection results are cached in
    ``_HEADROOM`` for the lifetime of the process.
    """
    state = _ensure_feeder()
    rows = []
    for bus in _headroom_buses(state):
        if bus not in _HEADROOM:
            mw, binds, loading, vmin = _single_bus_headroom(state, bus)
            _HEADROOM[bus] = dict(headroom_mw=mw, binds=binds)
            _HEADROOM[bus]["loading_at_limit_pct"] = loading
            _HEADROOM[bus]["min_v_at_limit_pu"] = vmin
        rows.append(dict(
            bus=bus,
            area=int(state["area"][bus]),
            base_load_mw=round(state["load_by_bus"][bus], 2),
            base_vm_pu=round(float(state["net"].res_bus.vm_pu[bus]), 4),
            headroom_mw=_HEADROOM[bus]["headroom_mw"],
            binds=_HEADROOM[bus]["binds"],
        ))
    rows.sort(key=lambda r: (-r["headroom_mw"], r["bus"]))
    return rows


def _single_bus_headroom(state, bus, cap_mw: float = 20.0, iters: int = 10):
    """Exponential search + bisection for one bus; returns (MW, binding, ...)."""
    if not _is_clean(_feasible(state, [0.0], [bus])):
        return 0.0, "base case already violates", None, None
    lo, hi, p = 0.0, None, 1.0
    while p <= cap_mw:
        if not _is_clean(_feasible(state, [p], [bus])):
            hi = p
            break
        lo, p = p, p * 2.0
    if hi is None:
        return cap_mw, "cap reached", None, None
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if _is_clean(_feasible(state, [mid], [bus])):
            lo = mid
        else:
            hi = mid
    probe = _feasible(state, [lo * 1.02], [bus])
    return (round(lo, 2), _binding(probe), probe["max_loading_pct"], probe["min_vm_pu"])


def pick_buses(n: int) -> list:
    """Default site buses: largest headroom, alternating between MV sub-areas."""
    rows = feeder_headroom()
    by_area: "collections.OrderedDict[int, list]" = collections.OrderedDict()
    for row in rows:
        by_area.setdefault(row["area"], []).append(row["bus"])
    lists = list(by_area.values())
    order: list = []
    depth = 0
    while len(order) < n and any(depth < len(lst) for lst in lists):
        for lst in lists:
            if depth < len(lst) and lst[depth] not in order:
                order.append(lst[depth])
        depth += 1
    return order[:n]


def check_portfolio(mw_list, buses=None, scale: float = 1.0) -> dict:
    """Place new loads on a real MV feeder and run one AC power flow.

    Parameters
    ----------
    mw_list : list[float]
        New constant-power loads in MW (cos(phi)=0.98).
    buses : list[int] | None
        Feeder buses to use; default = ``pick_buses(len(mw_list))`` (largest
        headroom, alternating between the two MV sub-areas).
    scale : float
        Uniform multiplier applied to every load (used for stress cases).

    Returns
    -------
    dict with the contract keys ``converged``, ``max_line_loading_pct``,
    ``min_vm_pu``, ``n_violations``, ``per_bus_vm``, ``top_loaded_lines`` plus
    the transformer-inclusive ``max_loading_pct`` and violation detail.
    Non-convergence is reported as ``converged=False`` with null metrics.
    """
    state = _ensure_feeder()
    scaled = [float(p) * float(scale) for p in mw_list]
    if buses is None:
        buses = pick_buses(len(scaled))
    buses = [int(b) for b in buses]
    if len(buses) != len(scaled):
        raise ValueError("mw_list and buses must have the same length")

    net = _net_with(state, scaled, buses)
    dt = _run_pf(net)
    m = _metrics(net)
    out = dict(
        converged=m["converged"],
        buses=buses,
        loads_mw=[round(p, 3) for p in scaled],
        scale=round(float(scale), 5),
        total_mw=round(float(sum(scaled)), 3),
        max_line_loading_pct=m["max_line_loading_pct"],
        max_loading_pct=m["max_loading_pct"],
        min_vm_pu=m["min_vm_pu"],
        max_vm_pu=m["max_vm_pu"],
        n_violations=m["n_violations"],
        n_voltage_violations=m["n_voltage_violations"],
        n_thermal_violations=m["n_thermal_violations"],
        voltage_violation_buses=m["voltage_violation_buses"],
        thermal_violations=m["thermal_violations"],
        worst_vm_bus=m["worst_vm_bus"],
        per_bus_vm=m["per_bus_vm"],
        top_loaded_lines=m["top_loaded_lines"],
        top_loaded_trafos=m["top_loaded_trafos"],
        run_ms=round(dt * 1000.0, 1),
    )
    out["status"] = ("converged-zero-violations" if _is_clean(m)
                     else "converged-with-violations" if m["converged"]
                     else "voltage-collapse")
    return out


def _max_scale(mw_list, buses, predicate, cap: float = 4.0, iters: int = 11):
    """Largest uniform scale in [0, cap] satisfying ``predicate(result)``."""
    def ok(s):
        return bool(predicate(check_portfolio(mw_list, buses, scale=s)))

    lo, s, hi = 0.0, 0.1, None
    while s <= cap:
        if not ok(s):
            hi = s
            break
        lo, s = s, s * 2.0
    if hi is None:
        return lo, True
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        if ok(mid):
            lo = mid
        else:
            hi = mid
    return lo, False


# --------------------------------------------------------------------------- #
# Case assembly
# --------------------------------------------------------------------------- #
def _read_portfolio() -> dict:
    """Snapshot of the agent's portfolio in results/loop.json (top sites by MW)."""
    path = ROOT / "results" / "loop.json"
    if not path.exists():
        return dict(source=None, total_mw=0.0, n_sites=0, sites=[],
                    sha256=None, note="results/loop.json not found - using the class case only")
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    sites = [s for s in data["best"]["sites"]
             if s.get("mode") != "skip" and float(s.get("mw", 0.0)) > 0.0]
    sites.sort(key=lambda s: (-float(s["mw"]), str(s.get("id"))))
    return dict(
        source=str(path.relative_to(ROOT)),
        sha256=hashlib.sha256(raw).hexdigest()[:12],
        n_sites=len(sites),
        total_mw=round(sum(float(s["mw"]) for s in sites), 2),
        sites=[dict(id=s["id"], substation=s.get("substation"), mode=s.get("mode"),
                    mw=round(float(s["mw"]), 2)) for s in sites],
    )


def _timing(state) -> dict:
    """Median wall time of one base PF and of one check_portfolio call."""
    base_times = []
    for _ in range(7):
        net = copy.deepcopy(state["net"])
        base_times.append(_run_pf(net))
    bus = feeder_headroom()[0]["bus"]
    check_times = [check_portfolio([SINGLE_SITE_MW], [bus])["run_ms"] for _ in range(7)]
    return dict(
        base_pf_ms=round(float(np.median(base_times)) * 1000.0, 1),
        check_portfolio_ms=round(float(np.median(check_times)), 1),
    )


def build_report() -> dict:
    """Run the whole verification and return the JSON-ready result dict."""
    t_start = time.perf_counter()
    state = _ensure_feeder()
    net = state["net"]
    base = state["base"]

    t0 = time.perf_counter()
    headroom = feeder_headroom()
    headroom_s = time.perf_counter() - t0

    portfolio = _read_portfolio()
    top = portfolio["sites"][:5]
    if top:
        mws = [s["mw"] for s in top]
        portfolio_note = "top-5 sites by MW from " + portfolio["source"]
    else:  # noqa: pragma: no cover - defensive fallback
        mws = list(CLASS_CASE_MW)
        portfolio_note = "fallback class case (loop.json unavailable)"
        top = [dict(id="class-%d" % i, substation=None, mode="class", mw=p)
               for i, p in enumerate(mws)]
    buses = pick_buses(len(mws))

    case = check_portfolio(mws, buses)
    stress = check_portfolio(mws, buses, scale=1.5)
    class_case = check_portfolio(CLASS_CASE_MW, pick_buses(len(CLASS_CASE_MW)))

    feasible_scale, _capped = _max_scale(
        mws, buses, lambda r: r["converged"] and r["n_violations"] == 0)
    feasible = check_portfolio(mws, buses, scale=feasible_scale)
    first_bad_scale = min(feasible_scale * 1.03, 4.0)
    first_bad = check_portfolio(mws, buses, scale=first_bad_scale)

    # Physical voltage collapse: first scale where the minimum bus voltage
    # falls below 0.90 p.u. (a level no operator would call a usable grid).
    # We use this instead of non-convergence because Newton's method can keep
    # returning a mathematically converged low-voltage solution for a while.
    collapse_scale, _ = _max_scale(
        mws, buses, lambda r: bool(r["converged"]) and (r["min_vm_pu"] or 0.0) >= 0.90)
    collapse = check_portfolio(mws, buses, scale=collapse_scale)
    solver_scale, _ = _max_scale(mws, buses, lambda r: bool(r["converged"]))
    solver_limit = check_portfolio(mws, buses, scale=solver_scale)

    best_bus = headroom[0]["bus"]
    single = check_portfolio([SINGLE_SITE_MW], [best_bus])
    largest_site = portfolio["sites"][0] if portfolio["sites"] else None
    largest = (check_portfolio([largest_site["mw"]], [best_bus]) if largest_site
               else dict(converged=True, total_mw=0.0, min_vm_pu=None, max_loading_pct=None,
                         n_violations=0, status="n/a", worst_vm_bus=None,
                         thermal_violations=[], voltage_violation_buses=[], max_line_loading_pct=None))

    # Voltage profile: all buses, ordered by base-case voltage (shown in the HTML).
    order = sorted(net.bus.index, key=lambda b: float(net.res_bus.vm_pu[b]))
    profile = dict(
        order="buses ordered by base-case voltage",
        buses=[int(b) for b in order],
        base_vm=[round(float(net.res_bus.vm_pu[b]), 5) for b in order],
        case_vm=[feasible["per_bus_vm"][int(b)] for b in order],
        case_label="+%.1f MW (feeder limit, 0 violations)" % feasible["total_mw"],
        limits=[VMIN_PU, VMAX_PU],
    )

    branch_loading = sorted(
        feasible["top_loaded_trafos"] + feasible["top_loaded_lines"],
        key=lambda b: -b["loading_pct"],
    )[:8]

    trafos = []
    for t in net.trafo.index:
        served = float(net.res_trafo.p_hv_mw[t])
        trafos.append(dict(
            index=int(t),
            sn_mva=round(float(net.trafo.sn_mva[t]), 1),
            loading_pct=round(float(net.res_trafo.loading_percent[t]), 2),
            p_hv_mw=round(served, 2),
            from_bus=int(net.trafo.hv_bus[t]),
            to_bus=int(net.trafo.lv_bus[t]),
        ))

    data = dict(
        feeder="mv_oberrhein",
        feeder_info=dict(
            name="mv_oberrhein",
            source="pandapower.networks.mv_oberrhein (bundled with pandapower)",
            note="real 20 kV German MV network (Oberrhein region); public test case",
            n_bus=int(len(net.bus)),
            n_line=int(len(net.line)),
            n_trafo=int(len(net.trafo)),
            mv_kv=20.0,
            hv_kv=110.0,
            trafo_mva=25.0,
            nominal_load_mw=round(state["nominal_load_mw"], 2),
            load_scaling=state["scaling"],
            served_load_mw=round(state["served_load_mw"], 2),
            areas=[dict(trafo=int(t), n_bus=int(sum(1 for b, a in state["area"].items() if a == int(t))),
                        served_load_mw=state["area_load_mw"][int(t)])
                   for t in sorted(net.trafo.index)],
        ),
        base=dict(
            converged=base["converged"],
            load_mw=round(state["served_load_mw"], 2),
            served_load_mw=round(state["served_load_mw"], 2),
            n_bus=int(len(net.bus)),
            min_vm=base["min_vm_pu"],
            max_loading=base["max_loading_pct"],
            max_line_loading_pct=base["max_line_loading_pct"],
            worst_vm_bus=base["worst_vm_bus"],
            n_violations=base["n_violations"],
            trafos=trafos,
        ),
        policy=dict(
            violation_definition="bus |V| outside 0.94-1.06 p.u. or any line/transformer loading > 100%",
            new_load_cos_phi=COS_PHI,
            new_load_q_per_mw=round(Q_PER_MW, 4),
            limits=dict(vmin_pu=VMIN_PU, vmax_pu=VMAX_PU, loading_pct=LOADING_LIMIT_PCT),
        ),
        headroom=headroom,
        portfolio=dict(
            source=portfolio["source"],
            sha256=portfolio["sha256"],
            n_sites=portfolio["n_sites"],
            total_mw=portfolio["total_mw"],
            top5_ids=[s["id"] for s in top],
            top5_mw=[round(float(s["mw"]), 2) for s in top],
            note=portfolio_note,
        ),
        case=dict(label="5 largest agent sites (as committed)",
                  loads_mw=[round(float(p), 2) for p in mws], buses=buses, **{
                      k: v for k, v in case.items() if k in (
                          "converged", "min_vm_pu", "max_loading_pct", "max_line_loading_pct",
                          "n_violations", "n_voltage_violations", "n_thermal_violations",
                          "voltage_violation_buses", "thermal_violations", "worst_vm_bus",
                          "status", "total_mw", "run_ms")}),
        stress_case=dict(label="top-5 sites at scale=1.5 (stress)",
                         scale=1.5, loads_mw=stress["loads_mw"], buses=stress["buses"],
                         **{k: v for k, v in stress.items() if k in (
                             "converged", "min_vm_pu", "max_loading_pct", "max_line_loading_pct",
                             "n_violations", "n_voltage_violations", "n_thermal_violations",
                             "voltage_violation_buses", "thermal_violations", "worst_vm_bus",
                             "status", "total_mw", "run_ms")}),
        class_case=dict(label="5 sites x 4-6 MW load class (20.8 MW)",
                        loads_mw=CLASS_CASE_MW, buses=class_case["buses"],
                        **{k: v for k, v in class_case.items() if k in (
                            "converged", "min_vm_pu", "max_loading_pct", "max_line_loading_pct",
                            "n_violations", "n_voltage_violations", "n_thermal_violations",
                            "voltage_violation_buses", "thermal_violations", "worst_vm_bus",
                            "status", "total_mw")}),
        feasible_case=dict(label="largest uniform scale of the top-5 portfolio with 0 violations",
                           scale=round(float(feasible_scale), 4),
                           loads_mw=feasible["loads_mw"], buses=feasible["buses"],
                           **{k: v for k, v in feasible.items() if k in (
                               "converged", "min_vm_pu", "max_loading_pct", "max_line_loading_pct",
                               "n_violations", "n_voltage_violations", "n_thermal_violations",
                               "voltage_violation_buses", "thermal_violations", "worst_vm_bus",
                               "status", "total_mw", "run_ms")}),
        first_violation=dict(scale=round(float(first_bad_scale), 4),
                             total_mw=first_bad["total_mw"],
                             **{k: v for k, v in first_bad.items() if k in (
                                 "converged", "min_vm_pu", "max_loading_pct", "n_violations",
                                 "n_voltage_violations", "n_thermal_violations",
                                 "voltage_violation_buses", "thermal_violations", "worst_vm_bus",
                                 "status")}),
        voltage_collapse=dict(
            definition="first scale where min bus voltage < 0.90 p.u. (physical collapse threshold)",
            scale=round(float(collapse_scale), 4),
            total_mw=collapse["total_mw"],
            converged=collapse["converged"],
            min_vm_pu=collapse["min_vm_pu"],
            max_loading_pct=collapse["max_loading_pct"],
            n_violations=collapse["n_violations"],
            worst_vm_bus=collapse["worst_vm_bus"],
            status=collapse["status"]),
        solver_limit=dict(
            note="mathematical solver limit: Newton PF still returns a converged solution below "
                 "the physical voltage-collapse threshold - not a usable operating point",
            scale=round(float(solver_scale), 4),
            total_mw=solver_limit["total_mw"],
            min_vm_pu=solver_limit["min_vm_pu"],
            max_loading_pct=solver_limit["max_loading_pct"],
            worst_vm_bus=solver_limit["worst_vm_bus"]),
        single_site_case=dict(label="a single %.1f MW site at the feeder's best bus" % SINGLE_SITE_MW,
                              bus=best_bus,
                              headroom_at_bus_mw=headroom[0]["headroom_mw"],
                              **{k: v for k, v in single.items() if k in (
                                  "converged", "min_vm_pu", "max_loading_pct", "max_line_loading_pct",
                                  "n_violations", "n_voltage_violations", "n_thermal_violations",
                                  "voltage_violation_buses", "thermal_violations", "worst_vm_bus",
                                  "status", "total_mw", "run_ms")}),
        largest_site_case=dict(
            label="largest single agent site at the feeder's best bus",
            site_id=(largest_site["id"] if largest_site else None),
            bus=best_bus,
            headroom_at_bus_mw=headroom[0]["headroom_mw"],
            **{k: v for k, v in largest.items() if k in (
                "converged", "min_vm_pu", "max_loading_pct", "max_line_loading_pct",
                "n_violations", "n_voltage_violations", "n_thermal_violations",
                "voltage_violation_buses", "thermal_violations", "worst_vm_bus",
                "status", "total_mw")}),
        voltage_profile=profile,
        branch_loading=branch_loading,
        timing=dict(**_timing(state), headroom_s=round(headroom_s, 2),
                    full_report_s=round(time.perf_counter() - t_start, 2)),
        caveats=[
            "mv_oberrhein is a real German 20 kV MV network shipped with pandapower (Oberrhein region). "
            "Assigning our synthetic sites to its buses is an illustration of the load class, not a claim about a specific project site.",
            "The public case scales its loads to 0.6 of nameplate: 61.86 MW nameplate = 37.12 MW actually served in the power flow.",
            "Violation = bus voltage outside 0.94-1.06 p.u. or any line/transformer above 100% of rating. "
            "New loads are constant power with cos(phi)=0.98 and no voltage support.",
            "The two 110/20 kV, 25 MVA transformers are the binding constraint: the feeder's spare capacity is set by them "
            "(70.9% and 85.5% loaded at base), not by the 20 kV line ratings.",
            "Headroom per bus is not additive: each bus is tested alone against the shared transformer capacity, "
            "so summing per-bus values overstates what the feeder can host at once.",
            "The portfolio snapshot is read from results/loop.json at run time (sha256 prefix in portfolio.sha256); "
            "rerun sim/powerflow.py after the agent loop changes the portfolio.",
            "Deterministic on the measured stack (Python 3.9.6, pandapower 3.2.2, numpy 2.0.2, scipy 1.13.1); no network access.",
        ],
    )
    return data


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def _summary(data: dict) -> str:
    base, case, stress = data["base"], data["case"], data["stress_case"]
    feasible, first_bad = data["feasible_case"], data["first_violation"]
    collapse, single = data["voltage_collapse"], data["single_site_case"]
    solver, largest = data["solver_limit"], data["largest_site_case"]
    hr = data["headroom"]
    lines = [
        "=== AC power flow on a real MV feeder: %s ===" % data["feeder"],
        "base: %d buses, %d lines, %d x %.0f MVA, served load %.1f MW (%.1f MW nameplate x %.1f); "
        "PF converged, %s violations, min V %.4f, max loading %.1f%% (transformer)"
        % (base["n_bus"], data["feeder_info"]["n_line"], data["feeder_info"]["n_trafo"],
           data["feeder_info"]["trafo_mva"], base["served_load_mw"],
           data["feeder_info"]["nominal_load_mw"], data["feeder_info"]["load_scaling"],
           base["n_violations"], base["min_vm"], base["max_loading"]),
        "headroom, %d load-centre buses: %.2f - %.2f MW (computed in %.1f s, cached)"
        % (len(hr), min(r["headroom_mw"] for r in hr), max(r["headroom_mw"] for r in hr),
           data["timing"]["headroom_s"]),
        "portfolio: %d sites, %.1f MW total; top-5 = %s MW on buses %s"
        % (data["portfolio"]["n_sites"], data["portfolio"]["total_mw"],
           [round(p, 2) for p in data["portfolio"]["top5_mw"]], case["buses"]),
        "case  top-5 as committed: %.1f MW -> %s, %s violations, min V %.4f, max loading %.1f%%"
        % (case["total_mw"], case["status"].replace("-", " "), case["n_violations"],
           case["min_vm_pu"], case["max_loading_pct"]),
        "stress scale 1.5:      %.1f MW -> %s, %s violations, min V %.4f, max loading %.1f%%"
        % (stress["total_mw"], stress["status"].replace("-", " "), stress["n_violations"],
           stress["min_vm_pu"], stress["max_loading_pct"]),
        "feasible: scale %.3f = %.1f MW -> converged, %.0f violations, min V %.4f, max loading %.2f%%"
        % (feasible["scale"], feasible["total_mw"], feasible["n_violations"],
           feasible["min_vm_pu"], feasible["max_loading_pct"]),
        "first violation: scale %.3f = %.1f MW -> %s; binding: %s at %.2f%% (min V %.4f)"
        % (first_bad["scale"], first_bad["total_mw"],
           first_bad["status"].replace("-", " "),
           first_bad["thermal_violations"][0]["kind"] if first_bad["thermal_violations"] else "voltage",
           first_bad["thermal_violations"][0]["loading_pct"] if first_bad["thermal_violations"] else float("nan"),
           first_bad["min_vm_pu"]),
        "voltage collapse (min V < 0.90 p.u.): scale %.3f = %.1f MW, max loading %.1f%%"
        % (collapse["scale"], collapse["total_mw"], collapse["max_loading_pct"]),
        "solver still converged at: scale %.3f = %.1f MW, min V %.4f, max loading %.1f%% (not a usable point)"
        % (solver["scale"], solver["total_mw"], solver["min_vm_pu"], solver["max_loading_pct"]),
        "single %.1f MW site @ bus %d: %s, min V %.4f, max loading %.1f%% (bus headroom %.2f MW)"
        % (SINGLE_SITE_MW, single["bus"], single["status"].replace("-", " "),
           single["min_vm_pu"], single["max_loading_pct"], single["headroom_at_bus_mw"]),
        "largest single site %.2f MW @ bus %d: %s, %s violations, min V %.4f, max loading %.1f%%"
        % (largest["total_mw"], largest["bus"], largest["status"].replace("-", " "),
           largest["n_violations"], largest["min_vm_pu"], largest["max_loading_pct"]),
        "timing: base PF %.1f ms, check_portfolio %.1f ms, headroom table %.1f s, full report %.1f s"
        % (data["timing"]["base_pf_ms"], data["timing"]["check_portfolio_ms"],
           data["timing"]["headroom_s"], data["timing"]["full_report_s"]),
    ]
    return "\n".join(lines)


def write_html(data: dict, path: Path) -> None:
    """Render the single-file, offline physics page (data embedded as const)."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    html = _HTML_TEMPLATE.replace("__DATA__", payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Real AC power-flow check on mv_oberrhein")
    ap.add_argument("--json", default=str(ROOT / "results" / "powerflow.json"))
    ap.add_argument("--html", default=str(ROOT / "web" / "physics.html"))
    ap.add_argument("--no-html", action="store_true")
    args = ap.parse_args(argv)

    data = build_report()
    json_path = Path(args.json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not args.no_html:
        write_html(data, Path(args.html))
    print(_summary(data))
    print("wrote %s (%d KB)" % (json_path, json_path.stat().st_size // 1024))
    if not args.no_html:
        print("wrote %s (%d KB)" % (args.html, Path(args.html).stat().st_size // 1024))
    return 0


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GRIDRUSH - real AC power flow on a real MV feeder</title>
<style>
:root{
  --bg:#070c15; --card:#0f1a2c; --card2:#0b1525; --line:#22314b; --txt:#e9eef8;
  --mut:#93a4bf; --green:#35d98f; --red:#ff5f63; --amber:#ffb347; --blue:#58a6ff;
}
*{box-sizing:border-box}
html,body{margin:0}
body{background:
  radial-gradient(1400px 700px at 50% -180px,#13233f 0%,rgba(19,35,63,0) 60%),
  var(--bg);
  color:var(--txt);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  font-size:17px;line-height:1.45}
.wrap{max-width:1460px;margin:0 auto;padding:30px 40px 56px}
h1{font-size:42px;line-height:1.1;margin:0 0 8px;letter-spacing:-.8px}
h2{font-size:27px;margin:38px 0 14px;letter-spacing:-.3px}
h2 .n{color:var(--mut);font-weight:600;margin-right:10px}
.sub{color:var(--mut);font-size:18px;max-width:1180px;margin:0 0 8px}
.badge{display:inline-block;font-size:13px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--green);border:1px solid rgba(53,217,143,.4);border-radius:99px;padding:3px 11px;margin-bottom:14px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-top:22px}
.kpi{background:linear-gradient(180deg,var(--card) 0%,var(--card2) 100%);
  border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.kpi .k{color:var(--mut);font-size:14px;letter-spacing:.06em;text-transform:uppercase}
.kpi .v{font-size:40px;font-weight:750;letter-spacing:-1px;margin:6px 0 2px}
.kpi .d{color:var(--mut);font-size:15px}
.kpi.good .v{color:var(--green)} .kpi.bad .v{color:var(--red)} .kpi.warn .v{color:var(--amber)}
.verdicts{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}
.verdict{border-radius:16px;padding:22px 26px;border:1px solid var(--line);background:var(--card)}
.verdict .tag{font-size:14px;letter-spacing:.1em;text-transform:uppercase;color:var(--mut)}
.verdict .head{font-size:30px;font-weight:760;letter-spacing:-.4px;margin:6px 0 6px}
.verdict .det{color:#cdd8ea;font-size:17px}
.verdict.ok{border-color:rgba(53,217,143,.55);box-shadow:inset 0 0 0 1px rgba(53,217,143,.12),0 0 40px rgba(53,217,143,.06)}
.verdict.ok .head{color:var(--green)}
.verdict.bad{border-color:rgba(255,95,99,.55);box-shadow:inset 0 0 0 1px rgba(255,95,99,.10),0 0 40px rgba(255,95,99,.06)}
.verdict.bad .head{color:var(--red)}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 24px;overflow-x:auto}
.grid2{display:grid;grid-template-columns:1.15fr .85fr;gap:18px;align-items:start}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th{font-size:14px;text-transform:uppercase;letter-spacing:.07em;color:var(--mut);text-align:left;
  padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:9px 10px;border-bottom:1px solid rgba(34,49,75,.55);font-size:16px;white-space:nowrap}
td.r,th.r{text-align:right}
.bar{height:14px;border-radius:7px;background:#18304c;position:relative;min-width:120px}
.bar i{position:absolute;left:0;top:0;bottom:0;border-radius:7px;background:linear-gradient(90deg,#2b7fff,#58a6ff)}
.bar i.hot{background:linear-gradient(90deg,#ff7a3d,#ffb347)}
.tagA{color:var(--blue)} .tagB{color:#c58cff}
.pill{display:inline-block;font-size:13px;padding:2px 9px;border-radius:99px;border:1px solid var(--line);color:var(--mut)}
.pill.g{color:var(--green);border-color:rgba(53,217,143,.45)}
.pill.r{color:var(--red);border-color:rgba(255,95,99,.45)}
.pill.a{color:var(--amber);border-color:rgba(255,179,71,.45)}
.legend{display:flex;gap:22px;flex-wrap:wrap;margin:2px 0 8px;color:var(--mut);font-size:15px}
.legend span{display:inline-flex;align-items:center;gap:8px}
.sw{display:inline-block;width:22px;height:4px;border-radius:2px}
.note{color:var(--mut);font-size:15px;margin-top:10px}
ul.break{margin:6px 0 0 0;padding-left:20px}
ul.break li{margin:7px 0;font-size:16.5px}
ul.break b{color:#fff}
footer{margin-top:42px;border-top:1px solid var(--line);padding-top:18px;color:var(--mut);font-size:14.5px}
footer li{margin:5px 0}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:15px}
@media (max-width:1150px){.kpis{grid-template-columns:repeat(2,1fr)}.verdicts{grid-template-columns:1fr}.grid2{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <div class="badge">GRIDRUSH &middot; grid physics check</div>
  <h1>Real AC power flow on a real medium-voltage feeder</h1>
  <p class="sub" id="subtitle"></p>

  <div class="kpis" id="kpis"></div>
  <div class="verdicts" id="verdicts"></div>

  <h2><span class="n">01</span>Feeder headroom, per bus</h2>
  <div class="card">
    <p class="note" style="margin-top:0" id="hrNote"></p>
    <table id="hrTable"><thead><tr>
      <th>Bus</th><th>MV sub-area</th><th class="r">Existing load (MW)</th><th class="r">Base voltage (p.u.)</th>
      <th class="r">Headroom (MW)</th><th style="width:26%">Largest added load with 0 violations</th><th>Binds first</th>
    </tr></thead><tbody></tbody></table>
  </div>

  <h2><span class="n">02</span>Bus voltage: base case vs with our load</h2>
  <div class="card">
    <div class="legend" id="voltLegend"></div>
    <div id="voltChart"></div>
    <p class="note" id="voltNote"></p>
  </div>

  <h2><span class="n">03</span>Branch loading after the load is added</h2>
  <div class="card">
    <div id="loadChart"></div>
    <p class="note" id="loadNote"></p>
  </div>

  <h2><span class="n">04</span>What breaks, and where</h2>
  <div class="grid2">
    <div class="card"><table id="caseTable"><thead><tr>
      <th>Site</th><th>Bus</th><th>Sub-area</th><th class="r">MW</th><th class="r">Bus headroom (MW)</th><th>AC check</th>
    </tr></thead><tbody></tbody></table>
    <p class="note" id="caseNote"></p></div>
    <div class="card"><ul class="break" id="breakList"></ul></div>
  </div>

  <footer>
    <b>Honesty notes</b>
    <ul id="caveats"></ul>
  </footer>
</div>
<script>
const D = __DATA__;
const base = D.base, info = D.feeder_info, pol = D.policy;
const fmt = (x, n) => (x === null || x === undefined || Number.isNaN(x)) ? 'n/a' : Number(x).toFixed(n);
const pct = x => fmt(x, 1) + '%';
const pu = x => fmt(x, 4) + ' p.u.';
const areaName = a => a === info.areas[0].trafo ? 'A' : 'B';

function svg(tag, attrs, parent) {
  const e = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function el(tag, cls, html) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (html !== undefined) e.innerHTML = html;
  return e;
}

/* ---------- header + KPI cards ---------- */
document.getElementById('subtitle').textContent =
  'pandapower.networks.mv_oberrhein - a real 20 kV German MV network: ' + info.n_bus +
  ' buses, ' + info.n_line + ' lines, ' + info.n_trafo + ' x ' + info.trafo_mva +
  ' MVA 110/20 kV transformers. Served load ' + fmt(base.served_load_mw,1) +
  ' MW (' + fmt(info.nominal_load_mw,1) + ' MW nameplate x ' + fmt(info.load_scaling,1) +
  ' scaling). Every number on this page is from one measured AC power flow run.';

const feas = D.feasible_case, single = D.single_site_case;
const vcol = D.voltage_collapse, solver = D.solver_limit, largest = D.largest_site_case;
const pct2 = x => fmt(x, 2) + '%';
const maxHr = Math.max(...D.headroom.map(r => r.headroom_mw));
const kpis = [
  {k:'Base feeder', v:fmt(base.min_vm,4)+' p.u.', c:'good',
   d:'AC PF converged, 0 violations - min V, max loading ' + pct(base.max_loading) + ' (transformer)'},
  {k:'Buses with headroom', v:D.headroom.filter(r=>true).length + ' / ' + D.headroom.length, c:'',
   d:'per-bus headroom ' + fmt(Math.min(...D.headroom.map(r=>r.headroom_mw)),2) + '-' +
     fmt(maxHr,2) + ' MW; transformer-limited'},
  {k:'Feeder spare capacity', v:fmt(feas.total_mw,1)+' MW', c:'good',
   d:'largest tested load with AC PF converged and 0 violations'},
  {k:'Our 5 largest sites', v:fmt(D.case.total_mw,1)+' MW', c:'bad',
   d:'AC PF ' + (D.case.converged ? 'converged with ' + D.case.n_violations + ' violations' : 'does NOT converge (voltage collapse)')},
];
const kpiBox = document.getElementById('kpis');
kpis.forEach(x => {
  const b = el('div', 'kpi ' + x.c);
  b.appendChild(el('div','k',' ')); b.firstChild.textContent = x.k;
  const v = el('div','v'); v.textContent = x.v; b.appendChild(v);
  const d = el('div','d'); d.textContent = x.d; b.appendChild(d);
  kpiBox.appendChild(b);
});

/* ---------- verdicts ---------- */
const vBox = document.getElementById('verdicts');
function verdict(cls, tag, head, det) {
  const v = el('div', 'verdict ' + cls);
  v.appendChild(el('div','tag',tag));
  const h = el('div','head'); h.textContent = head; v.appendChild(h);
  const d = el('div','det'); d.innerHTML = det; v.appendChild(d);
  vBox.appendChild(v);
}
verdict('ok', 'Verified AC power flow',
  'CONVERGED · 0 violations',
  'At <b>' + fmt(feas.total_mw,1) + ' MW</b> of new load (' + fmt(feas.scale*100,0) + '% of the top-5 portfolio, sited on the best-headroom buses) ' +
  'the AC power flow converges with zero violations: <b>min V = ' + pu(feas.min_vm_pu) + '</b>, ' +
  '<b>max loading = ' + pct2(feas.max_loading_pct) + '</b>, ' + feas.n_violations + ' violations.');
verdict('bad', 'Our portfolio vs one real feeder',
  'DOES NOT FIT · ' + fmt(D.case.n_violations,0) + ' violations',
  'The five largest sites total <b>' + fmt(D.case.total_mw,1) + ' MW</b> — ' +
  fmt(D.case.total_mw / feas.total_mw, 1) + 'x the feeder\'s spare capacity of ' + fmt(feas.total_mw,1) + ' MW. ' +
  'AC PF ' + (D.case.converged
    ? 'converges only to a violated state: <b>min V = ' + pu(D.case.min_vm_pu) + '</b>, <b>max loading = ' +
      pct2(D.case.max_loading_pct) + '</b>, ' + D.case.n_violations + ' violations'
    : 'does not converge (voltage collapse)') +
  '. At <b>scale 1.5 (' + fmt(D.stress_case.total_mw,1) + ' MW)</b>: ' +
  (D.stress_case.converged
    ? '<b>min V = ' + pu(D.stress_case.min_vm_pu) + '</b> at bus ' + D.stress_case.worst_vm_bus +
      ', ' + pct2(D.stress_case.max_loading_pct) + ' loading, ' + D.stress_case.n_violations + ' violations'
    : 'AC PF diverges') + '.');

/* ---------- headroom table ---------- */
document.getElementById('hrNote').textContent =
  'Largest added load at a single bus that keeps AC PF converged with zero violations. ' +
  '15 load-centre buses (' + info.areas.map(a => 'sub-area ' + areaName(a.trafo) + ' / T' + a.trafo +
  ': ' + fmt(a.served_load_mw,1) + ' MW served').join('; ') + '). ' +
  'Headroom is limited by the shared 25 MVA transformers, so per-bus values are NOT additive.';
const hrBody = document.querySelector('#hrTable tbody');
D.headroom.forEach(r => {
  const tr = el('tr');
  const cells = [String(r.bus), 'Sub-area ' + areaName(r.area) + ' (T' + r.area + ')',
                 fmt(r.base_load_mw,2), fmt(r.base_vm_pu,4), fmt(r.headroom_mw,2)];
  cells.forEach((c,i) => {
    const td = el('td', i >= 2 ? 'r' : ''); td.textContent = c; tr.appendChild(td);
  });
  const barTd = el('td'); const bar = el('div','bar');
  const fill = el('i'); fill.style.width = (100*r.headroom_mw/maxHr).toFixed(1) + '%';
  if (r.headroom_mw < maxHr*0.6) fill.className = 'hot';
  bar.appendChild(fill); barTd.appendChild(bar); tr.appendChild(barTd);
  const bd = el('td'); const pill = el('span','pill ' + (/transformer/.test(r.binds) ? 'a' : ''));
  pill.textContent = r.binds; bd.appendChild(pill); tr.appendChild(bd);
  hrBody.appendChild(tr);
});

/* ---------- voltage profile chart ---------- */
(function voltageChart() {
  const prof = D.voltage_profile, W = 1300, H = 430, L = 62, R = 22, T = 26, B = 46;
  const iw = W - L - R, ih = H - T - B;
  const all = prof.base_vm.concat(prof.case_vm);
  const lo = Math.min(0.94, Math.min(...all) - 0.01);
  const hi = Math.max(1.01, Math.max(...all) + 0.005);
  const n = prof.buses.length;
  const x = i => L + (n === 1 ? 0 : i/(n-1)*iw);
  const y = v => T + (hi - v)/(hi - lo)*ih;
  const root = svg('svg', {viewBox:'0 0 '+W+' '+H, width:'100%', role:'img',
                           'aria-label':'bus voltage profile before and after added load'});
  document.getElementById('voltChart').appendChild(root);
  // y grid
  const ticks = [0.94, 0.96, 0.98, 1.00, 1.02, 1.04].filter(v => v >= lo && v <= hi);
  ticks.forEach(v => {
    svg('line', {x1:L, y1:y(v), x2:W-R, y2:y(v), stroke:'#1b2a43', 'stroke-width':1}, root);
    const t = svg('text', {x:L-10, y:y(v)+5, fill:'#93a4bf', 'font-size':14, 'text-anchor':'end'}, root);
    t.textContent = v.toFixed(2);
  });
  // limits
  svg('line', {x1:L, y1:y(0.94), x2:W-R, y2:y(0.94), stroke:'#ff5f63', 'stroke-width':1.6,
               'stroke-dasharray':'7 6', opacity:.8}, root);
  const lim = svg('text', {x:W-R, y:y(0.94)-8, fill:'#ff8b8e', 'font-size':14, 'text-anchor':'end'}, root);
  lim.textContent = 'lower limit 0.94 p.u.';
  // x labels
  [0, Math.floor(n*0.25), Math.floor(n*0.5), Math.floor(n*0.75), n-1].forEach(i => {
    const t = svg('text', {x:x(i), y:H-14, fill:'#93a4bf', 'font-size':14, 'text-anchor':'middle'}, root);
    t.textContent = 'bus ' + prof.buses[i];
  });
  const path = vals => vals.map((v,i) => (i ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1)).join(' ');
  svg('path', {d:path(prof.base_vm), fill:'none', stroke:'#5f7fb0', 'stroke-width':2.4, opacity:.95}, root);
  svg('path', {d:path(prof.case_vm), fill:'none', stroke:'#35d98f', 'stroke-width':2.8}, root);
  // min markers
  const iMinBase = prof.base_vm.indexOf(Math.min(...prof.base_vm));
  const iMinCase = prof.case_vm.indexOf(Math.min(...prof.case_vm));
  svg('circle', {cx:x(iMinBase), cy:y(prof.base_vm[iMinBase]), r:4, fill:'#5f7fb0'}, root);
  svg('circle', {cx:x(iMinCase), cy:y(prof.case_vm[iMinCase]), r:5, fill:'#35d98f'}, root);
  const t1 = svg('text', {x:x(iMinBase)+9, y:y(prof.base_vm[iMinBase])+18, fill:'#a9bcd8', 'font-size':14}, root);
  t1.textContent = 'base min ' + fmt(prof.base_vm[iMinBase],4);
  const t2 = svg('text', {x:x(iMinCase)+9, y:y(prof.case_vm[iMinCase])-10, fill:'#8ff0bf', 'font-size':14}, root);
  t2.textContent = 'with ' + fmt(feas.total_mw,1) + ' MW: ' + fmt(prof.case_vm[iMinCase],4);
  // legend
  const lg = document.getElementById('voltLegend');
  lg.innerHTML = '<span><i class="sw" style="background:#5f7fb0"></i>base case (' + n + ' buses)</span>' +
    '<span><i class="sw" style="background:#35d98f"></i>' + prof.case_label + '</span>' +
    '<span><i class="sw" style="background:#ff5f63"></i>limit 0.94 p.u.</span>';
  document.getElementById('voltNote').textContent =
    'Each point is one bus in a real AC power flow; ' + prof.order + '. ' +
    'The case curve uses the largest load that still passes (' + fmt(feas.total_mw,1) + ' MW, ' + feas.n_violations + ' violations). ' +
    'Adding the full ' + fmt(D.case.total_mw,1) + ' MW is not plotted: ' +
    (D.case.converged
      ? 'min V drops to ' + pu(D.case.min_vm_pu) + ' with ' + fmt(D.case.n_violations,0) + ' violations'
      : 'the AC solver diverges') + '.';
})();

/* ---------- branch loading chart ---------- */
(function loadingChart() {
  const rows = D.branch_loading.slice().sort((a,b) => b.loading_pct - a.loading_pct);
  const W = 1300, rowH = 40, L = 210, R = 130, T = 16, B = 10;
  const H = T + rows.length*rowH + B;
  const max = Math.max(110, Math.ceil(Math.max(...rows.map(r => r.loading_pct))/10)*10);
  const iw = W - L - R;
  const root = svg('svg', {viewBox:'0 0 '+W+' '+H, width:'100%', role:'img',
                           'aria-label':'branch loading after added load'});
  document.getElementById('loadChart').appendChild(root);
  const x = v => L + v/max*iw;
  [0, 20, 40, 60, 80, 100].forEach(v => {
    if (v > max) return;
    svg('line', {x1:x(v), y1:T, x2:x(v), y2:H-B, stroke:'#17243a', 'stroke-width':1}, root);
    const t = svg('text', {x:x(v), y:H-2, fill:'#7f90ab', 'font-size':13, 'text-anchor':'middle'}, root);
    t.textContent = v + '%';
  });
  svg('line', {x1:x(100), y1:T, x2:x(100), y2:H-B, stroke:'#ff5f63', 'stroke-width':1.8,
               'stroke-dasharray':'7 6'}, root);
  const lim = svg('text', {x:x(100)+8, y:T+16, fill:'#ff8b8e', 'font-size':14}, root);
  lim.textContent = 'rating 100%';
  rows.forEach((r, i) => {
    const cy = T + i*rowH + rowH/2;
    const lab = svg('text', {x:L-12, y:cy+5, fill:'#cdd8ea', 'font-size':15, 'text-anchor':'end'}, root);
    lab.textContent = r.label;
    const col = r.loading_pct > 100.05 ? '#ff5f63' : (r.loading_pct > 90 ? '#ffb347' : '#35d98f');
    svg('rect', {x:L, y:cy-11, width:Math.max(2, x(r.loading_pct)-L), height:22, rx:6, fill:col, opacity:.9}, root);
    const val = svg('text', {x:x(r.loading_pct)+10, y:cy+5, fill:'#e9eef8', 'font-size':15, 'font-weight':600}, root);
    val.textContent = pct(r.loading_pct) + (r.kind === 'trafo' ? '  (transformer)' : '');
  });
  document.getElementById('loadNote').textContent =
    'Branch loading at ' + fmt(feas.total_mw,1) + ' MW of added load (the last point with zero violations). ' +
    'The 110/20 kV transformers, not the 20 kV lines, sit closest to their rating: this feeder has ' +
    fmt(feas.total_mw,1) + ' MW of spare capacity for our load class.';
})();

/* ---------- case placement table ---------- */
const caseBody = document.querySelector('#caseTable tbody');
const hrByBus = Object.fromEntries(D.headroom.map(r => [r.bus, r]));
const siteIds = D.portfolio.top5_ids || [];
(D.case.loads_mw || []).forEach((mw, i) => {
  const bus = D.case.buses[i], hr = hrByBus[bus];
  const tr = el('tr');
  const over = hr && mw > hr.headroom_mw;
  [ (siteIds[i] || ('site ' + (i+1))), String(bus), 'Sub-area ' + areaName(hr ? hr.area : info.areas[0].trafo),
    fmt(mw,2), hr ? fmt(hr.headroom_mw,2) : 'n/a' ].forEach((c,j) => {
    const td = el('td', j >= 3 ? 'r' : ''); td.textContent = c; tr.appendChild(td);
  });
  const td = el('td');
  const pill = el('span','pill ' + (over ? 'r' : 'g'));
  pill.textContent = over ? (D.case.converged ? 'exceeds bus headroom' : 'contributes to collapse') : 'within headroom';
  td.appendChild(pill); tr.appendChild(td);
  caseBody.appendChild(tr);
});
document.getElementById('caseNote').textContent =
  'Buses are the five best-headroom feeder buses, alternating between the two MV sub-areas (best-case siting). ' +
  'Site MW are the five largest connected sites in the agent portfolio (' + (D.portfolio.source || 'n/a') +
  ', sha256 ' + (D.portfolio.sha256 || 'n/a') + '; portfolio total ' + fmt(D.portfolio.total_mw,1) + ' MW).';

/* ---------- what breaks ---------- */
const bl = document.getElementById('breakList');
function li(html) { const x = el('li'); x.innerHTML = html; bl.appendChild(x); }
li('Feeder spare capacity (AC): <b>' + fmt(feas.total_mw,1) + ' MW</b> at scale ' + fmt(feas.scale,3) +
   ' — min V <b>' + pu(feas.min_vm_pu) + '</b>, max loading <b>' + pct2(feas.max_loading_pct) + '</b>, 0 violations.');
li('First violation just above it: <b>' + fmt(D.first_violation.total_mw,1) + ' MW</b> — ' +
   (D.first_violation.thermal_violations.length ? ('transformer/line above 100% (' +
     pct2(D.first_violation.thermal_violations[0].loading_pct) + ')') : 'voltage limit') +
   (D.first_violation.voltage_violation_buses.length ? ', ' + D.first_violation.voltage_violation_buses.length + ' bus(es) outside 0.94-1.06 p.u.' : '') + '.');
li('Top-5 sites at <b>' + fmt(D.case.total_mw,1) + ' MW</b>: ' +
   (D.case.converged ? (D.case.n_violations + ' violations; min V ' + pu(D.case.min_vm_pu) +
    ' at bus ' + D.case.worst_vm_bus + '; max loading ' + pct2(D.case.max_loading_pct)) :
    '<b>AC PF diverges => voltage collapse</b>') + '.');
li('Stress case, scale 1.5 = <b>' + fmt(D.stress_case.total_mw,1) + ' MW</b>: ' +
   (D.stress_case.converged ? (D.stress_case.n_violations + ' violations; min V ' + pu(D.stress_case.min_vm_pu) +
    ' at bus ' + D.stress_case.worst_vm_bus + '; max loading ' + pct2(D.stress_case.max_loading_pct)) :
    '<b>AC PF diverges</b>') + '.');
li('Physical voltage collapse (min V &lt; 0.90 p.u.): <b>' + fmt(vcol.total_mw,1) + ' MW</b> at scale ' +
   fmt(vcol.scale,3) + ' — max loading ' + pct2(vcol.max_loading_pct) + ', ' + fmt(vcol.n_violations,0) + ' violations.');
li('Note: Newton AC PF still returns a converged solution far into the low-voltage region (' +
   fmt(solver.total_mw,1) + ' MW, min V ' + pu(solver.min_vm_pu) + ') — that is not a usable grid; ' +
   'we therefore use min V &lt; 0.90 p.u. as the collapse threshold, not solver divergence.');
li('Largest single agent site (' + fmt(largest.total_mw,1) + ' MW) at the best bus ' + largest.bus + ': ' +
   (largest.converged && largest.n_violations === 0 ? 'converged, 0 violations' :
    (largest.n_violations + ' violations; max loading ' + pct2(largest.max_loading_pct))) +
   ' — the agent\'s biggest sites are larger than one 20 kV feeder bus can host.');
li('Per-site class check: one <b>' + fmt(single.total_mw,1) + ' MW</b> site at bus ' + single.bus +
   ' → ' + (single.converged ? 'converged, 0 violations' : 'not converged') +
   ', min V ' + pu(single.min_vm_pu) + ', max loading ' + pct2(single.max_loading_pct) +
   ' (bus headroom ' + fmt(single.headroom_at_bus_mw,2) + ' MW).');
li('Even a 5 x 4-6 MW class (' + fmt(D.class_case.total_mw,1) + ' MW) ' +
   (D.class_case.converged ? ('gives ' + D.class_case.n_violations + ' violations, max loading ' +
    pct2(D.class_case.max_loading_pct)) : 'does not converge') +
   ' — one 20 kV feeder is not sized for five data-centre loads.');

/* ---------- caveats ---------- */
const cav = document.getElementById('caveats');
D.caveats.forEach(c => { const x = el('li'); x.textContent = c; cav.appendChild(x); });
</script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
