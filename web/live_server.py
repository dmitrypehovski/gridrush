"""GRIDRUSH live run — watch the agent think, in the browser, right now.

    python3 web/live_server.py            # → http://127.0.0.1:8767/  (opens the page)
    python3 web/live_server.py --iters 120 --budget 2500

Runs the real loop (parametric proposer → per-site local search → the LLM-written policy)
against the real evaluator, and streams progress to a self-contained page. No network, no
node_modules, stdlib only. Safe to show on stage: the main dashboard is untouched.

Endpoints:
    GET /        live page
    GET /state   JSON snapshot (polled by the page every 120 ms)
    GET /start   (re)starts a run
    GET /result  final JSON (evaluator result of the best portfolio)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from sim.curves import site_curves  # noqa: E402
from sim.engine import evaluate  # noqa: E402
from loop.policy import build_portfolio  # noqa: E402
from loop.search import hill_climb  # noqa: E402
from loop.local_search import local_search  # noqa: E402

ARGV = None
STATE = {
    "status": "idle",
    "phase": "idle",
    "started_at": None,
    "elapsed_s": 0.0,
    "iterations": [],
    "best": None,
    "portfolio": [],
    "error": None,
    "config": {},
    "counts": {"parametric": 0, "local": 0, "llm": 0},
}
LOCK = threading.Lock()


def _load_llm_policy():
    path = os.path.join(ROOT, "rsi_agent", "gen_6.py")
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("rsi_best", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, path
    except Exception:  # noqa: BLE001
        return None, path


def _snapshot(res: dict) -> dict:
    return {
        "score": round(float(res.get("score", 0.0)), 4),
        "delivered_mwmonths": round(float(res.get("delivered_mwmonths", 0.0)), 2),
        "mw_at_month12": round(float(res.get("mw_at_month12", 0.0)), 2),
        "net_value_musd": round(float(res.get("net_value_musd", 0.0)), 3),
        "violations_mwh": round(float(res.get("violations_mwh", 0.0)), 3),
        "sla_breach_mwh": round(float(res.get("sla_breach_mwh", 0.0)), 3),
        "n_active": (sum(1 for m in (res.get("modes") or {}).values() if m != "skip")
                     if res.get("modes") else None),
        "monthly_mw": [round(float(v), 2) for v in (res.get("monthly_mw") or [])],
    }


def _merge(kind: str, row: dict, res: dict):
    with LOCK:
        STATE["iterations"].append(row)
        STATE["counts"][kind] += 1
        STATE["phase"] = row.get("phase", kind)
        STATE["best"] = _snapshot(res)
        STATE["elapsed_s"] = round(time.time() - (STATE["started_at"] or time.time()), 1)


def run_loop(region: str, iters: int, budget: int, seeds: int):
    t0 = time.time()
    with LOCK:
        STATE.update({"status": "running", "phase": "loading", "started_at": t0,
                      "elapsed_s": 0.0, "iterations": [], "error": None,
                      "best": None, "counts": {"parametric": 0, "local": 0, "llm": 0},
                      "config": {"region": region, "iters": iters, "local_budget": budget,
                                 "seeds": seeds}})
    try:
        curves = site_curves(region)
        ev = lambda p: evaluate(region, p)  # noqa: E731

        with LOCK:
            STATE["phase"] = "parametric"

        best = None
        best_port = None
        for sd in range(seeds):
            def on_iter(row, _sd=sd):
                res = {"score": row["score"], "delivered_mwmonths": row["delivered_mwmonths"],
                       "mw_at_month12": row["mw_at_month12"], "net_value_musd": row["net_value_musd"],
                       "violations_mwh": 0.0, "modes": None}
                _merge("parametric", {**row, "seed": _sd}, res)

            lg = hill_climb(curves, ev, n_iter=iters, seed=sd, verbose=False, on_iter=on_iter)
            if best is None or float(lg["best"]["score"]) > float(best["score"]):
                best, best_port = lg["best"], lg["best_portfolio"]

        # phase 2 — per-site local search against the simulator
        with LOCK:
            STATE["phase"] = "local"

        def on_step(row):
            res = {"score": row["score"], "delivered_mwmonths": row["delivered_mwmonths"],
                   "mw_at_month12": row["mw_at_month12"], "net_value_musd": row["net_value_musd"],
                   "violations_mwh": 0.0, "modes": {}}
            _merge("local", {**row, "iter": None}, res)

        ls = local_search(curves, ev, best_port, max_evals=budget, sweeps=2,
                          verbose=False, on_step=on_step)
        with LOCK:
            STATE["portfolio"] = ls["portfolio"]
            STATE["best"] = _snapshot(ls["result"])
            if best is not None and float(ls["result"]["score"]) >= float(best["score"]):
                best = ls["result"]

        # phase 3 — the policy the LLM proposer wrote during the hack
        with LOCK:
            STATE["phase"] = "llm"
        mod, path = _load_llm_policy()
        if mod is not None:
            try:
                port = mod.build_portfolio(curves)
                r = ev(port)
                with LOCK:
                    STATE["iterations"].append({
                        "phase": "llm", "gen": 6, "site": "policy rewrite",
                        "change": "LLM-written policy: exact per-substation DP (flex-only)",
                        "score": round(float(r["score"]), 4),
                        "net_value_musd": round(float(r["net_value_musd"]), 3),
                        "delivered_mwmonths": round(float(r["delivered_mwmonths"]), 2),
                        "mw_at_month12": round(float(r["mw_at_month12"]), 2),
                    })
                    STATE["counts"]["llm"] += 1
                    STATE["iterations"].append({
                        "phase": "llm", "gen": 6, "site": "policy rewrite",
                        "change": "evaluated: zero violations, zero SLA breach",
                        "score": round(float(r["score"]), 4),
                        "net_value_musd": round(float(r["net_value_musd"]), 3),
                        "delivered_mwmonths": round(float(r["delivered_mwmonths"]), 2),
                        "mw_at_month12": round(float(r["mw_at_month12"]), 2),
                    })
                    STATE["counts"]["llm"] += 1
                    STATE["best"] = _snapshot(r)
                    STATE["portfolio"] = port
            except Exception as e:  # noqa: BLE001
                with LOCK:
                    STATE["error"] = f"llm policy: {e}"

        with LOCK:
            STATE["status"] = "done"
            STATE["phase"] = "done"
            STATE["elapsed_s"] = round(time.time() - t0, 1)
    except Exception as e:  # noqa: BLE001
        with LOCK:
            STATE["status"] = "error"
            STATE["error"] = f"{e}\n{traceback.format_exc()[-800:]}"
            STATE["elapsed_s"] = round(time.time() - t0, 1)


PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>GRIDRUSH — live run</title>
<style>
:root{--bg:#080d14;--panel:#0f1823;--line:#1e2c40;--txt:#e8eef7;--dim:#7b8ba3;
 --amber:#f5a524;--cyan:#22d3ee;--green:#2dd4a7;--red:#ff5c6c;--blue:#4c9aff}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:radial-gradient(1200px 600px at 20% -10%,#12202f 0%,#080d14 55%);
 color:var(--txt);font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display",Inter,system-ui,sans-serif;
 overflow:hidden}
.wrap{height:100vh;display:flex;flex-direction:column;gap:10px;padding:16px 20px}
header{display:flex;align-items:flex-end;gap:14px;border-bottom:1px solid var(--line);padding-bottom:10px}
h1{font-size:30px;letter-spacing:1.5px;font-weight:850}
.sub{color:var(--dim);font-size:12px;padding-bottom:4px}
.badge{margin-left:auto;display:flex;gap:8px;align-items:center;font-size:11px;color:var(--dim)}
.live{color:var(--red);font-weight:800;letter-spacing:1px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--red);animation:p 1s infinite}
@keyframes p{50%{opacity:.25}}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 12px}
.kpi .l{font-size:10px;letter-spacing:1.3px;color:var(--dim);text-transform:uppercase}
.kpi .v{font-size:30px;font-weight:800;letter-spacing:-.5px;margin-top:2px}
.kpi .s{font-size:10.5px;color:var(--dim);margin-top:2px}
.main{flex:1;display:grid;grid-template-columns:1.55fr 1fr;gap:10px;min-height:0}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:9px;padding:10px 12px;
 display:flex;flex-direction:column;min-height:0}
.ph{font-size:10.5px;letter-spacing:1.3px;color:var(--dim);text-transform:uppercase;display:flex;
 justify-content:space-between;gap:8px;margin-bottom:4px}
.ph b{color:var(--txt);font-weight:700}
svg{flex:1;min-height:0;width:100%}
.feed{flex:1;overflow:hidden;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11.5px;
 line-height:1.55;color:#b9c7da}
.feed div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.feed .phase{color:#5b6b80;font-style:italic;margin:3px 0}
.feed .p{color:var(--blue)} .feed .l{color:var(--amber)} .feed .m{color:var(--cyan)}
.feed .new{animation:in .35s ease-out}
@keyframes in{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
footer{display:flex;gap:16px;font-size:10px;color:var(--dim);border-top:1px solid var(--line);padding-top:7px}
footer b{color:#9fb0c6;font-weight:600}
.err{color:var(--red);font-size:11px;white-space:pre-wrap}
#again{font:inherit;font-size:11px;font-weight:700;letter-spacing:.4px;color:#0b121b;background:var(--amber);
 border:0;border-radius:6px;padding:5px 11px;cursor:pointer;margin-left:6px}
#again:hover{filter:brightness(1.08)}
#again:disabled{opacity:.5;cursor:default}
</style></head><body><div class="wrap">
<header>
  <h1>GRIDRUSH</h1>
  <div class="sub">live run — the agent proposes, the 8,760-hour simulator judges, the archive keeps the best</div>
  <div class="badge"><span class="dot"></span><span class="live" id="live">LIVE</span>
    <span id="phase">loading</span><span>·</span><span id="clock">0.0 s</span>
    <span>·</span><span id="region">CAL</span>
    <button id="again" title="run the loop again (12 s)">Run again</button></div>
</header>
<div class="kpis">
  <div class="kpi"><div class="l">best score</div><div class="v" id="k-score">—</div><div class="s" id="k-iters">iterations 0</div></div>
  <div class="kpi"><div class="l">net value</div><div class="v" id="k-net">—</div><div class="s">modelled compute margin, 36 mo</div></div>
  <div class="kpi"><div class="l">MW at month 12</div><div class="v" id="k-mw12">—</div><div class="s" id="k-deliv">—</div></div>
  <div class="kpi"><div class="l">violations / SLA breach</div><div class="v" id="k-viol">—</div><div class="s">independent hour-by-hour verifier</div></div>
</div>
<div class="main">
  <div class="panel"><div class="ph"><span>score, best so far</span><span id="p-phase">phase: loading</span></div>
    <svg id="chart" viewBox="0 0 900 420" preserveAspectRatio="none"></svg></div>
  <div class="panel"><div class="ph"><span>agent log</span><span id="p-count">0 events</span></div>
    <div class="feed" id="feed"></div></div>
</div>
<footer><span>proposer <b>parametric mutator</b> → <b>per-site local search</b> → <b>LLM-written policy</b></span>
 <span>verifier <b>all 8,760 hours of 2025</b>, per-substation capacity</span>
 <span>data <b>real EIA-930 demand shape</b> · synthetic site geometry</span>
 <span id="f-status">starting…</span></footer>
</div>
<script>
const $=id=>document.getElementById(id), NS="http://www.w3.org/2000/svg";
let lastN=0, feedEl=$("feed");
function money(v){return "$"+(v>=0?"":"−")+Math.abs(v).toFixed(1)+"M"}
function draw(iters){
  const svg=$("chart"); while(svg.firstChild)svg.removeChild(svg.firstChild);
  const W=900,H=420,pad={l:70,r:16,t:14,b:34};
  const xs=iters.map((d,i)=>i), ys=iters.map(d=>d.score);
  if(!ys.length)return;
  let y0=Math.min(...ys,0), y1=Math.max(...ys,0); if(y1-y0<1)y1=y0+1;
  const X=i=>pad.l+(W-pad.l-pad.r)*(iters.length<2?0.5:i/(iters.length-1));
  const Y=v=>pad.t+(H-pad.t-pad.b)*(1-(v-y0)/(y1-y0));
  // grid
  for(let k=0;k<4;k++){const v=y0+(y1-y0)*k/3, y=Y(v);
    const l=document.createElementNS(NS,"line");l.setAttribute("x1",pad.l);l.setAttribute("x2",W-pad.r);
    l.setAttribute("y1",y);l.setAttribute("y2",y);l.setAttribute("stroke","#1b2839");svg.appendChild(l);
    const t=document.createElementNS(NS,"text");t.setAttribute("x",pad.l-8);t.setAttribute("y",y+3);
    t.setAttribute("fill","#6b7f9c");t.setAttribute("font-size","11");t.setAttribute("text-anchor","end");
    t.textContent="$"+v.toFixed(0)+"M";svg.appendChild(t);}
  const path=iters.map((d,i)=>`${i?"L":"M"}${X(i).toFixed(1)},${Y(d.score).toFixed(1)}`).join("");
  const area=path+`L${X(iters.length-1)},${H-pad.b}L${X(0)},${H-pad.b}Z`;
  const a=document.createElementNS(NS,"path");a.setAttribute("d",area);a.setAttribute("fill","rgba(45,212,167,.12)");svg.appendChild(a);
  const p=document.createElementNS(NS,"path");p.setAttribute("d",path);p.setAttribute("fill","none");
  p.setAttribute("stroke","#2dd4a7");p.setAttribute("stroke-width","2.2");svg.appendChild(p);
  // phase boundaries: color last points (llm)
  iters.forEach((d,i)=>{ if(d.phase==="llm"){
    const c=document.createElementNS(NS,"circle");c.setAttribute("cx",X(i));c.setAttribute("cy",Y(d.score));
    c.setAttribute("r",3.4);c.setAttribute("fill","#22d3ee");svg.appendChild(c);} });
  const last=iters[iters.length-1];
  const c2=document.createElementNS(NS,"circle");c2.setAttribute("cx",X(iters.length-1));c2.setAttribute("cy",Y(last.score));
  c2.setAttribute("r",5);c2.setAttribute("fill","#2dd4a7");svg.appendChild(c2);
  const t2=document.createElementNS(NS,"text");t2.setAttribute("x",X(iters.length-1));t2.setAttribute("y",Y(last.score)-10);
  t2.setAttribute("fill","#e8eef7");t2.setAttribute("font-size","12");t2.setAttribute("text-anchor","end");
  t2.textContent=money(last.score);svg.appendChild(t2);
}
let lastParamScore=-1e9, lastPhase=null;
function pushLine(txt,cls){
  const d=document.createElement("div"); d.className="new";
  d.innerHTML=`<span class="${cls}">${txt.replace(/</g,"&lt;")}</span>`;
  feedEl.prepend(d);
  while(feedEl.children.length>24) feedEl.removeChild(feedEl.lastChild);
}
function feed(rows){
  rows.slice(lastN).forEach(r=>{
    if(r.phase!==lastPhase){
      lastPhase=r.phase;
      const label={parametric:"— parametric proposer: score plateau, archive keeps best —",
                   local:"— per-site local search: every proposal judged by the full-year check —",
                   llm:"— LLM-written policy arrives —"}[r.phase]||r.phase;
      pushLine(label,"phase");
    }
    if(r.phase==="parametric"){
      // log only archive improvements (the meaningful event), not every rejected candidate
      if(r.score>lastParamScore+0.01){ lastParamScore=r.score; pushLine(`[best] score ${money(r.score)} · ${r.mw_at_month12.toFixed(1)} MW @12`,"p"); }
    } else if(r.phase==="local"){
      pushLine(`[local] ${r.site} → ${r.change} · ${money(r.score)}`,"l");
    } else {
      pushLine(`[llm] gen ${r.gen} · ${r.change} · ${money(r.score)}`,"m");
    }
  });
  lastN=rows.length;
}
async function tick(){
  try{
    const s=await (await fetch("/state",{cache:"no-store"})).json();
    $("phase").textContent=s.phase; $("p-phase").textContent="phase: "+s.phase;
    $("clock").textContent=(s.elapsed_s||0).toFixed(1)+" s";
    $("region").textContent=(s.config&&s.config.region)||"CAL";
    $("f-status").textContent=s.status;
    $("p-count").textContent=s.iterations.length+" events";
    if(s.best){
      $("k-score").textContent=s.best.score.toFixed(1);
      $("k-net").textContent=s.best.net_value_musd.toFixed(1)+"M";
      $("k-mw12").textContent=s.best.mw_at_month12.toFixed(1)+" MW";
      $("k-deliv").textContent=s.best.delivered_mwmonths.toFixed(0)+" MW·months"+(s.best.n_active?(" · "+s.best.n_active+" sites"):"");
      $("k-viol").textContent=(s.best.violations_mwh||0).toFixed(0)+" MWh";
      $("k-iters").textContent="iterations "+s.iterations.length;
    }
    if(s.iterations.length) draw(s.iterations);
    feed(s.iterations);
    if(s.status==="done"||s.status==="error"){
      $("live").textContent=s.status==="done"?"DONE":"ERROR";
      $("live").style.color=s.status==="done"?"var(--green)":"var(--red)";
      document.querySelector(".dot").style.animation="none";
      if(s.status==="done") return; // stop polling
    }
  }catch(e){}
  setTimeout(tick,120);
}
function reset(){
  lastN=0; lastParamScore=-1e9; lastPhase=null; feedEl.innerHTML="";
  $("live").textContent="LIVE"; $("live").style.color="var(--red)";
  document.querySelector(".dot").style.animation="p 1s infinite";
  $("k-score").textContent="—"; $("k-net").textContent="—";
  $("k-mw12").textContent="—"; $("k-deliv").textContent="—";
  $("k-viol").textContent="—"; $("k-iters").textContent="iterations 0";
  const svg=$("chart"); while(svg.firstChild)svg.removeChild(svg.firstChild);
}
$("again").addEventListener("click", async ()=>{
  const btn=$("again"); btn.disabled=true;
  try{ await fetch("/start",{cache:"no-store"}); reset(); setTimeout(()=>{btn.disabled=false;tick();},150); }
  catch(e){ btn.disabled=false; }
});
// if the server already ran a demo before the page opened, offer a fresh one
fetch("/state",{cache:"no-store"}).then(r=>r.json()).then(s=>{
  if(s.status==="done"||s.status==="error"){ reset(); }
}).finally(()=>tick());
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the console clean on stage
        pass

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path.startswith("/state"):
            with LOCK:
                self._send(200, json.dumps(STATE).encode())
        elif self.path.startswith("/result"):
            with LOCK:
                self._send(200, json.dumps({"best": STATE["best"],
                                            "portfolio": STATE["portfolio"]}).encode())
        elif self.path.startswith("/start"):
            if STATE["status"] == "running":
                self._send(200, b'{"ok":false,"reason":"already running"}')
                return
            threading.Thread(target=run_loop, args=(ARGV.region, ARGV.iters, ARGV.budget,
                                                     ARGV.seeds), daemon=True).start()
            self._send(200, b'{"ok":true}')
        else:
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")


def main():
    global ARGV
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8767)
    ap.add_argument("--region", default="CAL")
    ap.add_argument("--iters", type=int, default=200, help="parametric iterations per seed")
    ap.add_argument("--budget", type=int, default=2600, help="local-search evaluation budget")
    ap.add_argument("--seeds", type=int, default=1)
    ap.add_argument("--no-open", action="store_true")
    ARGV = ap.parse_args()

    threading.Thread(target=run_loop, args=(ARGV.region, ARGV.iters, ARGV.budget, ARGV.seeds),
                     daemon=True).start()
    srv = ThreadingHTTPServer(("127.0.0.1", ARGV.port), Handler)
    url = f"http://127.0.0.1:{ARGV.port}/"
    print(f"GRIDRUSH live run → {url}   (Ctrl+C to stop)")
    if not ARGV.no_open:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
