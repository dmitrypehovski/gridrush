"""GRIDRUSH — RSI-луп: proposer → evaluator → архив → стало лучше.

Это тот самый «agentic loop», который просил ивент: «agents that do that testing and get
better at it each run». Здесь proposer — параметрический мутатор (быстрый, 150+ итераций
за секунды); рядом в rsi_agent/ лежит лог LLM-in-the-loop, где ту же роль играет агент,
пишущий код политики (см. README).

Каждая итерация: мутируем вектор параметров → строим портфель → sim.evaluate() →
сравниваем score → оставляем лучшее. Лог сохраняется для графика «агент учится».
"""

from __future__ import annotations

import json
import time

import numpy as np

from .policy import D, build_portfolio


def evaluate_params(curves, evaluate_fn, params) -> dict:
    portfolio = build_portfolio(curves, params)
    res = evaluate_fn(portfolio)
    res["portfolio"] = portfolio
    return res


def hill_climb(curves, evaluate_fn, n_iter: int = 220, seed: int = 0,
               init=None, verbose: bool = True, on_iter=None) -> dict:
    """Простой (1+λ) hill-climbing с адаптивным шагом и рестартом.

    Возвращает {"best_params","best","iterations","history","n_evals","wall_s"}.
    """
    rng = np.random.default_rng(seed)
    t0 = time.time()

    def ev(x):
        return evaluate_params(curves, evaluate_fn, x)

    if init is None:
        # агент стартует «незнающим»: случайная точка пространства политик.
        # Кривая обучения — честная: от плохого портфеля к хорошему.
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
        # рестарт при застое
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
        "best_portfolio": cur_portfolio_at(curves, evaluate_fn, best_x),
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
