"""GRIDRUSH — RSI loop: proposer -> evaluator -> archive -> better.

This is the agentic loop the event asked for: "agents that do that testing and get
better at it each run". The proposer is a parametric mutator (fast, 150+ iterations
in seconds); next to it, rsi_agent/ holds the LLM-in-the-loop log where an agent
writing policy code plays the same role (see README).

Each iteration: mutate the parameter vector -> build a portfolio -> sim.evaluate() ->
compare the score -> keep the better one. The log feeds the "the agent learns" chart.
"""

from __future__ import annotations

import json
import time

import numpy as np

from .policy import D, build_portfolio


def evaluate_params(curves, evaluate_fn, params, sub_limit_mw=None) -> dict:
    portfolio = build_portfolio(curves, params, sub_limit_mw=sub_limit_mw)
    res = evaluate_fn(portfolio)
    res["portfolio"] = portfolio
    return res


def hill_climb(curves, evaluate_fn, n_iter: int = 220, seed: int = 0,
               init=None, verbose: bool = True, on_iter=None,
               sub_limit_mw=None) -> dict:
    """Simple (1+lambda) hill-climbing with an adaptive step and restarts.

    Returns {"best_params","best","iterations","history","n_evals","wall_s"}.
    """
    rng = np.random.default_rng(seed)
    t0 = time.time()

    def ev(x):
        return evaluate_params(curves, evaluate_fn, x, sub_limit_mw=sub_limit_mw)

    if init is None:
        # the agent starts "knowing nothing": a random point in policy space.
        # The learning curve is honest: from a bad portfolio to a good one.
        x = rng.random(D)
        cur = ev(x)
        init_name = "random"
    else:
        x = np.asarray(init, dtype=float)
        cur = ev(x)
        init_name = "custom"

    best_x, best = x.copy(), cur
    history = []
    iterations = []
    step = np.full(D, 0.22)
    no_improve = 0
    restarts = [0]
    for it in range(n_iter):
        cand = np.clip(x + rng.normal(0.0, step), 0.0, 1.0)
        cand_res = ev(cand)
        improved = cand_res["score"] > cur["score"] + 1e-9
        if improved:
            x, cur = cand, cand_res
            no_improve = 0
            step = np.minimum(step * 1.15, 0.35)
        else:
            no_improve += 1
            step = np.maximum(step * 0.97, 0.03)
        if cur["score"] > best["score"] + 1e-9:
            best_x, best = x.copy(), cur
        # restart when stuck
        if no_improve >= 45:
            restarts[0] += 1
            x = np.clip(best_x + rng.normal(0.0, 0.12, size=D), 0.0, 1.0)
            cur = ev(x)
            step = np.full(D, 0.18)
            no_improve = 0
        history.append({"iter": it, "candidate_score": round(float(cand_res["score"]), 4),
                        "current_score": round(float(cur["score"]), 4),
                        "best_score": round(float(best["score"]), 4),
                        "candidate_delivered": round(float(cand_res.get("delivered_mwmonths", 0.0)), 2),
                        "candidate_violations": round(float(cand_res.get("violations_mwh", 0.0)), 3)})
        iterations.append({"iter": it, "score": round(float(best["score"]), 4),
                           "delivered_mwmonths": round(float(best.get("delivered_mwmonths", 0.0)), 2),
                           "mw_at_month12": round(float(best.get("mw_at_month12", 0.0)), 2),
                           "violations_mwh": round(float(best.get("violations_mwh", 0.0)), 3),
                           "net_value_musd": round(float(best.get("net_value_musd", 0.0)), 3)})
        if on_iter is not None:
            on_iter({"phase": "parametric", "iter": it,
                     "score": round(float(best["score"]), 4),
                     "candidate_score": round(float(cand_res["score"]), 4),
                     "delivered_mwmonths": round(float(best.get("delivered_mwmonths", 0.0)), 2),
                     "mw_at_month12": round(float(best.get("mw_at_month12", 0.0)), 2),
                     "net_value_musd": round(float(best.get("net_value_musd", 0.0)), 3)})
        if verbose and (it % 20 == 0 or it == n_iter - 1):
            print(f"  iter {it:3d}  best_score={best['score']:9.3f}  "
                  f"delivered={best.get('delivered_mwmonths', 0):7.1f} MW·mo  "
                  f"viol={best.get('violations_mwh', 0):.2f}  step={step.mean():.3f}")

    best = dict(best)
    best.pop("portfolio", None)
    return {
        "best_params": best_params_list(best_x),
        "best_params_vector": [round(float(v), 5) for v in best_x],
        "best": best,
        "best_portfolio": build_portfolio(curves, best_x, sub_limit_mw=sub_limit_mw),
        "iterations": iterations,
        "history": history,
        "n_evals": n_iter + 1 + restarts[0],
        "wall_s": round(time.time() - t0, 2),
        "init_preset": init_name,
    }


def cur_portfolio_at(curves, evaluate_fn, x):
    return build_portfolio(curves, x)


def best_params_list(x) -> list[float]:
    return [round(float(v), 5) for v in x]


def save_log(path: str, log: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=1)
