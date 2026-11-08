#!/usr/bin/env python3
"""GRIDRUSH — real PG&E data: fetch substation capacities/loadings and coordinates from GRIP.

Source (public, no key): PG&E GRIP Data Portal ArcGIS REST service
  https://services2.arcgis.com/mJaJSax0KPHoCNB6/arcgis/rest/services/DRPComplianceRelProd/FeatureServer

Layers used
  13  DFCircuitsView : per-circuit facility rating (MW) and 2026 facility loading (MW)
   0  EDSubstations  : real substation names, kV, division, coordinates (WGS84)

Output: `data/pge_grip_raw.json` (cached) and `data/sites_CAL_real.json` — 8 real PG&E
substations × 5 candidate edge sites each, in the exact schema `sim/data.make_sites` returns,
so the whole pipeline (engine, baselines, loop, dashboard) can run on it with

    GRIDRUSH_SITES=real python3 loop/run.py ...

What is real here: substation identity, location, facility rating and 2026 loading (and therefore
the loading factor `lf = loading / rating`), i.e. the two numbers the headroom model actually
consumes. What stays synthetic and documented: which 5 sites sit inside a substation, the site
nameplate ceilings, connection timelines and costs (same as the main model).
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")

BASE = ("https://services2.arcgis.com/mJaJSax0KPHoCNB6/arcgis/rest/services/"
        "DRPComplianceRelProd/FeatureServer")
RAW = os.path.join(DATA, "pge_grip_raw.json")
OUT = os.path.join(DATA, "sites_CAL_real.json")
N_SUBSTATIONS = 8
PER_SUBSTATION = 5


def fetch_layer(layer_id: int, out_fields: list[str], where: str = "1=1",
                page: int = 2000, geometry: bool = True) -> list[dict]:
    feats: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": where, "outFields": ",".join(out_fields),
            "returnGeometry": "true" if geometry else "false",
            "f": "json", "resultOffset": offset, "resultRecordCount": page,
        }
        if geometry:
            params["outSR"] = "4326"
        url = f"{BASE}/{layer_id}/query?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=60) as r:
            d = json.load(r)
        if "error" in d:
            raise RuntimeError(f"GRIP layer {layer_id} error: {d['error']}")
        got = d.get("features", [])
        feats.extend(got)
        if not d.get("exceededTransferLimit") or not got:
            break
        offset += len(got)
        if offset > 20000:  # safety valve
            break
    return feats


def main() -> int:
    os.makedirs(DATA, exist_ok=True)
    if not os.path.exists(RAW):
        print("fetching PG&E GRIP ...")
        circuits = fetch_layer(13, ["substationname", "circuitname", "division",
                                    "facilityratingmw", "facilityloadingmw2026",
                                    "facilitytype", "circuitname"], geometry=False)
        subs = fetch_layer(0, ["SubstationName", "SubstationID", "Voltage_kV", "Division"])
        raw = {"circuits": circuits, "substations": subs,
               "source": f"{BASE} (PG&E GRIP Data Portal), layers 13 and 0",
               "fetched_utc": "2026-11-08"}
        with open(RAW, "w", encoding="utf-8") as f:
            json.dump(raw, f)
        print(f"  cached {RAW} ({len(circuits)} circuits, {len(subs)} substations)")
    else:
        with open(RAW, encoding="utf-8") as f:
            raw = json.load(f)
        print(f"using cache {RAW}: {len(raw['circuits'])} circuits, {len(raw['substations'])} substations")

    # ---- aggregate circuit ratings/loadings per substation -----------------
    agg: dict[str, dict] = {}
    for f in raw["circuits"]:
        a = f.get("attributes", {})
        name = (a.get("substationname") or "").strip().upper()
        if not name:
            continue
        rating = a.get("facilityratingmw")
        load = a.get("facilityloadingmw2026")
        if rating is None or load is None:
            continue
        try:
            rating = float(rating)
            load = float(load)
        except (TypeError, ValueError):
            continue
        if rating <= 0:
            continue
        e = agg.setdefault(name, {"rating_mw": 0.0, "load_mw": 0.0, "division": a.get("division"),
                                  "circuits": 0, "types": set()})
        e["rating_mw"] += rating
        e["load_mw"] += load
        e["circuits"] += 1
        if a.get("facilitytype"):
            e["types"].add(str(a["facilitytype"]))

    # ---- real coordinates per substation ----------------------------------
    coords: dict[str, dict] = {}
    for f in raw["substations"]:
        a = f.get("attributes", {})
        g = f.get("geometry") or {}
        name = (a.get("SubstationName") or "").strip().upper()
        if not name or g.get("x") is None:
            continue
        coords.setdefault(name, {"x": float(g["x"]), "y": float(g["y"]),
                                 "kv": a.get("Voltage_kV"), "division": a.get("Division"),
                                 "id": a.get("SubstationID")})

    # ---- pick 8 real substations able to host edge compute ----------------
    cands = []
    for name, e in agg.items():
        c = coords.get(name)
        if not c or e["rating_mw"] < 8.0:
            continue
        lf = e["load_mw"] / e["rating_mw"]
        if not (0.25 <= lf <= 0.92):          # keep real substations with real headroom
            continue
        if e["circuits"] < 2:                 # a substation, not a single feeder
            continue
        cands.append({"name": name, "rating_mw": round(e["rating_mw"], 2),
                      "load_mw": round(e["load_mw"], 2), "lf_real": round(lf, 4),
                      "circuits": e["circuits"], "division": e["division"],
                      "x": round(c["x"], 5), "y": round(c["y"], 5), "kv": c["kv"]})
    # spread across divisions, then take the largest headroom
    cands.sort(key=lambda r: (-(r["rating_mw"] - r["load_mw"])))
    chosen, seen_div = [], {}
    for r in cands:
        d = (r["division"] or "?")
        if seen_div.get(d, 0) >= 2:
            continue
        chosen.append(r)
        seen_div[d] = seen_div.get(d, 0) + 1
        if len(chosen) >= N_SUBSTATIONS:
            break
    if len(chosen) < N_SUBSTATIONS:  # fall back to pure headroom order
        for r in cands:
            if r not in chosen:
                chosen.append(r)
            if len(chosen) >= N_SUBSTATIONS:
                break

    # ---- real u_peak for the region, so the model's peak hour matches real loading ----
    import numpy as np
    import pandas as pd
    csv = os.path.join(DATA, "us_grid_hourly_2025.csv")
    u_peak = 1.30
    try:
        df = pd.read_csv(csv, usecols=["region", "demand_mw"])
        d_ = df[df["region"] == "CAL"]["demand_mw"].dropna().to_numpy()
        if d_.size > 1000:
            u_ = d_ / np.percentile(d_, 95)
            u_peak = float(np.max(u_))
    except Exception as e:  # noqa: BLE001
        print(f"  (u_peak fallback: {e})")
    print(f"  region u_peak = {u_peak:.3f} (model peak hour = real 2026 facloading)")

    # ---- build sites in the exact make_sites schema ------------------------
    rng_state = 7
    def rnd():
        nonlocal rng_state
        rng_state = (1103515245 * rng_state + 12345) % (2 ** 31)
        return rng_state / (2 ** 31)

    sites = []
    for si, sub in enumerate(chosen):
        # the headroom model uses u = demand/p95 with 1.0 at p95 and u_peak at the peak;
        # real 2026 facility loading is peak loading, so lf_model = lf_real / u_peak
        sub["lf"] = round(min(0.78, sub["lf_real"] / u_peak), 4)
        headroom = sub["rating_mw"] - sub["load_mw"]
        for k in range(PER_SUBSTATION):
            max_mw = round(min(10.0, max(0.5, headroom / 2.5)), 2)
            prop_days = int(30 + 370 * rnd())
            sites.append({
                "id": f"P{si + 1:02d}-{k + 1}",
                "substation": sub["name"][:18],
                "cap_mw": sub["rating_mw"],
                "lf": sub["lf"],
                "max_mw": max_mw,
                "x": round(sub["x"] + (rnd() - 0.5) * 0.05, 5),
                "y": round(sub["y"] + (rnd() - 0.5) * 0.05, 5),
                "T_firm": int(18 + 18 * rnd()),
                "T_flex": int(5 + 5 * rnd()),
                "T_on": None,
                "fiber": bool(rnd() > 0.35),
                "permit_days": prop_days,
            })
            sites[-1]["T_on"] = sites[-1]["T_flex"] + 1 + int(2 * rnd())

    out = {"region": "CAL", "source": "PG&E GRIP Data Portal (public, no key)",
           "real_fields": ["substation", "cap_mw (sum of facility rating MW)",
                           "lf_real (= 2026 facility loading / rating)",
                           "lf (same, rescaled so the model's peak hour reproduces that loading)",
                           "n_circuits", "x", "y"],
           "synthetic_fields": ["max_mw", "T_firm", "T_flex", "T_on", "fiber", "permit_days",
                                "site placement inside a substation"],
           "substations": [{**{k: v for k, v in s.items()}, "n_circuits": s["circuits"]}
                           for s in chosen],
           "sites": sites}
    os.makedirs(DATA, exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {OUT}: {len(chosen)} real substations x {PER_SUBSTATION} sites")
    for s in chosen:
        print(f"  {s['name'][:22]:24s} {s['division'][:14]:15s} rating {s['rating_mw']:7.1f} MW "
              f"load {s['load_mw']:7.1f} MW  lf {s['lf']:.3f}  headroom "
              f"{s['rating_mw'] - s['load_mw']:6.1f} MW  ({s['circuits']} circuits)")
    total_cap = sum(s["rating_mw"] for s in chosen)
    total_load = sum(s["load_mw"] for s in chosen)
    print(f"  totals: {total_cap:.0f} MW rating, {total_load:.0f} MW loading, "
          f"{total_cap - total_load:.0f} MW real headroom")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
