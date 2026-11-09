# GRIDRUSH — a speed-to-power agent for compute

**One line:** GRIDRUSH is an agent that decides *which compute loads to energize, with what firmness,
and with what flexibility*, so that MW that would sit in an interconnection queue for years start
earning in months — without violating the local grid or the availability the customer bought.

Built in one day at **SF x MIT Hack Day: Energy** (AGI House SF, 2026-11-08), track set
“grid-friendly compute” (tracks 1 + 2 + 3: where → how much → how flexible).

---

## Presentation material (start here to understand the project)

| What | Where |
|---|---|
| **AI-generated overview deck** (NotebookLM, from a single source pack) | [`pitch/GRIDRUSH-AI-overview-deck.pdf`](pitch/GRIDRUSH-AI-overview-deck.pdf) |
| **One-page leave-behind** (A4 landscape, everything on one page) | [`pitch/GRIDRUSH-one-pager.pdf`](pitch/GRIDRUSH-one-pager.pdf) |
| **Single source pack** used to generate the deck (18 sections, 5.1k words) | [`NOTEBOOKLM_SOURCE.md`](NOTEBOOKLM_SOURCE.md) |
| **Public site** with all dashboards + download | https://dmitrypehovski.github.io/gridrush/ |
| **3-minute verbatim demo script** + cue card + 16-question Q&A | [`pitch/demo-script.md`](pitch/demo-script.md) |

## The problem, in one number

A data center can be built in 2–3 years; grid interconnection historically takes longer. ERCOT
tracked ~410 GW of large-load requests in March 2026, ~87% of them data centers, against ~7.5 GW
approved to energize since January 2022. On stage, the utility (PG&E) and the track host argued the
same point from opposite sides: *would you connect faster if you accepted 98% availability and
curtailed a few hours a year?*

GRIDRUSH answers that question with a computed portfolio instead of an opinion.

## What the agent does

For 40 candidate edge sites (0.5–10 MW) sharing 8 substations, over a 36-month horizon, the agent
chooses per site:

| Decision | Options |
|---|---|
| connect or not | `skip` / `firm` / `flex` (non-firm, step-up) / `flex + battery` |
| how much | 0.5 … min(nameplate, available headroom) MW |
| availability commitment | **99.99%** (0.88 h/yr curtailment, revenue premium ×1.25) · **99.9%** (8.76 h/yr, ×1.00) · **99%** (87.6 h/yr, ×0.80) |
| speed | firm waits 18–36 months · flexible connects in 5–10 · with an onsite battery 1–3 months later |

The trade is explicit and physical:

- **firm** MW is capped by the substation's *tightest hour* of the year → small and slow;
- **flexible** MW can be several times larger immediately, but the site must drop load in stress hours;
- the **SLA** decides how many stress hours you may drop, and the contract price pays for reliability;
- a **battery** covers the deficit in those hours, at a capex.

The agent’s plan is then checked hour by hour: the evaluator recomputes every substation’s load from
every site on it and scores grid limits plus each site’s own SLA. One honest detail — flexible load
cannot exceed headroom **by construction** (that is what flexible service means: the site is clipped
to what the grid can carry), so for the flexible portfolio the agent actually chooses, the binding
check is the **per-site SLA**, not the violation count. Violations would appear if *firm* capacity
were oversubscribed; we report both numbers and we say which one binds.

## Results (CAL / CAISO, real 2025 hourly replay)

| Strategy | MW online at month 12 | Contract-compliant MW·months | Net value |
|---|---|---|---|
| All **firm**, wait for the queue | **0** | 651 | **$65.1M** |
| Sign **everything non-firm** at max MW | 173 | 3384 gross, mostly non-compliant | **−$449.5M** |
| **GRIDRUSH agent** | **85.4** | **2490.6** | **+$279.9M** |

- **4.30×** the net value of the best honest strategy, **3.82×** the sellable compute
- **0 MWh** of grid violations, **every site meets its own SLA** (no SLA breach energy)
- 32 of 40 sites energized — the agent says no to the rest, which is a decision, not a failure
- the naive “speed at any price” strategy is *loss-making*: speed without reliability is not a business

The interesting part is *how* it wins: it does not pick one availability level globally. It pays for
99.99% where stress hours are rare (and collects the ×1.25 premium) on 16 sites, 99.9% on 6, and
accepts 99% on 10 where the grid is congested — buying 5–10 months of earlier revenue. Batteries and
firm service turn out to be dominated: the exact per-site trade makes them unnecessary.

## How it learns (the RSI loop)

The event asked for “agents that do that testing and get better at it each run”. GRIDRUSH is that
loop, made explicit:

```
proposer → portfolio → simulator (hour-by-hour) → score → keep if better → mutate
```

