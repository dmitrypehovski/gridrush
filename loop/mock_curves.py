"""DEV-ONLY: мок кривых и упрощённый evaluator, чтобы валидировать луп до готовности sim/.
После интеграции loop/run.py использует sim.curves.site_curves + sim.engine.evaluate.
Эти числа НЕ идут в демо.
"""
from __future__ import annotations

import numpy as np

HORIZON = 36
REV = 0.10           # $M / MW·месяц (базовая цена, SLA даёт множитель)
BAT_MW = 0.35
BAT_MWH = 0.25
SLA_PENALTY = 5.0    # × revenue за MW·ч сверх бюджета
SLA_BUDGET = {0.9999: 0.876, 0.999: 8.76, 0.99: 87.6}
SLA_MULT = {0.9999: 1.25, 0.999: 1.0, 0.99: 0.80}


def _nearest_sla(sla: float) -> float:
    return min(SLA_BUDGET, key=lambda k: abs(k - sla))


def make_mock(seed: int = 7, n_sub: int = 8, per_sub: int = 5) -> dict:
    rng = np.random.default_rng(seed)
    H = 8760
    hours = np.arange(H)
    hour_of_day = hours % 24
    day = hours // 24
    daily = 0.55 + 0.45 * np.exp(-0.5 * ((hour_of_day - 19.0) / 3.2) ** 2) - 0.12 * np.exp(
        -0.5 * ((hour_of_day - 4.0) / 3.0) ** 2)
    seasonal = 1.0 + 0.28 * np.cos(2 * np.pi * (day - 200) / 365)
    solar = np.clip(np.exp(-0.5 * ((hour_of_day - 12.5) / 2.6) ** 2) * seasonal, 0, None) * 0.5
    u = daily * seasonal
    u = u / np.percentile(u, 95)
    cap = rng.uniform(10, 60, n_sub)
    lf = rng.uniform(0.55, 0.95, n_sub)
    e = lf[:, None] * cap[:, None] * u[None, :]
    sub_idx = np.repeat(np.arange(n_sub), per_sub)
    n = len(sub_idx)
    Hm = np.stack([cap[sub_idx[i]] - e[sub_idx[i]] - 0.02 * cap[sub_idx[i]] for i in range(n)])
    ids = [f"S{int(sub_idx[i]) + 1:02d}-{i % per_sub + 1}" for i in range(n)]
    T_flex = rng.uniform(5, 10, n)
    T_on = T_flex + rng.uniform(1.0, 3.0, n)
    curves = {
        "ids": ids,
        "sub_idx": sub_idx,
        "max_mw": rng.uniform(0.5, 10.0, n),
        "cap_mw": cap,
        "e": e,
        "H": Hm,
        "T_firm": rng.uniform(18, 36, n),
        "T_flex": T_flex,
        "T_on": T_on,

        "fiber": rng.uniform(0, 1, n),
        "permit_days": rng.uniform(30, 400, n),
        "stress_hours": (Hm < 2.0).sum(axis=1).astype(float),
        "u": u,
        "solar": solar,
        "region": "MOCK",
    }
    return curves


def mock_evaluate(curves: dict, portfolio: list[dict]) -> dict:
    """Упрощённый verifier: считает, что реально достанется сети и сколько потеряно."""
    Hm = np.asarray(curves["H"])
    n = len(curves["ids"])
    idx = {sid: i for i, sid in enumerate(curves["ids"])}
    cap_use = {int(s): np.zeros(8760) for s in np.unique(curves["sub_idx"])}
    delivered = 0.0
    mw12 = 0.0
    capex = 0.0
    sla_breach = 0.0
    curtail_energy = 0.0
    monthly = np.zeros(HORIZON)
    rev_weighted_delivered = 0.0
    details = []
    for item in portfolio:
        i = idx[item["site_id"]]
        if item["mode"] == "skip" or item["mw"] <= 0:
            continue
        s = int(curves["sub_idx"][i])
        mw = float(item["mw"])
        sla = _nearest_sla(float(item["sla"]))
        budget = SLA_BUDGET[sla]
        rev_mult = SLA_MULT[sla]
        R = np.maximum(0.0, Hm[i] - cap_use[s])
        if item["mode"] == "firm":
            served = mw
            cap_use[s] += mw
        elif item["mode"] == "battery":
            served = mw
            deficit = np.maximum(0.0, mw - R)
            bat = float(item.get("battery_mwh", 0.0))
            covered = min(float(deficit.sum()), bat)
            curtail_energy += float(deficit.sum()) - covered
            capex += BAT_MW * mw + BAT_MWH * bat
            cap_use[s] += np.minimum(mw, R)
            served_hours = 8760.0
        else:
            served_hours = float((R >= mw).sum()) + 0.0
            cap_use[s] += np.minimum(mw, R)
            deficit = np.maximum(0.0, mw - R)
            curtail_energy += float(deficit.sum())
        if item["mode"] == "firm":
            avail = 1.0
        else:
            avail = served_hours / 8760.0
        days_curt = (1 - avail) * 8760.0
        if days_curt > budget:
            sla_breach += (days_curt - budget) * mw * (REV / 730.0) * SLA_PENALTY
        T = {"firm": curves["T_firm"][i], "flex": curves["T_flex"][i], "battery": curves["T_on"][i]}[item["mode"]]
        mon = max(0.0, HORIZON - float(T))
        delivered += mw * mon * avail
        rev_weighted_delivered += mw * mon * avail * SLA_MULT[_nearest_sla(float(item["sla"]))]
        if mon > 0:
            mw12 += mw * avail if float(T) <= 12 else 0.0
        start = int(np.ceil(T))
        for m in range(start, HORIZON):
            monthly[m] += mw * avail
        details.append({"site_id": item["site_id"], "mode": item["mode"], "mw": mw, "sla": sla,
                        "energize_month": int(T), "avail": round(avail, 5),
                        "curtail_hours": round((1 - avail) * 8760.0, 1),
                        "battery_mwh": item.get("battery_mwh", 0.0)})
    net = rev_weighted_delivered * REV - capex - sla_breach
    score = net
    return {
        "score": float(score), "delivered_mwmonths": float(delivered),
        "rev_weighted_mwmonths": float(rev_weighted_delivered),
        "mw_at_month12": float(mw12), "net_value_musd": float(net),
        "violations_mwh": 0.0, "sla_breach_mwh": float(sla_breach), "capex_musd": float(capex),
        "monthly_mw": [round(float(v), 2) for v in monthly],
        "sites": details,
    }
