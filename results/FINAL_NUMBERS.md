# GRIDRUSH — FINAL NUMBERS (frozen 2026-11-08 ~13:00 PT)

Source: `results/loop.json` (region = CAL / CAISO); engine `sim/engine.py` was frozen by the
sim-engineer (determinism verified, `sim/test_engine.py` 26/26 ok).

## Main table (for the slide and the submission)

| Strategy | MW online by month 12 | Contract-compliant MW·months | Net value |
|---|---|---|---|
| All **firm**, wait for the queue (`queue_order`) | **0** | 651.3 | **$65.1M** |
| Sign **everything non-firm** at max MW (`max_mw_no_flex`) | 172.6 | 1447.9 (out of 3384 gross) | **−$449.5M** |
| **GRIDRUSH agent** (`gen_6`, LLM-written policy) | **85.4** | **2490.6** | **+$279.9M** |

Ratios: **4.30×** net value, **3.82×** contract-compliant MW·months, **85.4 MW vs 0 MW** by month
12. Grid violations: **0.000 MWh**. SLA breach: **0.000 MWh** (each site's own SLA is met).
**32 sites out of 40** connected (the agent turned down 8).

## Learning loop

`iterations` = **207** points: 200 parametric-mutator iterations + 7 LLM-proposer generations
(`rsi_agent/gen_0..gen_6`, log `rsi_agent/rsi_log.json`). Best-so-far curve: **108.4 → 279.9**.

Key story beat: the parametric search hits a plateau at **~178.6**; the LLM agent rewrites the
policy (exact DP over substations, flex-only) and jumps **178.6 → 269.6 → 279.9** (+57%).

## The agent's portfolio

- 32 sites, all `flex`, about **~104 MW** in total (out of 208.5 MW nameplate across 40 sites)
- SLA mix: **16 sites at 99.99%** (×1.25 premium), **6 sites at 99.9%** (×1.00), **10 sites at 99%** (×0.80)
- batteries are not used (in the model they are dominated by flex@99.99% and create violation risk)
- energize: months 5–12 (firm queue 18–36 months)

## Stress day (for worst-day chart)

- `grid.stress_day.date` = **2025-08-21** (CAISO), peak **43,860 MW at 20:00 local**
- required curtailment at 20:00: **agent ≈ 1.9 MW**, **naive portfolio ≈ 28 MW**
  (exact series: `grid.stress_day.curtail_mw`, `curtail_mw_naive`)

## Data facts (can cite)

- 12 US balancing authorities, 3,513 TWh, hourly 2025, EIA-930 public domain
- CAISO duck curve worst day 2025-03-08: net load −1,140 MW at 13:00 → +22,682 MW in 6 hours
- flex-worthy hours (top-1% demand OR top-1% ramp): 2.0% of the year, 160–177 hours per operator
- ERCOT: 410 GW large-load requests (87% data centers) vs 7.5 GW approved since 2022
- 1 MW over 3–4 years = $5M (from the stage); interconnection 7–10 years (PG&E, from the stage)

## Four regions, one and the same policy (no tuning)

| region | ratio net | ratio MW·months | net $M | compliant MW·months | MW@12 | violations |
|---|---|---|---|---|---|---|
| CAL (CAISO) | **4.30×** | 3.82× | 279.91 | 2490.6 | 85.4 | 0 |
| TEX (ERCOT) | 3.41× | 2.79× | 304.46 | 2491.7 | 84.1 | 0 |
| MIDA (PJM) | 4.07× | 3.57× | 275.30 | 2415.7 | 82.4 | 0 |
| MIDW (MISO) | 3.88× | 3.33× | 277.84 | 2390.4 | 81.3 | 0 |

Source: `results/loop_{CAL,TEX,MIDA,MIDW}.json` (the same `rsi_agent/gen_6.py`, `--iters 60 --seeds 1`).
Wording for the judges: "the same policy, four operators, 3.4–4.3× and zero violations — no per-region
tuning".

## Physics-in-the-loop (closes the "AC power flow outside the loop" objection)

The real AC power flow (`pandapower`, `mv_oberrhein`, a genuine 20 kV feeder) measures the
**allowable load addition per substation: 6.53 MW** (first violation at 7.03 MW; with a min V
limit of 0.95785 p.u., loading 100.0%). This limit is built into the loop as an admission
constraint: the search has to spread compute across substations, and the final plan is checked
with 8 real AC-PF runs.

| variant | net value | ratio | compliant MW·months | MW@12 | AC-PF |
|---|---|---|---|---|---|
| profile model (ICA-style headroom) | **$279.9M** | **4.30×** | 2490.6 | 85.4 | not checked |
| **physics-in-the-loop** | **$155.5M** | **2.39×** | 1313 | 44.7 | **8/8 substations clean** |

Delta **−44.5% net value**: the real feeder takes ~6.5 MW of new load, not the 20–60 MW that
the synthetic capacities allowed. That is the price of real physics — and the value of real
utility ICA data. Commands: `<venv>/python sim/physics_gate.py` (the limit), then
`<venv>/python loop/run_physics.py --warm-start results/loop.json --budget 2500` (the optimization),
`python3 web/build.py results/loop_physics.json -o web/dashboard_physics.html`.

## Real PG&E data instead of synthetic capacities

`sim/real_sites.py` pulls the public PG&E GRIP Data Portal (ArcGIS REST, no key):
8 real PG&E substations — real names, coordinates, aggregate facility rating and
**2026 load** (DFCircuitsView layer), sorted by real headroom:

| substation | division | rating | load 2026 | lf |
|---|---|---|---|---|
| SAN RAMON | Mission | 302.2 MW | 136.9 MW | 0.453 |
| CLAYTON | Diablo | 193.1 | 124.9 | 0.647 |
| CAMP EVERS | Central Coast | 100.4 | 38.5 | 0.383 |
| TASSAJARA | Diablo | 184.2 | 130.2 | 0.707 |
| STOCKDALE | Kern | 327.1 | 275.2 | 0.841 |
| WOODWARD | Fresno | 174.6 | 124.5 | 0.713 |
| FIGARDEN | Fresno | 225.4 | 180.2 | 0.799 |
| COTTLE | Yosemite | 112.9 | 70.5 | 0.624 |

Run: `python3 sim/real_sites.py` → `GRIDRUSH_SITES=real python3 loop/run.py --region CAL ...`
→ `results/loop_real.json` → `web/dashboard_real.html`.

**Result: 1.22×, 397.7 MW@12, 11,533 MW·months, 0 violations, all 40 sites.**
The honest conclusion: at the **aggregate substation level** the real PG&E substations are large
and are not the bottleneck — the flexibility premium almost disappears. The limit lives at the
feeder level: in a sample of 2,000 PG&E GNA circuits, **124 circuits (6.2%) are already deficient
in 2026** (up to 12.4 MW). That is exactly the next step stated in the ask.

## RSI: second round (closes the "one run per day" objection)

The archive is preserved, so the loop can be continued: round 2 started from `gen_6` (279.9082)
and recorded `gen_7 … gen_10`. The best is **gen_9 = 280.256 (+0.12%)**: the policy has converged,
and that is an honest result (in the per-substation exact DP for flex-only there is nothing left
to improve). `gen_10` got worse (−1.4) and was rejected by the keep-best rule. Logs:
`rsi_agent/rsi_log.json`, `rsi_agent/rsi_log2.json`, `rsi_agent/BEST2.md`. The headline stays on
`gen_6`; round 2 is proof of resumability.

## Regions as first-class

`web/regions.html` — one page with all four operators (CAL 4.30× · TEX 3.41× · MIDA 4.07× ·
MIDW 3.88×, violations 0 everywhere) + the physics-in-the-loop card with links to
`dashboard_<REGION>.html`. Build: `python3 web/build_regions.py`.

## What NOT to say

- "real data" without "synthetic site geometry"; "zero violations" without "in the model";
  "we made $279.9M" (that's modelled compute margin over 36 months on a synthetic portfolio);
  any solar numbers from that CSV (the column isn't physical, it isn't used in the calculations).