- `loop/search.py` — a fast mutator over a 9-parameter policy (≈200 generations in ~20 s), with an
  adaptive step and restarts; every generation is logged (`results/loop.json → iterations`) so the
  learning curve is real, not an illustration;
- `loop/local_search.py` — second proposer: per-site proposals (mode × MW × SLA × battery) scored by
  the full-year simulator; only SLA-clean improvements are accepted;
- `rsi_agent/` — the same loop with an **LLM proposer**: the agent writes new policy code
  (`gen_0.py` … `gen_10.py`), the simulator scores it, the best is kept (`rsi_log.json`, `BEST.md`).
  The archive survives between rounds: round 2 resumed from `gen_6` and produced four more
  generations (`rsi_log2.json`, `BEST2.md`) — it converged at **+0.12%**, which is the honest finding
  (exact per-substation DP leaves little room), and one generation regressed and was rejected.
  This is where the result came from: the fast search plateaus at **179** (score), then the LLM agent
  rewrites the policy — an exact per-substation DP — and jumps to **279.9**, beating even a
  hand-written greedy reference ($250M). 7 generations, 1 of them a recorded failure (returned an
  empty portfolio, scored 115) — kept in the log on purpose;
- the policy also **repairs its own plan** (`repair_portfolio`) — plan, verify, shrink MW until every
  site's SLA holds; without this step the plan is optimistic and part of the MW is unsellable.

### The same policy on four operators (no per-region tuning)

Open `web/regions.html` for all four with links to their dashboards.

| Region | 2025 peak | Net value ratio | Compliant MW·months ratio | Violations |
|---|---|---|---|---|
| CAL (CAISO) | 43,860 MW | 4.30× | 3.82× | 0 |
| TEX (ERCOT) | 83,597 MW | 3.41× | 2.79× | 0 |
| MIDA (PJM) | 160,560 MW | 4.07× | 3.57× | 0 |
| MIDW (MISO) | 120,343 MW | 3.88× | 3.33× | 0 |

### Physics check

The main engine is an hourly capacity verifier on a headroom profile (the shape of data a utility
publishes — PG&E ICA gives 576 hourly values per line section). On top of it, `sim/powerflow.py` runs
a **real AC power flow** (pandapower `mv_oberrhein`: a real 20 kV German MV feeder, 179 buses,
2×25 MVA). Base case converges at min V 0.9756 p.u.; the feeder has **8.2 MW of spare capacity** with
0 violations, while our five largest sites need **31.8 MW** — they do not fit on one feeder (71
violations, voltage collapse). That is exactly why this is a *siting* problem: 0.5–10 MW edge sites
are the right unit, and the agent has to distribute them. `web/physics.html` shows every number from a measured run.

**Two limits from one real feeder — 8.2 MW and 6.53 MW.** Both are measured, and they answer
different questions. **8.2 MW** is the first thermal violation when the top-5 site profile is scaled
uniformly (transformer T142 reaches 100.4 %). **6.53 MW** is the conservative admission limit we
enforce: the same total added load spread over the five best-headroom buses in proportion to their
headroom, with every bus at or above 0.95785 p.u. and every branch at or below 100 %. We quote 6.53 on
stage because it is the number the optimiser actually uses.

**Does 4.30× survive if the economics are wrong?** The ratio is invariant to the margin *level* —
the same prices scale the agent and the baselines together: 4.30× at $0.033, $0.10 and $0.30 per
MW-month (`results/sensitivity.json`). What is sensitive is the SLA premium spread: flattening
1.25 / 1.00 / 0.80 to 1.10 / 1.00 / 0.95, and halving the penalty, still gives **4.04×**. The
physical ratio — **3.82× contract-compliant MW-months, 2490.6 vs 651.3** — contains no prices at all.
What rests on assumptions is the absolute dollar level ($279.9M), not the comparison.

**Real PG&E data.** `sim/real_sites.py` rebuilds the site model from the public **PG&E GRIP Data
Portal** (no key): 8 real substations with real coordinates, facility ratings and 2026 loadings.
Running the same agent on them gives **1.22×** (397.7 MW online at month 12, 11,533 sellable
MW·months, zero violations) — the premium collapses because, at the *substation aggregate* level,
these substations are large and not the bottleneck. PG&E's own Grid Needs Assessment shows where the
constraint actually lives: in a 2,000-circuit sample, **124 of the 1,462 circuits that actually carry data
(8.5%; 538 of the 2,000 sampled rows are a −99.99 sentinel) are already deficient for 2026** (up to
12.4 MW). That is the next data we need, and it is why the ask is circuit-level ICA.
`web/dashboard_real.html`, `results/loop_real.json`, `data/sites_CAL_real.json`.

