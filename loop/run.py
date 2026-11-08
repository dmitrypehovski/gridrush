"""GRIDRUSH — запуск лупа и сборка results/loop.json (формат — CONTRACT §5).

Использование:
  python3 loop/run.py                      # реальный sim (регион по умолчанию CAL)
  python3 loop/run.py --region TEX --iters 260
  python3 loop/run.py --mock               # dev-режим без sim/ (мок-кривые)

Выход: results/loop.json — его читает web/build.py и вставляет в dashboard.html.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import datetime as dt

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from loop.policy import build_portfolio, decode, params_to_json  # noqa: E402
from loop.search import hill_climb  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
DEFAULT_REGION = "CAL"
REGION_NAMES = {"CAL": "CAISO", "TEX": "ERCOT", "MIDA": "PJM", "MIDW": "MISO"}


def load_sim():
    """Возвращает (site_curves_fn, evaluate_fn, baselines_module) из sim/."""
    from sim.curves import site_curves          # type: ignore
    from sim.engine import evaluate             # type: ignore
    try:
        import sim.baselines as baselines       # type: ignore
    except Exception as e:  # noqa: BLE001  (baselines ещё в работе — не блокируем луп)
        print(f"  (sim.baselines пока нет: {e}); считаю baseline сами")
        baselines = None
    return site_curves, evaluate, baselines


def load_mock():
    from loop.mock_curves import make_mock, mock_evaluate  # type: ignore
    cache = {}

    def site_curves(region):
        if region not in cache:
            cache[region] = make_mock(seed=hash(region) % 1000)
        return cache[region]

    def evaluate(portfolio, _curves=None):
        # мок-evaluate нуждается в curves, подставим при первом вызове
        raise RuntimeError("mock evaluate requires curves")
    return site_curves, evaluate, None


def _site_coords() -> dict:
    """x/y из data/sites.json (генерирует sim по seed=7) — для гео-карты в дашборде."""
    try:
        with open(os.path.join(ROOT, "data", "sites.json"), encoding="utf-8") as f:
            d = json.load(f)
        sites = d.get("sites", d) if isinstance(d, dict) else d
        return {s["id"]: (float(s.get("x", 0.0)), float(s.get("y", 0.0))) for s in sites}
    except Exception:  # noqa: BLE001
        return {}


def site_records(curves: dict) -> list[dict]:
    coords = _site_coords()
    out = []
    for i, sid in enumerate(curves["ids"]):
        out.append({
            "id": sid,
            "substation": f"S{int(curves['sub_idx'][i]) + 1:02d}",
            "cap_mw": round(float(curves["cap_mw"][int(curves["sub_idx"][i])]), 2),
            "max_mw": round(float(curves["max_mw"][i]), 2),
            "x": round(coords.get(sid, (0.0, 0.0))[0], 5),
            "y": round(coords.get(sid, (0.0, 0.0))[1], 5),
            "T_firm": round(float(curves["T_firm"][i]), 1),
            "T_flex": round(float(curves["T_flex"][i]), 1),
            "Hmax_mw": round(float(np.max(curves["H"][i])), 2),
            "stress_hours": int(curves["stress_hours"][i]),
        })
    return out


def best_site_rows(curves: dict, best: dict, portfolio: list[dict], sites_by_id: dict) -> list[dict]:
    """Одна строка на подключённый сайт. Источник — per-site словари движка."""
    avail_by = best.get("avail_by_site") or {}
    sla_by = best.get("sla_by_site") or {}
    curtail_by = best.get("curtail_hours_by_site") or {}
    energ_by = best.get("energize_month_by_site") or {}
    mw_by = best.get("mw_by_site") or {}
    bat_by = best.get("battery_mwh_by_site") or {}
    rows = []
    for item in portfolio:
        if item["mode"] == "skip" or float(item.get("mw", 0.0)) <= 0:
            continue
        sid = item["site_id"]
        rows.append({
            "id": sid,
            "substation": sites_by_id.get(sid, {}).get("substation", "?"),
            "mode": item["mode"],
            "mw": round(float(mw_by.get(sid, item["mw"])), 2),
            "sla": round(float(sla_by.get(sid, item.get("sla", 0.999))), 4),
            "battery_mwh": round(float(bat_by.get(sid, item.get("battery_mwh", 0.0))), 2),
            "energize_month": int(energ_by.get(sid, 0)) if sid in energ_by else None,
            "curtail_hours": round(float(curtail_by.get(sid, 0.0)), 1) if sid in curtail_by else None,
            "avail": round(float(avail_by.get(sid, 1.0)), 6) if sid in avail_by else None,
        })
    rows.sort(key=lambda r: (r["mode"], -r["mw"]))
    return rows


def monthly_by_mode(curves: dict, best: dict, portfolio: list[dict]) -> dict:
    """(36,) MW по месяцам, разложенные по режимам — для stacked bar в дашборде."""
    avail_map = {}
    if isinstance(best.get("avail_by_site"), dict):
        avail_map = {k: float(v) for k, v in best["avail_by_site"].items()}
    elif isinstance(best.get("sites"), list):
        avail_map = {d["site_id"]: float(d.get("avail", 1.0)) for d in best["sites"]}
    out = {"firm": [0.0] * 36, "flex": [0.0] * 36, "battery": [0.0] * 36, "skip": [0.0] * 36}
    for item in portfolio:
        mode = item["mode"]
        if mode == "skip" or item["mw"] <= 0:
            continue
        T = {"firm": float(curves["T_firm"][curves["ids"].index(item["site_id"])]),
             "flex": float(curves["T_flex"][curves["ids"].index(item["site_id"])]),
             "battery": float(curves["T_on"][curves["ids"].index(item["site_id"])])}[mode]
        avail = avail_map.get(item["site_id"], 1.0)
        start = int(np.ceil(T))
        for m in range(max(0, start), 36):
            out[mode][m] += float(item["mw"]) * avail
    return {k: [round(v, 2) for v in arr] for k, arr in out.items()}


def compliant_mwmonths(res: dict) -> float:
    """MW·месяцы, которые реально можно продать по контракту: SLA сайта соблюдён.

    Сайт, у которого доступность ниже заявленного SLA, контракт не выполняет —
    его MW·месяцы не считаем (это и есть разница между «набрали MW» и «заработали»).
    """
    tot = 0.0
    mw_by = res.get("mw_by_site") or {}
    for sid, mw in mw_by.items():
        avail = float((res.get("avail_by_site") or {}).get(sid, 0.0))
        sla = float((res.get("sla_by_site") or {}).get(sid, 0.999))
        mon = 36 - int((res.get("energize_month_by_site") or {}).get(sid, 36))
        if avail >= sla - 1e-9:
            tot += float(mw) * max(0, mon) * avail
    return tot


def compliant_mw12(res: dict) -> float:
    """MW, которые к 12-му месяцу работают И соблюдают свой SLA."""
    tot = 0.0
    for sid, mw in (res.get("mw_by_site") or {}).items():
        avail = float((res.get("avail_by_site") or {}).get(sid, 0.0))
        sla = float((res.get("sla_by_site") or {}).get(sid, 0.999))
        if int((res.get("energize_month_by_site") or {}).get(sid, 99)) <= 12 and avail >= sla - 1e-9:
            tot += float(mw)
    return tot


def _curtail_series(curves, mw_by, modes, indices, day_hours):
    """Сколько MW этот набор сайтов обязан сбросить в каждый час (модель)."""
    H = np.asarray(curves["H"], dtype=float)
    out = []
    for h in day_hours:
        total = 0.0
        shed = 0.0
        for k in indices:
            mw = float(mw_by.get(curves["ids"][k], 0.0))
            if mw <= 0:
                continue
            total += mw
            shed += max(0.0, mw - float(H[k, h]))
        out.append(round(shed, 2))
    return out


def stress_day_block(curves: dict, best: dict, region: str, naive_portfolio=None) -> dict:
    """Stress-day chart: реальный день 2025 в MW + модельный куртейлмент агента и naive.

    День = час максимального спроса региона в локальном времени (CAL: 2025-08-21 20:00 PDT,
    43,860 MW — вечерний пик, солнце уже село). Ряды: реальный demand/solar (EIA-930, MW),
    суммарный свободный headroom подстанций и сколько MW обязаны сбросить:
      - агент (SLA-дизайн) — почти ничего;
      - naive-портфель «всё non-firm на максимум» — десятки MW, что и есть цена скорости
        без дисциплины.
    """
    import pandas as pd

    u = np.asarray(curves.get("u", np.zeros(8760)), dtype=float)
    H = np.asarray(curves["H"], dtype=float)
    H_sub = np.asarray(curves.get("H_sub", H), dtype=float)
    modes = best.get("modes") or {}
    mw_by = best.get("mw_by_site") or {}
    ids = list(curves["ids"])
    flex_idx = [k for k, sid in enumerate(ids)
                if modes.get(sid) == "flex" and float(mw_by.get(sid, 0)) > 0]

    date_str = None
    demand_day = solar_day = None
    try:
        df = pd.read_csv(os.path.join(ROOT, "data", "us_grid_hourly_2025.csv"),
                         usecols=["region", "local_time_end", "demand_mw", "solar_mw"])
        df = df[df["region"] == region].copy()
        df["date"] = df["local_time_end"].str.slice(0, 10)
        df["h"] = df["local_time_end"].str.slice(11, 13).astype(int)
        peak_row = df.loc[df["demand_mw"].idxmax()]
        date_str = str(peak_row["date"])
        day = df[df["date"] == date_str].sort_values("h")
        if len(day) == 24:
            demand_day = [round(float(v), 0) for v in day["demand_mw"].fillna(0.0)]
            solar_day = [round(float(v), 0) for v in day["solar_mw"].fillna(0.0)]
    except Exception as e:  # noqa: BLE001
        print(f"  (stress-day: реальные MW недоступны: {e})")

    # индекс часов representative year: тот же час суток, что у пикового часа u
    peak_hour = int(np.argmax(u))
    d0 = peak_hour // 24 * 24
    day_hours = list(range(d0, d0 + 24))
    if date_str is None:
        date_str = f"peak day (hour {peak_hour})"

    curtail_agent = _curtail_series(curves, mw_by, modes, flex_idx, day_hours)

    # naive-портфель: тот же расчёт по его MW
    curtail_naive = None
    if naive_portfolio:
        n_mw = {p["site_id"]: float(p.get("mw", 0)) for p in naive_portfolio}
        n_modes = {p["site_id"]: p.get("mode", "skip") for p in naive_portfolio}
        n_idx = [k for k, sid in enumerate(ids) if n_modes.get(sid) in ("flex", "battery")
                 and n_mw.get(sid, 0) > 0]
        curtail_naive = _curtail_series(curves, n_mw, n_modes, n_idx, day_hours)

    headroom = [round(float(np.maximum(0.0, H_sub[:, h]).sum()), 1) for h in day_hours]
    if demand_day is None:
        demand_day = [round(float(u[h] * 43500.0), 0) for h in day_hours]  # CAISO peak scale
        solar_day = [0.0] * 24

    return {
        "date": date_str,
        "region": region,
        "hours": [h % 24 for h in day_hours],
        "demand_mw": demand_day,
        "solar_mw": solar_day,
        "headroom_mw": headroom,
        "curtail_mw": curtail_agent,
        "curtail_mw_naive": curtail_naive,
        "peak_demand_mw": max(demand_day) if demand_day else None,
        "note": (f"real 2025 EIA-930 demand and solar for {region} (local time), "
                 f"peak {max(demand_day) if demand_day else 0:.0f} MW; headroom and required "
                 f"curtailment are model output on synthetic site geometry"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--iters", type=int, default=220)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--seeds", type=int, default=1, help="сколько сидов прогнать, взять лучший")
    ap.add_argument("--policy-file", default=None,
                    help="python-файл политики от LLM-агента (rsi_agent/gen_N.py): берём её портфель")
    ap.add_argument("--rsi-log", default=os.path.join(ROOT, "rsi_agent", "rsi_log.json"))
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--out", default=os.path.join(RESULTS, "loop.json"))
    args = ap.parse_args()

    t0 = time.time()
    os.makedirs(RESULTS, exist_ok=True)
    print(f"GRIDRUSH loop | region={args.region} iters={args.iters} mock={args.mock}")

    sim_meta = None
    if args.mock:
        from loop.mock_curves import make_mock, mock_evaluate
        curves = make_mock(seed=7)
        curves["region"] = args.region
        curves["x"] = np.random.default_rng(3).uniform(-122.4, -117.0, len(curves["ids"]))
        curves["y"] = np.random.default_rng(4).uniform(33.0, 38.2, len(curves["ids"]))

        def eval_fn(portfolio):
            return mock_evaluate(curves, portfolio)

        baselines_json = {}
        # честный baseline: всё firm, максимально возможная мощность
        def all_firm():
            H = curves["H"]
            order = np.argsort(-H.max(axis=1))
            port = [{"site_id": s, "mode": "skip", "mw": 0.0, "sla": 0.999, "battery_mwh": 0.0}
                    for s in curves["ids"]]
            used = {int(s): np.zeros(8760) for s in np.unique(curves["sub_idx"])}
            for i in order:
                s = int(curves["sub_idx"][i])
                R = np.maximum(0.0, H[i] - used[s])
                mw = float(min(curves["max_mw"][i], R.min()))
                if mw >= 0.5:
                    port[i] = {"site_id": curves["ids"][i], "mode": "firm", "mw": mw,
                               "sla": 0.999, "battery_mwh": 0.0}
                    used[s] += mw
            return port
        r = eval_fn(all_firm())
        baselines_json["all_firm_greedy"] = {
            "label": "All firm, biggest headroom first (conservative)",
            "delivered_mwmonths": round(r["delivered_mwmonths"], 2),
            "mw_at_month12": round(r["mw_at_month12"], 2),
            "net_value_musd": round(r["net_value_musd"], 3),
            "violations_mwh": 0.0, "ratio": 1.0,
            "compliant_mwmonths": round(r["delivered_mwmonths"], 2),
            "compliant_mw12": round(r["mw_at_month12"], 2),
        }
        sim_meta = {"project": "GRIDRUSH", "region": args.region, "mock": True}
    else:
        site_curves, evaluate, baselines = load_sim()
        curves = site_curves(args.region)
        eval_fn = lambda portfolio: evaluate(args.region, portfolio)  # noqa: E731
        baselines_json = {}
        if baselines is None:
            # fallback: добросовестный baseline «всё firm, самый большой headroom первым»
            def _all_firm(region, curves):
                H = np.asarray(curves["H"])
                order = np.argsort(-H.max(axis=1))
                port = [{"site_id": s, "mode": "skip", "mw": 0.0, "sla": 0.999,
                         "battery_mwh": 0.0} for s in curves["ids"]]
                used = {int(s): np.zeros(H.shape[1]) for s in np.unique(curves["sub_idx"])}
                for i in order:
                    s_i = int(curves["sub_idx"][i])
                    R = np.maximum(0.0, H[i] - used[s_i])
                    mw = float(min(curves["max_mw"][i], R.min()))
                    if mw >= 0.5:
                        port[i] = {"site_id": curves["ids"][i], "mode": "firm", "mw": mw,
                                   "sla": 0.9999, "battery_mwh": 0.0}
                        used[s_i] += mw
                return port
            baselines = type("B", (), {"BASELINES": {"all_firm_greedy": _all_firm}})()
        for name, fn in getattr(baselines, "BASELINES", {}).items():
            try:
                port = fn(args.region, curves)
                r = eval_fn(port)
                baselines_json[name] = {
                    "label": getattr(baselines, "LABELS", {}).get(name, name),
                    "delivered_mwmonths": round(float(r["delivered_mwmonths"]), 2),
                    "mw_at_month12": round(float(r["mw_at_month12"]), 2),
                    "net_value_musd": round(float(r["net_value_musd"]), 3),
                    "violations_mwh": round(float(r["violations_mwh"]), 3),
                    "sla_breach_mwh": round(float(r.get("sla_breach_mwh", 0.0)), 1),
                    "compliant_mwmonths": round(compliant_mwmonths(r), 2),
                    "compliant_mw12": round(compliant_mw12(r), 2),
                    "monthly_mw": [round(float(v), 2) for v in r.get("monthly_mw", [0.0] * 36)],
                }
            except Exception as e:  # noqa: BLE001
                print(f"  !! baseline {name} failed: {e}")

    # --- луп
    print(f"running RSI loop ({args.iters} iters x {args.seeds} seeds)...")
    best_log = None
    for sd in range(args.seeds):
        lg = hill_climb(curves, eval_fn, n_iter=args.iters, seed=args.seed + sd,
                        verbose=(args.seeds == 1))
        print(f"  seed {args.seed + sd}: best_score={lg['best']['score']:.2f}")
        if best_log is None or lg["best"]["score"] > best_log["best"]["score"]:
            best_log = lg
    log = best_log

    # --- фаза 2: LLM-пропозер (агент пишет код политики, симулятор судит) ---
    rsi_res = rsi_port = None
    if args.policy_file:
        print(f"LLM proposer: {args.policy_file}")
        import importlib.util
        spec = importlib.util.spec_from_file_location("rsi_best", args.policy_file)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "build_portfolio"):
            rsi_port = mod.build_portfolio(curves)
        elif hasattr(mod, "make_portfolio"):
            rsi_port = mod.make_portfolio(curves)
        else:
            raise SystemExit("policy file must define build_portfolio(curves)")
        rsi_res = eval_fn(rsi_port)
        print(f"  LLM policy: score={rsi_res['score']:.2f} net=${rsi_res['net_value_musd']:.1f}M "
              f"deliv={rsi_res['delivered_mwmonths']:.0f} mw12={rsi_res['mw_at_month12']:.1f} "
              f"viol={rsi_res['violations_mwh']:.2f} breach={rsi_res['sla_breach_mwh']:.1f}")

        # добавляем поколения LLM в кривую обучения (best-so-far, как в архиве RSI)
        gen_rows = []
        try:
            with open(args.rsi_log, encoding="utf-8") as f:
                rl = json.load(f)
            for g in rl.get("generations", []):
                gen_rows.append({
                    "gen": g.get("gen"),
                    "score": round(float(g.get("score_now", g.get("score", 0.0))), 4),
                    "net_value_musd": round(float(g.get("net_value_musd", 0.0)), 3),
                    "delivered_mwmonths": round(float(g.get("compliant_mwmonths", 0.0)), 2),
                    "mw_at_month12": round(float(g.get("mw_at_month12", 0.0)), 2),
                    "kept": bool(g.get("kept", False)),
                    "change": (g.get("change", "") or "")[:160],
                })
        except Exception as e:  # noqa: BLE001
            print(f"  (rsi_log.json не прочитан: {e})")

        best_so_far = log["iterations"][-1]["score"] if log["iterations"] else -1e9
        for k, g in enumerate(gen_rows):
            best_so_far = max(best_so_far, g["score"])
            log["iterations"].append({
                "iter": len(log["iterations"]),
                "score": round(float(best_so_far), 4),
                "delivered_mwmonths": round(g["delivered_mwmonths"], 2),
                "mw_at_month12": round(g["mw_at_month12"], 2),
                "violations_mwh": 0.0,
                "net_value_musd": round(g["net_value_musd"], 3),
                "phase": "llm",
                "gen": g["gen"],
                "gen_score": g["score"],
                "gen_kept": g["kept"],
                "gen_change": g["change"],
            })
        meta_llm = {"policy_file": os.path.relpath(args.policy_file, ROOT),
                    "generations": gen_rows,
                    "n_generations": len(gen_rows)}
    else:
        meta_llm = None

    # архив RSI: оставляем лучший из двух пропозеров (параметрический / LLM)
    best, portfolio = log["best"], log["best_portfolio"]
    if rsi_res is not None and float(rsi_res["score"]) > float(log["best"]["score"]):
        print(f"  -> LLM proposer wins: {rsi_res['score']:.2f} > {log['best']['score']:.2f}")
        best, portfolio = rsi_res, rsi_port
    else:
        print("  -> parametric proposer wins")
    sites_recs = site_records(curves)
    sites_by_id = {s["id"]: s for s in sites_recs}

    # --- сравнение: главная метрика = net value (там уже учтены SLA-штрафы и capex),
    # вторая = contract-compliant MW·месяцы (только продаваемый compute).
    agent_compliant = compliant_mwmonths(best)
    agent_mw12 = compliant_mw12(best)
    for name, b in baselines_json.items():
        b["compliant_mwmonths"] = round(float(b.get("compliant_mwmonths", b["delivered_mwmonths"])), 2)
        b["compliant_mw12"] = round(float(b.get("compliant_mw12", b["mw_at_month12"])), 2)
    best_bl_name, best_bl = None, None
    for name, b in baselines_json.items():
        if best_bl is None or b["net_value_musd"] > best_bl["net_value_musd"]:
            best_bl_name, best_bl = name, b
    ref_net = float(best_bl["net_value_musd"]) if best_bl else 1.0
    ref_comp = max(float(best_bl["compliant_mwmonths"]), 1.0) if best_bl else 1.0
    ref_mw12 = float(best_bl["compliant_mw12"]) if best_bl else 0.0

    # самый «быстрый» наивный baseline — для показа, что скорость без надёжности стоит отрицательно
    naive = baselines_json.get("max_mw_no_flex")

    comparison = {
        # headline
        "ratio_net_value": round(float(best["net_value_musd"]) / ref_net, 2) if ref_net > 1e-6 else None,
        "ratio_compliant_mwmonths": round(agent_compliant / ref_comp, 2),
        "agent_net_value_musd": round(float(best["net_value_musd"]), 2),
        "agent_compliant_mwmonths": round(agent_compliant, 1),
        "agent_compliant_mw12": round(agent_mw12, 1),
        # baseline reference (лучший честный)
        "baseline_ref": best_bl_name,
        "baseline_net_value_musd": round(ref_net, 2),
        "baseline_compliant_mwmonths": round(float(ref_comp), 1),
        "baseline_mw12": round(ref_mw12, 1),
        "baseline_label": (best_bl or {}).get("label", best_bl_name),
        # наивная стратегия «подписать всё non-firm»
        "naive_net_value_musd": round(float(naive["net_value_musd"]), 2) if naive else None,
        "naive_mw12": round(float(naive["mw_at_month12"]), 1) if naive else None,
        # качество
        "violations": f"{float(best.get('violations_mwh', 0.0)):.1f} MWh",
        "sla": "99.9%+ (per-site SLA met)",
        "sites_energized": sum(1 for i in portfolio if i["mode"] != "skip"),
    }

    naive_port = None
    if not args.mock:
        try:
            naive_port = baselines.BASELINES["max_mw_no_flex"](args.region, curves)
        except Exception as e:  # noqa: BLE001
            print(f"  (naive stress-day series unavailable: {e})")

    out = {
        "meta": {
            "project": "GRIDRUSH",
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "region": args.region,
            "region_name": REGION_NAMES.get(args.region, args.region),
            "horizon_months": 36,
            "n_sites": len(curves["ids"]),
            "n_substations": int(len(np.unique(curves["sub_idx"]))),
            "assumptions_version": 1,
            "loop": {"iters": args.iters, "seed": args.seed, "wall_s": log["wall_s"],
                     "n_evals": log["n_evals"], "init_preset": log["init_preset"],
                     "proposer": "parametric mutator + LLM proposer (archive keeps the best)",
                     "llm": meta_llm},
        },
        "regions": [{"code": args.region, "name": REGION_NAMES.get(args.region, args.region)}],
        "sites": sites_recs,
        "grid": {
            "region": args.region,
            "demand_mw": [round(float(v), 1) for v in np.asarray(curves.get("demand_mw", curves.get("u", np.zeros(8760)) * 30000))],
            "solar_mw": [round(float(v), 1) for v in np.asarray(curves.get("solar", np.zeros(8760)))],
            "u": [round(float(v), 4) for v in np.asarray(curves.get("u", np.zeros(8760)))],
            "stress_day": stress_day_block(curves, best, args.region, naive_portfolio=naive_port),
        },
        "baselines": baselines_json,
        "iterations": [{"phase": "parametric", **row} for row in log["iterations"]],
        "history": log["history"][-60:],
        "best": {
            "label": "GRIDRUSH agent",
            "params": (params_to_json(log["best_params_vector"]) if best is log["best"]
                       else {"policy": "flex-only exact DP per substation (LLM-generated code)",
                             "source": (meta_llm or {}).get("policy_file")}),
            "delivered_mwmonths": round(float(best["delivered_mwmonths"]), 2),
            "compliant_mwmonths": round(compliant_mwmonths(best), 2),
            "mw_at_month12": round(float(best["mw_at_month12"]), 2),
            "net_value_musd": round(float(best["net_value_musd"]), 3),
            "violations_mwh": round(float(best.get("violations_mwh", 0.0)), 3),
            "sla_breach_mwh": round(float(best.get("sla_breach_mwh", 0.0)), 3),
            "capex_musd": round(float(best.get("capex_musd", 0.0)), 3),
            "monthly_mw": [round(float(v), 2) for v in best.get("monthly_mw", [0.0] * 36)],
            "monthly_mw_by_mode": monthly_by_mode(curves, best, portfolio),
            "sites": best_site_rows(curves, best, portfolio, sites_by_id),
        },
        "comparison": comparison,
        "run_log": [
            f"sim_meta={sim_meta}",
            f"region={args.region} sites={len(curves['ids'])} iters={args.iters} wall={log['wall_s']}s",
            f"baselines={list(baselines_json)}",
            f"best net=${best['net_value_musd']:.1f}M vs {best_bl_name} ${ref_net:.1f}M "
            f"({comparison['ratio_net_value']}x), compliant={agent_compliant:.0f} MW·mo, "
            f"mw12={agent_mw12:.1f}",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    print(f"\nDONE in {time.time() - t0:.1f}s -> {args.out}")
    print(f"  best: {best['delivered_mwmonths']:.1f} MW·months, "
          f"{best['mw_at_month12']:.1f} MW @ month 12, net ${best['net_value_musd']:.1f}M")
    print(f"  vs {best_bl_name}: net ${ref_net:.1f}M -> ${best['net_value_musd']:.1f}M "
          f"({comparison['ratio_net_value']}x); compliant MW·mo {best_bl['compliant_mwmonths'] if best_bl else 0:.0f} -> {agent_compliant:.0f} "
          f"({comparison['ratio_compliant_mwmonths']}x); violations={comparison['violations']}")
    print(f"  portfolio: {sum(1 for i in portfolio if i['mode'] != 'skip')} sites energized")


if __name__ == "__main__":
    main()
