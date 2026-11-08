"""GRIDRUSH — параметризованная политика «что подключать и как».

Политика получает кривые headroom по сайтам и их фичи, и возвращает портфель:
[{"site_id", "mode": "skip|firm|flex|battery", "mw", "sla", "battery_mwh"}]

Она НЕ считает прибыль окончательно — окончательный счёт даёт sim.engine.evaluate().
Политика — эвристика с 9 параметрами в [0,1], которые ищет луп.

Ключевая идея модели (CONTRACT §2):
- firm-мощность ограничена МИНИМУМОМ свободного headroom за год (нельзя куртейлить) → она
  маленькая и её ждут 18–36 месяцев;
- flex/step-up может взять МНОГО MW уже через 5–10 месяцев, но обязан снижать нагрузку в
  стресс-часы; сколько часов в год допустимо — это SLA сайта;
- SLA — это выбор с ценой: 99.99% (0.88 ч/год) платит премию ×1.25, 99.9% — ×1.0,
  99% (87.6 ч/год) — ×0.8 (со сцены: «за 6 nines платят премию»);
- батарея закрывает дефицит в стресс-часы, но стоит capex.

Поэтому политика — это торг: на «спокойных» сайтах берём 99.99% и много MW, на
перегруженных — либо меньше MW при высоком SLA, либо 99% и быстрые месяцы.
"""

from __future__ import annotations

import numpy as np

PARAM_NAMES = [
    "target_frac",   # какую долю max_mw сайта целимся подключить
    "sla_bias",      # сдвиг предпочтения SLA (ниже = жаднее к доступности)
    "speed_w",       # вес скорости подключения (раньше = ценнее)
    "firm_w",        # премия за firm (нет куртейлмента) / за надёжность
    "battery_w",     # готовность платить за батарею
    "risk_w",        # штраф за риск куртейлмента сверх цены SLA
    "size_w",        # предпочтение крупных сайтов
    "wait_w",        # штраф за долгое ожидание (общий, поверх speed)
    "sub_order",     # порядок подстанций: 0 = побольше headroom, 1 = поменьше стресса
]

D = len(PARAM_NAMES)

# Реальные параметры экономики (см. CONTRACT §1). $M.
REV_PER_MW_MONTH = 0.10
BAT_CAPEX_MW = 0.35
BAT_CAPEX_MWH = 0.25
HORIZON = 36.0

# (sla, допустимые часы куртейлмента в год, множитель цены compute)
SLA_LEVELS = [(0.9999, 0.876, 1.25), (0.999, 8.76, 1.00), (0.99, 87.6, 0.80)]
SLA_BY_INDEX = {lvl[0]: lvl for lvl in SLA_LEVELS}


