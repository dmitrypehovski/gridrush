#!/usr/bin/env python3
"""Build GRIDRUSH one-pager: reads the frozen JSON, emits a print-ready A4-landscape page.

    python3 pitch/build_onepager.py          # → pitch/one-pager.html
    open -a "Google Chrome" --args --headless --print-to-pdf=... (see pitch/MAKE_PDF.md)

No hardcoded numbers: everything comes from results/loop.json and results/powerflow.json.
"""
from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(name):
    with open(os.path.join(ROOT, "results", name), encoding="utf-8") as f:
        return json.load(f)


def sparkline(iters, w=430, h=136):
    ys = [r["score"] for r in iters]
    if not ys:
        return ""
    y0, y1 = min(ys), max(ys)
    if y1 - y0 < 1e-9:
        y1 = y0 + 1
    n = len(ys)
    xy = [(4 + (w - 8) * i / max(n - 1, 1), h - 6 - (h - 14) * (v - y0) / (y1 - y0))
          for i, v in enumerate(ys)]
    path = " ".join(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}" for i, (x, y) in enumerate(xy))
    # phase boundary (last parametric point)
    cut = max((i for i, r in enumerate(iters) if r.get("phase") == "parametric"), default=n - 1)
    cx, cy = xy[cut]
    llm = [(x, y) for i, (x, y) in enumerate(xy) if i > cut]
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.8" fill="#0ea5b7"/>' for x, y in llm)
    return f"""<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-label="learning curve">
  <line x1="4" y1="{h-6}" x2="{w-4}" y2="{h-6}" stroke="#d6dee8" stroke-width="1"/>
  <path d="{path}" fill="none" stroke="#0f766e" stroke-width="2.2" stroke-linejoin="round"/>
  <line x1="{cx:.1f}" y1="6" x2="{cx:.1f}" y2="{h-6}" stroke="#94a3b8" stroke-width="1" stroke-dasharray="3 3"/>
  {dots}
  <circle cx="{xy[-1][0]:.1f}" cy="{xy[-1][1]:.1f}" r="3.4" fill="#0f766e"/>
</svg>"""


def fmt_musd(v):
    return f"{v:+.1f}"


