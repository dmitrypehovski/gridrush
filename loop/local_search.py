"""GRIDRUSH — локальный поиск: вторая половина RSI-лупа.

Параметрический мутатор (`search.hill_climb`) находит хорошую *глобальную* политику, но
она грубая: компромиссы между MW / SLA / батареей на каждом сайте решаются эвристикой.
Здесь агент делает то, что делает настоящий инженер: берёт текущий портфель, для каждого
сайта предлагает варианты (skip / flex / battery × MW × SLA × ёмкость батареи), и
**симулятор судит каждый вариант**. Принимается только то, что повышает score при
нулевых нарушениях сети и нулевом SLA-breach.

Каждый принятый шаг — это точка в кривой обучения (`iterations`), именно её видно на демо:
«предложил → проверил → стало лучше».

Стоимость: ~6000 вызовов evaluate() по 3.7 мс ≈ 20–25 с. Это осознанный trade-off:
качество финального портфеля важнее времени прогона.
"""
from __future__ import annotations

import copy

import numpy as np

MIN_MW = 0.5
SLA_LEVELS = (0.9999, 0.999, 0.99)


def _mw_grid(cap_mw: float) -> list[float]:
    """Сетка кандидатных MW для сайта: половина того, что физически влезает."""
    cap = float(max(0.0, cap_mw))
    if cap < MIN_MW:
        return []
    vals = []
    mw = MIN_MW
    while mw <= cap + 1e-9 and len(vals) < 14:
        vals.append(round(mw, 2))
        step = 0.5 if mw < 2.0 else (1.0 if mw < 5.0 else 1.5)
        mw += step
    if cap not in vals and cap >= MIN_MW:
        vals.append(round(cap, 2))
    return vals


def _candidates(curves, i: int, mw_grid: list[float]) -> list[dict]:
    sid = curves["ids"][i]
    out = [{"site_id": sid, "mode": "skip", "mw": 0.0, "sla": 0.999, "battery_mwh": 0.0}]
    for mw in mw_grid:
        out.append({"site_id": sid, "mode": "firm", "mw": mw, "sla": 0.9999, "battery_mwh": 0.0})
        for sla in SLA_LEVELS:
            out.append({"site_id": sid, "mode": "flex", "mw": mw, "sla": sla, "battery_mwh": 0.0})
        for bat_mult in (2.0, 4.0):
            out.append({"site_id": sid, "mode": "battery", "mw": mw, "sla": 0.9999,
                        "battery_mwh": round(bat_mult * mw, 2)})
    return out


def _is_valid(r: dict) -> bool:
    return float(r.get("violations_mwh", 0.0)) <= 1e-6 and float(r.get("sla_breach_mwh", 0.0)) <= 1e-6


def local_search(curves, evaluate_fn, portfolio, max_evals: int = 7000,
                 sweeps: int = 3, verbose: bool = True, log: list | None = None,
                 on_step=None) -> dict:
    """Улучшает портфель жадным покоординатным поиском с симулятором в роли судьи.

    Возвращает {"portfolio","result","steps","n_evals","wall_s"}.
    `steps` — принятые улучшения (для кривой обучения).
    """
    import time
    t0 = time.time()
    cur = copy.deepcopy([p for p in portfolio if p.get("mode") != "skip"
                         and float(p.get("mw", 0.0)) > 0])
    cur_res = evaluate_fn(cur)
    n_evals = 1
    steps: list[dict] = []
    mw_grids = {i: _mw_grid(min(float(curves["max_mw"][i]), float(np.max(curves["H"][i]))))
                for i in range(len(curves["ids"]))}
    order = sorted(range(len(curves["ids"])),
                   key=lambda i: -(float(np.max(curves["H"][i])) + 0.5 * float(curves["max_mw"][i])))

    for sweep in range(sweeps):
        improved = False
        for i in order:
            sid = curves["ids"][i]
            base = [p for p in cur if p.get("site_id") != sid]
            base_res = evaluate_fn(base) if not base else cur_res
            n_evals += 0 if not base else 1
            best_res, best_item, best_score = None, None, float(cur_res["score"])
            for cand in _candidates(curves, i, mw_grids[i]):
                trial = base + [cand] if cand["mode"] != "skip" else base
                # исключаем очевидно текущий вариант, чтобы не тратить вызовы
                if cand["mode"] != "skip" and any(
                        p.get("site_id") == sid and p.get("mode") == cand["mode"]
                        and abs(float(p.get("mw", 0)) - cand["mw"]) < 1e-9
                        and abs(float(p.get("sla", 0)) - cand["sla"]) < 1e-9
                        and abs(float(p.get("battery_mwh", 0)) - cand["battery_mwh"]) < 1e-9
                        for p in cur):
                    continue
                r = evaluate_fn(trial)
                n_evals += 1
                if not _is_valid(r):
                    continue
                if float(r["score"]) > best_score + 1e-6:
                    best_score, best_res, best_item, best_trial = float(r["score"]), r, cand, trial
                if n_evals >= max_evals:
                    break
            if best_res is not None and best_item is not None:
                old_mw = next((float(p.get("mw", 0)) for p in cur if p.get("site_id") == sid), 0.0)
                cur, cur_res = best_trial, best_res
                improved = True
                steps.append({
                    "site": sid,
                    "change": f"{best_item['mode']} {best_item['mw']:.1f} MW @ SLA "
                              f"{best_item['sla']:.4f}"
                              + (f" + battery {best_item['battery_mwh']:.1f} MWh"
                                 if best_item["battery_mwh"] > 0 else ""),
                    "prev_mw": old_mw,
                    "score": round(float(best_res["score"]), 4),
                    "delivered_mwmonths": round(float(best_res["delivered_mwmonths"]), 2),
                    "mw_at_month12": round(float(best_res["mw_at_month12"]), 2),
                    "net_value_musd": round(float(best_res["net_value_musd"]), 3),
                    "n_active": len(cur),
                })
                if on_step is not None:
                    on_step({"phase": "local", "gen": len(steps) - 1, **steps[-1]})
                if verbose:
                    print(f"  local[{sweep}] {sid:7s} -> {steps[-1]['change']:42s} "
                          f"score={best_res['score']:8.2f}  net=${best_res['net_value_musd']:.1f}M")
            if n_evals >= max_evals:
                break
        if not improved or n_evals >= max_evals:
            break

    if log is not None:
        log.extend(steps)
    return {"portfolio": cur, "result": cur_res, "steps": steps,
            "n_evals": n_evals, "wall_s": round(time.time() - t0, 2)}