def decode(p: np.ndarray) -> dict:
    """[0,1]^D → осмысленные параметры."""
    p = np.clip(np.asarray(p, dtype=float), 0.0, 1.0)
    return {
        "target_frac": 0.30 + 0.70 * p[0],
        "sla_bias": -1.0 + 2.0 * p[1],     # >0 → предпочитает высокий SLA
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
    """Вариант flex для КОНКРЕТНОГО уровня SLA.

    Возвращает {"mw","sla","budget","avail","k_hours"} или {} если нереально.
    """
    sla, budget_h, rev_mult = sla_level
    # sla_bias > 0 → урезаем допустимый куртейлмент (боимся риска)
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
    """Строит портфель жадно по подстанциям с общим остатком headroom.

    `sub_limit_mw` — необязательный жёсткий лимит суммарной НОВОЙ нагрузки на подстанцию.
    Если задан, конструктор никогда его не превышает, поэтому физическое ограничение
    (например, измеренный AC power-flow лимит фидера) действует внутри политики, а не
    наказывается постфактум. По умолчанию None — поведение прежнее.
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

        # --- FIRM: без куртейлмента, максимум по минимуму headroom за год.
        # 0.02 MW зазор, чтобы округления не дали violation в независимом verifier.
        firm_mw = float(min(target, max(0.0, R_sorted[0] - 0.02)))
        firm_mw = float(np.floor(firm_mw * 100.0) / 100.0)
        v_firm = -1e9
        if firm_mw >= min_mw:
            mon = max(0.0, HORIZON - float(T_firm[i]))
            v_firm = REV_PER_MW_MONTH * 1.25 * firm_mw * mon   # firm = 99.99%, премия
            v_firm *= 1.0 + par["speed_w"] * (mon / HORIZON)
            v_firm += par["firm_w"] * firm_mw * 2.0

        # --- FLEX: по каждому уровню SLA; учитываем скорость step-up
        v_flex, flex_mw, flex_sla, flex_avail = -1e9, 0.0, 0.999, 1.0
        mon_flex = max(0.0, HORIZON - float(T_flex[i]))
        for lvl in SLA_LEVELS:
            rev_mult = lvl[2]
            opt = _flex_option(R_sorted, target, par, lvl)
            if not opt:
                continue
            # пересчитываем value под этот SLA (в _flex_option он усреднён — сделаем явно)
            mw = opt["mw"]
            v = REV_PER_MW_MONTH * rev_mult * mw * mon_flex / HORIZON
            v *= 1.0 + par["speed_w"] * (mon_flex / HORIZON)
            v *= 1.0 + 0.25 * par["size_w"] * (mw / max(float(max_mw[i]), 1e-6))
            v -= par["risk_w"] * (1.0 - opt["avail"]) * 40.0 * mw
            if v > v_flex:
                v_flex, flex_mw, flex_sla, flex_avail = v, mw, opt["sla"], opt["avail"]

        # --- BATTERY: целевой MW, дефицит закрываем батареей (по самому дешёвому SLA)
        bat_mw = float(min(target, max(0.0, float(np.max(R)))))
        # engine: батарея имеет ДНЕВНОЙ бюджет энергии (0.9 * bat_mwh), а не годовой.
        # Поэтому нужна ёмкость под самый тяжёлый день.
        gap = np.clip(bat_mw - R, 0.0, None)
        days = min(365, len(gap) // 24)
        daily_gap = gap[: days * 24].reshape(days, 24).sum(axis=1) if days else gap.sum()
        deficit_mwh = float(np.max(daily_gap)) / 0.90
        bat_capex = (BAT_CAPEX_MW * bat_mw + BAT_CAPEX_MWH * deficit_mwh) * (
            0.6 + 1.4 * max(0.0, -par["battery_w"]))
        mon_on = max(0.0, HORIZON - float(T_on[i]))
        v_bat = -1e9
        # Батарея имеет смысл ТОЛЬКО если она реально закрывает стресс-часы,
        # которых не хватает для 99.99%. Иначе это flex с лишним capex — не берём.
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
            mode, bmwh = "flex", 0.0   # батарея ничего не закрывает -> обычный flex

        portfolio[i] = {"site_id": curves["ids"][i], "mode": mode, "mw": float(np.floor(mw * 100.0) / 100.0),
                        "sla": float(sla), "battery_mwh": round(float(bmwh), 2)}
        alloc_total[s] += portfolio[i]["mw"]
        if mode == "firm":
            remaining[s] = np.maximum(0.0, R - portfolio[i]["mw"])
        else:  # flex/battery: в стресс-часы забирают всё, что есть
            remaining[s] = np.where(R < portfolio[i]["mw"], 0.0, R - portfolio[i]["mw"])

    return repair_portfolio(curves, portfolio)


def _cover_daily(deficit: np.ndarray, daily_budget: float) -> np.ndarray:
    """Локальная копия логики движка: дневной бюджет батареи, худшие часы первыми."""
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
    """Доступность сайта при заданном MW (mimics engine allocation order)."""
    s = sub_rows[k]
    load = np.minimum(mw, np.maximum(0.0, cap_left[s]))
    deficit = np.clip(mw - load, 0.0, None)
    if bat_mwh > 0:
        deficit = np.clip(deficit - _cover_daily(deficit, 0.90 * bat_mwh), 0.0, None)
    avail = 1.0 - float((deficit > 1e-9).sum()) / 8760.0
    return avail, load


def repair_portfolio(curves: dict, portfolio: list[dict], verbose: bool = False) -> list[dict]:
    """Проверяет собственный план и ужимает MW, пока SLA каждого сайта не соблюдён.

    Это обязательный шаг: подстанция общая, и два flex-сайта на ней конкурируют за
    headroom в стресс-часы. Без repair план оптимистичен и часть MW не продаётся.
    Порядок — как в движке (по месяцу подключения), чтобы прогноз совпадал с проверкой.
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
    # firm не должен превышать минимум headroom подстанции
    for s in range(S):
        rows = np.flatnonzero(sub_rows == s)
        if rows.size:
            hmin = float(H_sub[s].min())
            if firm_total[s] > hmin:
                # ужимаем firm-сайты на этой подстанции пропорционально
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