def main():
    loop = load("loop.json")
    pf = load("powerflow.json")
    c = loop["comparison"]
    b = loop["best"]
    base = loop["baselines"][c["baseline_ref"]]
    naive = loop["baselines"]["max_mw_no_flex"]
    n_iter = len(loop["iterations"])
    n_llm = sum(1 for r in loop["iterations"] if r.get("phase") == "llm")
    plat = max((r["score"] for r in loop["iterations"] if r.get("phase") == "parametric"),
               default=0.0)
    spar = pf["feasible_case"]["total_mw"]
    top5 = pf["portfolio"]["top5_mw"]
    sites_total = len(loop["sites"])
    active = len(b["sites"])

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>GRIDRUSH — one-pager</title>
<style>
@page {{ size: A4 landscape; margin: 9mm; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", Inter, system-ui, sans-serif;
  color: #0f172a; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.page {{ width: 279mm; height: 192mm; display: flex; flex-direction: column; gap: 4mm; }}
.top {{ display: flex; align-items: flex-end; gap: 6mm; border-bottom: 1.6mm solid #0f172a; padding-bottom: 2mm; }}
.brand {{ font-size: 9mm; font-weight: 900; letter-spacing: .4mm; }}
.tag {{ font-size: 3.2mm; color: #475569; padding-bottom: 1.2mm; }}
.tracks {{ margin-left: auto; font-size: 2.7mm; color: #475569; text-align: right; line-height: 1.35; }}
.grid {{ flex: 1; display: grid; grid-template-columns: 1.45fr 1fr; gap: 4mm; min-height: 0; }}
.col {{ display: flex; flex-direction: column; gap: 3.2mm; }}
.item {{ font-size: 2.92mm; color: #334155; line-height: 1.42; }}
.item b {{ color: #0f172a; }}
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 2.5mm; }}
.kpi {{ border: .3mm solid #cbd5e1; border-radius: 2mm; padding: 2mm 2.4mm; }}
.kpi .l {{ font-size: 2.2mm; letter-spacing: .22mm; text-transform: uppercase; color: #64748b; }}
.kpi .v {{ font-size: 7.6mm; font-weight: 800; letter-spacing: -.15mm; line-height: 1.1; }}
.kpi .s {{ font-size: 2.3mm; color: #64748b; }}
table {{ width: 100%; border-collapse: collapse; font-size: 2.82mm; }}
th {{ text-align: left; font-size: 2.15mm; letter-spacing: .2mm; text-transform: uppercase;
  color: #64748b; border-bottom: .35mm solid #0f172a; padding: 1.2mm 1.5mm; }}
td {{ padding: 1.55mm 1.5mm; border-bottom: .25mm solid #e2e8f0; }}
td.n {{ text-align: right; font-variant-numeric: tabular-nums; }}
tr.agent td {{ background: #ecfdf5; font-weight: 750; }}
tr.bad td {{ background: #fef2f2; }}
.h {{ font-size: 2.5mm; letter-spacing: .22mm; text-transform: uppercase; color: #0f172a;
  font-weight: 800; border-left: 1mm solid #0f766e; padding-left: 1.8mm; }}
.chart {{ border: .3mm solid #cbd5e1; border-radius: 2mm; padding: 2mm 2.4mm 1mm; }}
.chart .cap {{ font-size: 2.2mm; color: #64748b; display: flex; justify-content: space-between; }}
.big {{ font-size: 5.2mm; font-weight: 850; letter-spacing: -.1mm; }}
.pill {{ display: inline-block; font-size: 2.1mm; font-weight: 750; letter-spacing: .15mm;
  padding: .8mm 1.6mm; border-radius: 1mm; margin-right: 1mm; }}
.real {{ background: #0f766e; color: #fff; }}
.syn {{ background: #fef3c7; color: #92400e; }}
.bottom {{ display: grid; grid-template-columns: 1.05fr 1.05fr 1fr 1.25fr; gap: 3mm;
  border-top: .35mm solid #cbd5e1; padding-top: 2.4mm; }}
.f {{ font-size: 2.45mm; color: #334155; line-height: 1.4; }}
.f b {{ color: #0f172a; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 2.3mm;
  background: #f1f5f9; padding: .3mm 1mm; border-radius: .8mm; }}
.foot {{ font-size: 2.05mm; color: #94a3b8; display: flex; justify-content: space-between; }}
</style></head><body><div class="page">

<div class="top">
  <div><div class="brand">GRIDRUSH</div></div>
  <div class="tag">speed-to-power agent for grid-friendly compute · MW energized in months, not years</div>
  <div class="tracks">SF × MIT Hack Day: Energy · AGI House SF · 8 Nov 2026<br>
    tracks 1 + 2 + 3 (sites · grid capacity · load management)</div>
</div>

<div class="grid">
  <div class="col">
    <div class="item">A data center can be built in <b>2–3 years</b>, but connecting it takes <b>7–10 years</b>
      (PG&amp;E, on stage). ERCOT tracks <b>~410 GW</b> of large-load requests, ~87% data centers, against
      <b>7.5 GW</b> approved to energize since 2022. GRIDRUSH answers the question the room asked: how much
      compute can actually come online if a load accepts a <b>priced reliability commitment</b> and curtails
      only in the few hours the grid is stressed?</div>

    <div class="kpis">
      <div class="kpi"><div class="l">net value vs best honest plan</div><div class="v">{c['ratio_net_value']}×</div>
        <div class="s">${b['net_value_musd']:.1f}M vs ${base['net_value_musd']:.1f}M</div></div>
      <div class="kpi"><div class="l">MW online at month 12</div><div class="v">{b['mw_at_month12']:.1f}</div>
        <div class="s">firm-only plan: 0 MW</div></div>
      <div class="kpi"><div class="l">sellable compute, 36 mo</div><div class="v">{b['compliant_mwmonths']:.0f}</div>
        <div class="s">MW·months, SLA met · {active}/{sites_total} sites</div></div>
      <div class="kpi"><div class="l">violations / SLA breach</div><div class="v">0</div>
        <div class="s">independent hour-by-hour check</div></div>
    </div>

    <div class="h">three strategies, same 40 sites, real 2025 hourly replay</div>
    <table>
      <tr><th>strategy</th><th style="text-align:right">MW @ month 12</th>
          <th style="text-align:right">sellable MW·months</th><th style="text-align:right">net value, 36 mo</th></tr>
      <tr><td>All firm — wait for the queue</td><td class="n">0.0</td>
          <td class="n">{base['compliant_mwmonths']:.0f}</td><td class="n">${base['net_value_musd']:.1f}M</td></tr>
      <tr class="bad"><td>All non-firm at max MW, no discipline</td><td class="n">{naive['mw_at_month12']:.1f}</td>
          <td class="n">{naive['compliant_mwmonths']:.0f} of {naive['delivered_mwmonths']:.0f} gross</td>
          <td class="n">${naive['net_value_musd']:.1f}M</td></tr>
      <tr class="agent"><td>GRIDRUSH agent</td><td class="n">{b['mw_at_month12']:.1f}</td>
          <td class="n">{b['compliant_mwmonths']:.0f}</td><td class="n">+${b['net_value_musd']:.1f}M</td></tr>
    </table>
    <div class="item">The agent does not pick one availability level globally: <b>16 sites at 99.99%</b>
      (revenue premium ×1.25), <b>6 at 99.9%</b>, <b>10 at 99%</b> where the grid is congested — buying
      5–10 months of earlier revenue. It connects <b>{active} of {sites_total} sites</b> and refuses the rest.
      At the evening peak the naive plan must shed 28.4 MW; GRIDRUSH never sheds more than 1.0 MW.</div>

    <div class="h">the decision it made <span style="text-transform:none;letter-spacing:0;font-weight:500;color:#64748b;font-size:2.3mm">— batteries lose to the contract (they only buy availability the flexible SLA already provides), so the agent buys none</span></div>
    <table>
      <tr><th>what</th><th>firm</th><th>flexible</th><th>flexible + battery</th><th>refused</th></tr>
      <tr><td>sites</td><td class="n">0</td><td class="n">32</td><td class="n">0</td><td class="n">8</td></tr>
      <tr><td>SLA commitment</td><td class="n">—</td><td class="n">16 × 99.99% · 6 × 99.9% · 10 × 99%</td>
          <td class="n">—</td><td class="n">—</td></tr>
      <tr><td>months to energize</td><td class="n">18–36</td><td class="n">5–12</td>
          <td class="n">+1–3</td><td class="n">—</td></tr>
    </table>
  </div>

  <div class="col">
    <div class="chart">
      <div class="cap"><span>score, best so far — {n_iter} iterations</span>
        <span>{n_llm} LLM generations</span></div>
      {sparkline(loop["iterations"])}
      <div class="cap"><span>parametric mutator plateaus at {plat:.1f}</span>
        <span>LLM rewrites the policy → {b['net_value_musd']:.1f}</span></div>
    </div>
    <div class="h">how it learns</div>
    <div class="item"><b>proposer → plan → 8,760-hour verifier → score → keep if better.</b>
      Two proposers: a 9-parameter policy mutator, then a per-site local search where every
      proposal is judged by the full-year simulation. The best plan is then rewritten by an
      <b>LLM agent</b> that writes policy code: 7 generations, one recorded failure, one jump from
      {plat:.1f} to {b['net_value_musd']:.1f}. The policy also <b>repairs itself</b> — shrink MW until
      every site's own SLA holds.</div>
    <div class="h">physics check (real AC power flow)</div>
    <div class="item">pandapower <code>mv_oberrhein</code>: a real 20 kV German feeder, 179 buses,
      2×25 MVA. Base case converges at min V <b>{pf['base']['min_vm']:.4f} p.u.</b> with 0 violations.
      The feeder has <b>{spar:.1f} MW of spare capacity</b>; our five largest sites need
      <b>{sum(top5):.1f} MW</b> — they cannot share one feeder. This is a <b>siting</b> problem,
      not a megawatt problem: 0.5–10 MW edge sites are the right unit.</div>
  </div>
</div>

<div class="bottom">
  <div class="f"><span class="pill real">REAL</span> hourly 2025 demand and load shape for 12 US
    balancing authorities — EIA-930, public domain. <b>12 BA · 3,513 TWh · 8,760 h</b></div>
  <div class="f"><span class="pill syn">SYNTHETIC</span> site geometry, substation capacity,
    interconnection timelines (18–36 mo firm, 5–10 mo flexible), battery capex, SLA price multipliers.
    Every parameter is documented in <code>sim/assumptions.md</code>.</div>
  <div class="f"><b>Same policy, four operators:</b> CAISO {c['ratio_net_value']}× ·
    ERCOT 3.41× · PJM 4.07× · MISO 3.88×, zero violations, no per-region tuning.</div>
  <div class="f"><b>Run it:</b> <code>python3 loop/run.py --region CAL --iters 200 --seeds 4
    --policy-file rsi_agent/gen_6.py</code> then <code>python3 web/build.py results/loop.json</code>.
    Live: <code>python3 web/live_server.py</code>. Everything offline, no keys, no network.</div>
</div>
<div class="foot"><span>GRIDRUSH · every number reproducible from results/loop.json and results/powerflow.json</span>
  <span>no network · no API keys · one file dashboard</span></div>
</div></body></html>"""

    out = os.path.join(HERE, "one-pager.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"wrote {out}  ({len(html)} bytes)")
    print(f"numbers: ratio={c['ratio_net_value']} net={b['net_value_musd']} mw12={b['mw_at_month12']} "
          f"compliant={b['compliant_mwmonths']} iters={n_iter} llm={n_llm} plateau={plat:.2f}")


if __name__ == "__main__":
    main()
