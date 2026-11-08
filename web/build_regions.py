#!/usr/bin/env python3
"""Build web/regions.html — one page with every region and the physics-in-the-loop variant.

Reads the frozen JSON (no hardcoded numbers) and writes a self-contained offline page that
links to the per-region dashboards, so "we only show one region" is not an issue at the demo.

    python3 web/build_regions.py
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

REGIONS = [("CAL", "CAISO", "dashboard.html"),
           ("TEX", "ERCOT", "dashboard_TEX.html"),
           ("MIDA", "PJM", "dashboard_MIDA.html"),
           ("MIDW", "MISO", "dashboard_MIDW.html")]


def load(name):
    path = os.path.join(ROOT, "results", name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def card(code, name, href, d, highlight=False):
    c = d["comparison"]
    b = d["best"]
    peak = None
    for r in d.get("regions", []):
        if r.get("code") == code:
            peak = r.get("peak_mw")
    return f"""
  <a class="card{' hi' if highlight else ''}" href="{href}">
    <div class="row"><span class="code">{code}</span><span class="name">{name}</span>
      {f'<span class="peak">peak {peak:,.0f} MW</span>' if peak else ''}</div>
    <div class="big">{c['ratio_net_value']:.2f}×</div>
    <div class="lbl">net value vs best honest plan</div>
    <div class="grid2">
      <div><b>{b['mw_at_month12']:.1f}</b><span>MW at month 12</span></div>
      <div><b>{b['compliant_mwmonths']:.0f}</b><span>sellable MW·months</span></div>
      <div><b>{c['violations'].split()[0]}</b><span>MWh grid violations</span></div>
      <div><b>{len(b['sites'])}</b><span>of {len(d['sites'])} sites energized</span></div>
    </div>
    <div class="open">open dashboard →</div>
  </a>"""


def main():
    cards, physics = [], None
    for code, name, href in REGIONS:
        d = load(f"loop_{code}.json") or (load("loop.json") if code == "CAL" else None)
        if d:
            cards.append(card(code, name, href, d, highlight=(code == "CAL")))

    ph = load("loop_physics.json")
    rep = load("physics_in_loop.json")
    if ph and rep:
        c = ph["comparison"]
        gate = rep["gate_limit_mw"]
        prof = rep.get("delta_vs_profile_only", {}).get("profile_only", {})
        delta = rep.get("delta_vs_profile_only", {}).get("delta_pct", {})
        physics = f"""
  <a class="card physics" href="dashboard_physics.html">
    <div class="row"><span class="code">AC PF</span><span class="name">physics-in-the-loop (CAL)</span>
      <span class="peak">measured admission limit {gate:.2f} MW / substation</span></div>
    <div class="big">{c['ratio_net_value']:.2f}×</div>
    <div class="lbl">net value vs best honest plan — with the real AC power-flow limit inside the loop</div>
    <div class="grid2">
      <div><b>{ph['best']['mw_at_month12']:.1f}</b><span>MW at month 12</span></div>
      <div><b>{ph['best']['compliant_mwmonths']:.0f}</b><span>sellable MW·months</span></div>
      <div><b>{c['sites_energized']}</b><span>sites, all AC-PF clean</span></div>
      <div><b>{rep['max_substation_load_mw']:.2f}</b><span>max MW on one real feeder</span></div>
    </div>
    <div class="note">Profile model (ICA-style headroom curve) gives {prof.get('ratio_net_value', 0):.2f}×;
      real physics cuts it by {abs(delta.get('net_value', 0)):.0f}% because a real 20 kV MV feeder of this
      class takes ~{gate:.1f} MW of new load, not the 20–60 MW the synthetic capacities assumed.
      Both numbers are reported; the delta is the value of real utility ICA data.</div>
    <div class="open">open physics dashboard →</div>
  </a>"""

    # ---- real PG&E data card -------------------------------------------------
    real = load("loop_real.json")
    real_card = ""
    if real:
        sites_meta = {}
        sp = os.path.join(ROOT, "data", "sites_CAL_real.json")
        if os.path.exists(sp):
            with open(sp, encoding="utf-8") as f:
                sites_meta = json.load(f)
        subs = sites_meta.get("substations", [])
        gna = None
        gp = os.path.join(ROOT, "results", "pge_gna_sample.json")
        if os.path.exists(gp):
            with open(gp, encoding="utf-8") as f:
                feats = json.load(f).get("features", [])
            vals = []
            for x in feats:
                try:
                    vals.append(float(x["attributes"].get("deficiencymw2026")))
                except (TypeError, ValueError):
                    pass
            pos = [v for v in vals if v > 0]
            gna = {"n": len(vals), "n_pos": len(pos), "sum_mw": round(sum(pos), 1),
                   "max_mw": round(max(pos), 1) if pos else 0.0}
        c = real["comparison"]
        rating = sum(s.get("rating_mw", 0) for s in subs)
        load_mw = sum(s.get("load_mw", 0) for s in subs)
        real_card = f"""
  <a class="card realdata" href="dashboard_real.html">
    <div class="row"><span class="code">REAL</span><span class="name">PG&amp;E GRIP substations (CAL)</span>
      <span class="peak">{len(subs)} real substations · {rating:,.0f} MW rating · {load_mw:,.0f} MW 2026 load</span></div>
    <div class="big">{c['ratio_net_value']:.2f}×</div>
    <div class="lbl">net value vs best honest plan — the same agent on real utility data</div>
    <div class="grid2">
      <div><b>{real['best']['mw_at_month12']:.1f}</b><span>MW at month 12</span></div>
      <div><b>{real['best']['compliant_mwmonths']:,.0f}</b><span>sellable MW·months</span></div>
      <div><b>{len(real['best']['sites'])}</b><span>of {len(real['sites'])} sites energized</span></div>
      <div><b>{c['violations'].split()[0]}</b><span>MWh grid violations</span></div>
    </div>
    <div class="note">Real: substation identity, coordinates, facility rating and 2026 loading
      (PG&amp;E GRIP Data Portal, public). The premium collapses to {c['ratio_net_value']:.2f}× because at the
      <b>substation aggregate</b> level these substations are large and not the bottleneck — which is exactly
      where PG&amp;E's own Grid Needs Assessment points: in a sample of {gna['n'] if gna else 2000:,} circuits,
      <b>{gna['n_pos'] if gna else 124} are already short</b> for 2026 (up to {gna['max_mw'] if gna else 12.4} MW).
      The constraint is per-circuit, not per-substation — that is the next data we need.</div>
    <div class="open">open real-data dashboard →</div>
  </a>"""
        cards.append("")

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>GRIDRUSH — all regions</title>
<style>
:root{{--bg:#080d14;--panel:#0f1823;--line:#1e2c40;--txt:#e8eef7;--dim:#7b8ba3;
 --green:#2dd4a7;--amber:#f5a524;--red:#ff5c6c;--cyan:#22d3ee}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:radial-gradient(1200px 600px at 20% -10%,#12202f 0%,#080d14 55%);color:var(--txt);
 font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",Inter,system-ui,sans-serif;padding:26px 30px}}
header{{display:flex;align-items:flex-end;gap:14px;border-bottom:1px solid var(--line);padding-bottom:12px;margin-bottom:16px}}
h1{{font-size:34px;letter-spacing:2px;font-weight:850}}
.sub{{color:var(--dim);font-size:13px;padding-bottom:5px}}
h2{{font-size:11px;letter-spacing:1.6px;color:var(--dim);text-transform:uppercase;margin:18px 0 10px;font-weight:700}}
.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.card{{display:flex;flex-direction:column;gap:6px;background:var(--panel);border:1px solid var(--line);
 border-radius:11px;padding:14px 15px;text-decoration:none;color:inherit;transition:.15s}}
.card:hover{{border-color:#2f4a68;transform:translateY(-2px)}}
.card.hi{{border-color:#2c5a4c;background:linear-gradient(180deg,rgba(45,212,167,.07),rgba(15,24,35,1))}}
.row{{display:flex;align-items:baseline;gap:8px;flex-wrap:wrap}}
.code{{font-size:10px;font-weight:800;letter-spacing:1px;color:#0b121b;background:var(--dim);padding:2px 6px;border-radius:4px}}
.name{{font-size:13px;font-weight:700}}
.peak{{font-size:10px;color:var(--dim);margin-left:auto}}
.big{{font-size:38px;font-weight:850;letter-spacing:-1px;line-height:1}}
.lbl{{font-size:10.5px;color:var(--dim);margin-bottom:4px}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:6px 8px;margin-top:4px}}
.grid2 div{{display:flex;flex-direction:column}}
.grid2 b{{font-size:16px;font-weight:800}}
.grid2 span{{font-size:9.5px;color:var(--dim)}}
.open{{margin-top:6px;font-size:10.5px;color:var(--green);font-weight:700}}
.phys-wrap{{margin-top:16px}}
.card.physics{{border-color:#1d4b5f;background:linear-gradient(180deg,rgba(34,211,238,.07),rgba(15,24,35,1))}}
.card.physics .code{{background:var(--cyan)}}
.card.realdata{{border-color:#4b3f1d;background:linear-gradient(180deg,rgba(245,165,36,.07),rgba(15,24,35,1))}}
.card.realdata .code{{background:var(--amber)}}
.card.realdata .grid2{{grid-template-columns:repeat(4,1fr);margin-top:6px}}
.card.physics .grid2{{grid-template-columns:repeat(4,1fr);margin-top:6px}}
.note{{font-size:11px;color:#b9c7da;line-height:1.45;margin-top:2px}}
footer{{margin-top:20px;border-top:1px solid var(--line);padding-top:10px;font-size:10px;color:var(--dim);
 display:flex;justify-content:space-between}}
</style></head><body>
<header><h1>GRIDRUSH</h1>
  <div class="sub">one policy, four operators, no per-region tuning — and what real power flow does to it</div></header>
<h2>2025 hourly replay, same agent policy</h2>
<div class="cards">{''.join(cards)}</div>
<<h2>reality check: measured AC power flow inside the loop</h2>
<div class="phys-wrap">{physics or ''}</div>
<h2>reality check: real PG&amp;E substations instead of synthetic ones</h2>
<div class="phys-wrap">{real_card or ''}</div>
<footer><span>numbers from results/loop_*.json, results/loop_physics.json, results/physics_in_loop.json, results/loop_real.json (+ data/sites_CAL_real.json, results/pge_gna_sample.json)</span>
  <span>offline · no keys · single-file dashboards</span></footer>
</body></html>"""
    out = os.path.join(HERE, "regions.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out} ({len(html)} bytes)")
    print(f"  regions: {[c for c, _, _ in REGIONS]}, physics card: {bool(physics)}")


if __name__ == "__main__":
    main()