**Physics in the loop.** The measured admission limit — **6.53 MW of new load per MV feeder**
(first violation at 7.03 MW) — is not just a check: it is passed into the portfolio builder
itself (`build_portfolio(..., sub_limit_mw=...)`, driven by `sim/physics_gate.py` →
`loop/run_physics.py`), so the policy physically cannot over-subscribe a feeder; the final plan is
then verified with eight real AC-PF runs. With real physics inside the loop the same agent reaches
**2.39× instead of 4.30×** (net $155.5M): a real feeder takes ~6.5 MW, not the 20–60 MW the
synthetic capacities assumed. Both numbers are reported — the delta is the value of real utility
ICA data. See `results/FINAL_NUMBERS.md`.

## What is real and what is synthetic

Honesty is part of the demo. Every number on screen is labeled.

**Real (public):**
- hourly 2025 demand, day-ahead forecast and generation-by-fuel for the 12 largest US balancing
  authorities — EIA-930, public domain (`data/us_grid_hourly_2025.csv`, shipped in this repo);
- the grid stress *shape* (`u[h] = demand / p95(demand)`) that drives headroom comes from that data;
- interconnection timelines order-of-magnitude, curtailment economics and the availability/premium
  logic are taken from the hackathon repo’s catalogue (MISO 18–36 month large-load process,
  Firm Service Step-Up, ERCOT batch studies) and from the talks on stage.

**Synthetic (documented in `sim/assumptions.md`):**
- 40 sites / 8 substations geometry, capacity, loading factors;
- exact queue months per site, battery capex ($0.35M/MW + $0.25M/MWh), revenue ($0.10M per MW-month),
  SLA price multipliers (1.25 / 1.00 / 0.80), SLA penalty multiplier;
- the 2025 year is replayed as a representative year across the 36-month horizon.

Data-quality caveats we found and handled: 7 corrupt demand rows in the CSV (interpolated), 26 rows
with an empty demand value (interpolated), one 24-hour ERCOT gap, and a physically implausible
`solar_mw` column (not used for capacity or stress
calculations; only the demand shape is used).

## Run it

```bash
cd gridrush
python3 loop/run.py --region CAL --iters 180      # agent loop → results/loop.json
python3 web/build.py results/loop.json            # single-file dashboard → web/dashboard.html
open web/dashboard.html                           # works offline, no network, no CDN
```

Dev/mock mode without the simulator: `python3 loop/run.py --mock --iters 120`.

## Layout

| Path | What |
|---|---|
| `sim/` | model: `curves.py` (single source of truth for headroom), `engine.py` (hour-by-hour verifier + economics), `baselines.py` (3 honest strategies), `run.py` → `results/sim_baseline.json`, `assumptions.md` |
| `loop/` | RSI loop: `policy.py` (parameterized policy + self-repair), `search.py` (mutator), `local_search.py` (per-site proposer), `run.py` (CLI → `results/loop.json`) |
| `results/FINAL_NUMBERS.md` | the frozen numbers every pitch artifact references |
| `rsi_agent/` | LLM-in-the-loop generations: `eval.py`, `gen_*.py`, `rsi_log.json`, `BEST.md` |
| `web/` | `dashboard.html` — one self-contained offline file (loop replay, portfolio map, stress day, strategy comparison); `regions.html` — four operators + physics variant; `dashboard_physics.html` — physics-in-the-loop run; `live_server.py` — live run streamed to the browser (`python3 web/live_server.py`, ~11 s) |
| `pitch/one-pager.html` + `GRIDRUSH-one-pager.pdf` | one-page leave-behind for judges, generated from the frozen JSON by `build_onepager.py` |
| `pitch/` | `submission.md`, `demo-script.md` (3 min, timed), `qa-defense.md`, `hooks.md` |
| `data/` | EIA-930 hourly 2025 starter dataset (public domain) |
| `CONTRACT.md` | frozen model/API/JSON contract used to build this in 4 hours |

## What we would do next

1. Replace synthetic substation data with real utility hosting capacity (PG&E GRIP/ICA publishes 576
   hourly values per line section) and real interconnection queue positions (MISO, ERCOT batch data).
2. Replace the headroom model with AC power flow + N-1 (`pandapower` / `powermodels` on synthetic
   grids) so capacity is a physics result, not a profile input.
3. Let the agent negotiate the contract, not just pick from it: durations, offtaker availability tiers,
   and multi-site aggregation into a single grid-service offer (track 4).
4. Turn the loop into an operations loop: re-run weekly as queue positions and load forecasts move.

**Ask:** real hosting-capacity and queue data from a utility or an edge developer — one region is
enough to replace the biggest synthetic assumption.
