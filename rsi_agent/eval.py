"""GRIDRUSH — evaluator для LLM-in-the-loop (RSI-агент как proposer).

Агент пишет файл политики `rsi_agent/gen_N.py` и вызывает:
    python3 rsi_agent/eval.py --policy rsi_agent/gen_N.py --region CAL

Файл политики может содержать ЛЮБОЕ из:
    PARAMS = [9 floats in 0..1]                      # передать в loop.policy.build_portfolio
    def build_portfolio(curves) -> list[dict]        # своя логика портфеля
    def make_portfolio(curves) -> list[dict]         # алиас

Формат портфеля (CONTRACT §4):
    {"site_id": str, "mode": "skip|firm|flex|battery", "mw": float,
     "sla": 0.9999|0.999|0.99, "battery_mwh": float}

Печатает JSON с метриками. Ничего не пишет на диск.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sim.curves import site_curves        # noqa: E402
from sim.engine import evaluate           # noqa: E402
from loop.policy import build_portfolio as default_build   # noqa: E402


def load_policy_module(path: str):
    spec = importlib.util.spec_from_file_location("rsi_policy", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", required=True)
    ap.add_argument("--region", default="CAL")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    curves = site_curves(args.region)
    mod = load_policy_module(args.policy)

    if hasattr(mod, "build_portfolio"):
        portfolio = mod.build_portfolio(curves)
    elif hasattr(mod, "make_portfolio"):
        portfolio = mod.make_portfolio(curves)
    elif hasattr(mod, "PARAMS"):
        portfolio = default_build(curves, np.asarray(mod.PARAMS, dtype=float))
    else:
        raise SystemExit("policy file must define PARAMS or build_portfolio(curves)")

    res = evaluate(args.region, portfolio)
    active = [p for p in portfolio if p.get("mode") != "skip" and float(p.get("mw", 0)) > 0]
    out = {
        "region": args.region,
        "score": round(float(res["score"]), 4),
        "net_value_musd": round(float(res["net_value_musd"]), 3),
        "delivered_mwmonths": round(float(res["delivered_mwmonths"]), 2),
        "mw_at_month12": round(float(res["mw_at_month12"]), 2),
        "violations_mwh": round(float(res["violations_mwh"]), 3),
        "sla_breach_mwh": round(float(res["sla_breach_mwh"]), 3),
        "capex_musd": round(float(res["capex_musd"]), 3),
        "n_active": len(active),
        "modes": {m: sum(1 for p in active if p["mode"] == m) for m in ("firm", "flex", "battery")},
        "sla_mix": {str(s): sum(1 for p in active if abs(float(p.get("sla", 0)) - s) < 1e-9)
                    for s in (0.9999, 0.999, 0.99)},
    }
    # contract-compliant MW·months (только сайты, где доступность >= заявленного SLA)
    comp = 0.0
    for sid, mw in (res.get("mw_by_site") or {}).items():
        avail = float((res.get("avail_by_site") or {}).get(sid, 0.0))
        sla = float((res.get("sla_by_site") or {}).get(sid, 0.999))
        mon = 36 - int((res.get("energize_month_by_site") or {}).get(sid, 36))
        if avail >= sla - 1e-9:
            comp += float(mw) * max(0, mon) * avail
    out["compliant_mwmonths"] = round(comp, 2)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
