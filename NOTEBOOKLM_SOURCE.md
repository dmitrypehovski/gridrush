# GRIDRUSH — complete project source pack for generating a presentation

> This document is a single, self-contained source of truth about the GRIDRUSH project, built at
> the SF × MIT Hack Day: Energy (AGI House SF, 8 November 2026). It is written to be read by an AI
> assistant and turned into a presentation. Every claim here is either a measured number in the
> project repository or an explicitly labelled synthetic modelling assumption. Nothing here is
> rounded up, and the limitations are stated as plainly as the results.

---

## 1. One-paragraph summary

GRIDRUSH is a **speed-to-power agent for grid-friendly compute**. A data centre can be built in
2–3 years, but connecting it to the electricity grid historically takes 7–10 years. GRIDRUSH decides,
for 40 candidate edge-compute sites on 8 substations, **which ones to connect, at what power, under
which availability commitment (99.99% / 99.9% / 99%) and with what flexibility**, so that compute comes
online in months instead of years — without violating local grid limits or the reliability the
customer bought. It learns by proposing plans, judging each one with an all-8,760-hour simulation of
2025, and keeping the best; a large-language-model agent then rewrote the policy itself. Measured
against the two strategies operators use today, the agent achieves **4.30× the net value**, **85.4 MW
online by month 12** (versus 0), and **zero modelled grid violations with zero SLA breach**. When the
same loop is run with a measured AC power-flow admission limit, the result honestly drops to
**2.39×**; when run on eight **real PG&E substations** (real ratings and 2026 loadings), it drops to
**1.22×** and locates the real constraint at the circuit level.

---

## 2. The event and the question we answered

The hackathon theme was "grid-friendly compute", across four tracks:
Track 1 — identifying suitable sites; Track 2 — assessing grid capacity at the edge;
Track 3 — managing loads; Track 4 — aggregating distributed compute.

The event statement, quoted verbatim from the organisers' repository: *"We want agents that do that
testing and get better at it each run."* Judging criteria listed on stage: technical depth, the agentic
loop (recursive self-improvement), energy-system relevance, innovation, simulation, alignment with the
track, the technical demo, and "the learning capabilities of your agents".

Three statements from the stage shaped the project:

1. A PG&E engineer, on the record: *"If you're a data center or if you want to connect a data center
   to the grid, it'll take you 7 to 10 years to do that."*
2. The same engineer, when a participant asked whether an interconnection could be faster: *"If you
   can reduce your availability down to like 98% or something like that … if the data center is
   willing to curtail their load … for a few days out of the year, that could drastically improve the
   chances and the speed with which they could connect."* Someone in the room then asked: *"But what
   if it was guaranteed capacity for 98% of the time?"* The utility answer was: *"We're trying."*
3. The track host, on interconnection economics: *"Each megawatt would be $5,000,000 for 3 to 4
   years."* And on the queue: *"Some sites have been in the interconnection queue for a year, versus
   some have been approved in days."*

GRIDRUSH exists to answer the "98% question" with a number instead of an opinion.

---

## 3. The problem in four numbers

- **7–10 years** — typical time to connect a large load to the grid (quoted on stage by PG&E).
- **2–3 years** — typical time to build a data centre (IEA 2025, in the hackathon catalogue).
- **~410 GW** — large-load requests tracked by ERCOT in March 2026, about **87%** of them data
  centres, against about **7.5 GW** actually approved to energise since January 2022.
- **~176 hours a year (2% of all hours)** — the "flex-worthy" hours in the 2025 data: hours that are
  either in the top 1% of demand or the top 1% of the evening ramp. This is the trade: compute gives
  up about 2% of the hours and gets months of running time in return.

---

## 4. What the agent decides

The model has **8 substations**, each hosting **5 candidate sites**, so **40 sites**. Each site can
take between **0.5 and 10 MW**. The horizon is **36 months**.

For every site the agent chooses:

| Decision | Options |
|---|---|
| connect at all? | skip / connect |
| connection type | **firm** (guaranteed, no curtailment) / **flexible** (non-firm / step-up, may be curtailed in stress hours) / **flexible + battery** |
| size | 0.5 … minimum(nameplate ceiling, available headroom) MW |
| availability commitment (SLA) | **99.99%** (0.876 h/yr curtailment, revenue premium ×1.25) · **99.9%** (8.76 h/yr, ×1.00) · **99%** (87.6 h/yr, ×0.80) |
| speed (implied) | firm waits **18–36 months**; flexible connects in **5–10 months**; a battery adds **1–3 months** on top of the flexible connection |

The agent may also refuse a site. In the final portfolio it connects **32 of 40 sites** and refuses 8.

---

## 5. The physics and economics of the model

### 5.1 Headroom (the grid side)

For each substation there is a capacity `cap_mw`, a loading factor `lf`, and an hourly normalised
demand shape `u[h]` from real 2025 data, where `u = demand / p95(demand)`, so `u = 1` at the 95th
percentile and about `1.30` at the annual peak. Existing load at a substation is
`e[h] = lf × cap_mw × u[h]`. Free headroom for a site is
`H[h] = cap_mw − e[h] − 2% margin`.

Consequences that drive the whole story:

- **Firm capacity** is limited by the **minimum** headroom over the year, because a firm customer
  cannot be curtailed. That makes firm capacity small (a few percent to a few tens of percent of the
  substation capacity) and slow (18–36 months).
- **Flexible capacity** can be several times larger immediately (5–10 months), but the site must
  reduce load in stress hours. **How many hours a year is the SLA** — and the SLA is priced.

### 5.2 Flexibility and reliability (what a site may do)

- Flexible load is **clipped to the available headroom** in every hour. That is what flexible service
  physically means: the site is curtailed to what the grid can carry. This is a modelling decision
  stated openly: for a flexible-only portfolio, "zero violations" is structural, not a discovery.
  The constraint that actually binds is the **per-site SLA**.
- A site's availability is `1 − curtailed_hours / 8760`. If availability falls below its declared
  SLA, the contract is violated; breach energy is penalised at **5× the compute margin per MWh**.
- A battery can cover the deficit in stress hours; its energy budget is daily (`0.9 × battery_mwh`
  usable per day), and it costs **$0.35M per MW** plus **$0.25M per MWh**.

### 5.3 Economics (synthetic, documented)

| Parameter | Value | Status |
|---|---|---|
| Compute margin | **$0.10M per MW-month** (≈ $1.2M per MW-year) | synthetic; order of magnitude from the stage quote "$5M per MW for 3–4 years" |
| SLA revenue multipliers | **1.25 / 1.00 / 0.80** for 99.99% / 99.9% / 99% | synthetic; sign and ordering from the stage: "you get a premium for six nines" |
| SLA breach penalty | **5× margin per MWh** beyond the declared curtailment budget | synthetic |
| Battery capex | **$0.35M/MW + $0.25M/MWh** | synthetic, market order of magnitude |
| Interconnection waits | firm **18–36 months**, flexible **5–10 months** | informed by MISO's 18–36 month large-load process and Firm Service Step-Up, ERCOT batch studies |
| Site geometry, ceilings, fibre, permit days | synthetic, seeded, documented | synthetic |
| Hourly demand shape | **real** 2025 EIA-930 data for 12 US balancing authorities | real, public domain |

The objective is **net value over 36 months**:
`net = Σ (margin × revenue multiplier × MW × active months × availability) − battery capex − SLA penalties`,
and the search score subtracts hard penalties for grid violations and SLA breach.

---

## 6. The simulator / verifier

`sim/engine.py` implements a deterministic, vectorised, hour-by-hour evaluation:

1. Parse the portfolio into arrays (site, mode, MW, SLA, battery energy).
2. Allocate substation capacity hour by hour: firm load is placed first and is never curtailed;
   flexible sites are served in the order of their energisation month and receive
   `min(requested MW, remaining headroom)`.
3. Battery cover: per site, per day, the deepest deficits are covered first from the daily energy
   budget; the uncovered remainder is curtailment.
4. Independent bookkeeping pass: total substation load is recomputed from existing load plus every
   site's actual load, and any excursion above capacity is counted as violations (MWh).
5. Availability, SLA breach energy, delivered and contract-compliant MW-months, capex, penalties,
   net value and score.

Performance: **~3.7 ms per evaluation** of 40 sites × 8,760 hours; the whole test suite is
**26 tests, 26 pass, 0.27 s**; the main optimisation run takes a few seconds. Two cold runs produce
identical results to six decimal places.

**Honest caveat, stated in the repository:** because flexible load is clipped to headroom, violations
can only arise from oversubscribed *firm* capacity, and the agent chooses no firm sites. So the
verifier's binding signal for this portfolio is the **SLA check**, not the violation count.

---

## 7. How the agent learns (the RSI loop)

The loop is exactly what the event asked for: propose → verify → score → keep the best → propose again.

- **Proposer 1 (fast).** A 9-parameter policy (target fraction, SLA bias, speed weight, firm weight,
  battery appetite, risk aversion, size preference, wait penalty, substation ordering) is mutated with
  an adaptive-step hill climb with restarts. Each candidate is converted into a full portfolio and
  scored by the simulator. The loop runs **200 generations** and logs every one.
- **Proposer 2 (per-site).** A local search proposes, for each site, variants of
  (mode × MW × SLA × battery energy) and lets the simulator judge each variant. Only SLA-clean
  improvements are accepted. This produces the intermediate steps visible on the learning curve.
- **Proposer 3 (LLM code).** An LLM agent writes **policy code** (seven generations, `gen_0 … gen_6`),
  which is scored by the same verifier; the archive keeps the best. One generation is a recorded
  failure: it returned an empty portfolio and scored 115. The log keeps the failures on purpose.
- **Self-repair.** Before scoring, the policy repairs its own plan: it shrinks MW until every site's
  SLA holds (the substation is shared, so two flexible sites compete for the same headroom).

**The learning curve is the demo's evidence.** The curve starts at about **108** in score units,
climbs as the fast proposer works, **plateaus at 179**, and then the LLM-written policy jumps to
**269.6 → 277.2 → 279.9**. Total: **207 iterations** (200 parametric + 7 LLM). This plateau-then-jump
is the "learning capabilities of your agents" criterion, visible in one animation.

**Round 2 (continual improvement).** The archive persists, so the loop was resumed from the best
policy and ran six more generations (`gen_7 … gen_12`). The best is **280.256, +0.12%** — a plateau,
and the honest finding is that the policy space is exhausted: an exact dynamic program over the
achievable prefixes per substation is the optimum of the admissible flexible-only space. Firm is
dominated (18–36 months versus 5–10, and forcing firm sites breaks the tightest-hour headroom),
batteries are negative on all 32 candidate sites. One generation regressed and was rejected — the
keep-best rule works.

---

## 8. The result

All numbers below are from the frozen run `results/loop.json` (region CAL = CAISO, 36 months), and
every baseline is included in the JSON.

| Strategy | MW online at month 12 | Contract-compliant MW-months | Net value |
|---|---|---|---|
| All **firm**, wait for the queue (what operators do today) | **0.0** | 651.3 | **$65.1M** |
| Sign **everything non-firm** at maximum MW (speed without discipline) | 172.6 | 1,447.9 of 3,384 gross | **−$449.5M** |
| **GRIDRUSH agent** | **85.4** | **2,490.6** | **+$279.9M** |

- **4.30×** the net value of the best honest strategy; **3.82×** the sellable ("contract-compliant")
  megawatt-months (651.3 → 2,490.6).
- **0.0 MWh** modelled grid violations and **0.0 MWh** SLA breach energy.
- **32 of 40 sites** energised; the agent refuses the other 8 — refusing is a decision, not a failure.
- The third row is the punchline: speed without reliability is **loss-making** (−$449.5M after
  1.15M MWh of SLA breach energy).

**What the agent actually chose.** No firm sites, no batteries, 32 flexible sites, and a **mix of
availability tiers**: 16 sites at **99.99%** (collecting the ×1.25 premium where stress hours are
rare), 6 at **99.9%**, and 10 at **99%** where the grid is congested and the alternative would be no
connection at all. This per-site trade — not one global availability level — is the core insight.

**Stress day (real 2025 data, CAISO, 21 August 2025).** Peak demand **43,860 MW at 20:00 local**, after
sunset. Required curtailment by hour:

| Hour | Naive portfolio | GRIDRUSH |
|---|---|---|
| **18:00** (evening ramp) | **28.4 MW** | **1.0 MW** |
| 20:00 (demand peak) | 18.2 MW | 0.0 MW |

The line to say on stage: *"At six p.m. the naive plan must shed twenty-eight megawatts. GRIDRUSH
never sheds more than one."*

---

## 9. Reality checks (the part that keeps the project honest)

### 9.1 Real AC power flow

The main engine scores sites on an hourly headroom profile — the shape of data a utility publishes
(PG&E's ICA publishes 576 hourly values per line section). On top of that, the project runs a **real
AC power flow** with `pandapower` on `mv_oberrhein`, a real 20 kV German medium-voltage feeder
(179 buses, 181 lines, two 25 MVA 110/20 kV transformers, 37.1 MW served).

Measured facts:

- Base case: converged, zero violations, minimum voltage **0.97562 p.u.**, maximum transformer loading
  85.5%.
- Largest added load at a single bus that keeps zero violations: **2.84–6.60 MW** depending on the bus
  (15 load-centre buses tested); the transformers bind, not the lines.
- **Spare feeder capacity: 8.2 MW** (first thermal violation at 8.44 MW). This figure comes from
  uniformly scaling the top-5 site profile.
- **Conservative admission limit we enforce: 6.53 MW** — the same total added load distributed over the
  five best-headroom buses in proportion to their headroom, with every bus at or above 0.95785 p.u. and
  every branch at or below 100% of rating. The two numbers answer different questions: 8.2 is the
  first thermal violation; 6.53 is the limit the optimiser actually uses.
- The five largest sites total **31.8 MW** — **they do not fit on one feeder** (71 violations, voltage
  collapse). This is a **siting** problem, not a megawatt problem: 0.5–10 MW edge sites are the right
  unit size, and they must be distributed.

### 9.2 Physics inside the loop

The measured limit is not a post-hoc check: it is passed **into the portfolio builder** as a hard
per-substation cap, so the policy physically cannot oversubscribe a feeder. The final plan is then
verified with **eight real AC power-flow runs — 8 of 8 substations clean**.

| Variant | Net value | Ratio | MW at month 12 | AC power flow |
|---|---|---|---|---|
| Profile model (ICA-style headroom curve) | $279.9M | **4.30×** | 85.4 | not checked |
| **Physics inside the loop** | **$155.5M** | **2.39×** | 44.7 | **8/8 clean** |

The drop of **−44.5%** is the honest cost of real physics: a real feeder of this class takes ~6.5 MW,
not the 20–60 MW the synthetic capacities assumed. Both numbers are reported; the difference is the
value of real utility data.

### 9.3 Real PG&E data

The site model can be rebuilt on the **public PG&E GRIP Data Portal** (ArcGIS REST, no key): eight real
substations with real coordinates, facility ratings and **2026 loadings**. Examples:
SAN RAMON (Mission division) 302.2 MW rating / 136.9 MW load; STOCKDALE (Kern) 327.1 / 275.2;
CLAYTON (Diablo) 193.1 / 124.9; CAMP EVERS (Central Coast) 100.4 / 38.5.

Running the same agent policy on those real substations gives **1.22×**, **397.7 MW at month 12**,
**11,533 contract-compliant MW-months**, **$1,410.1M** net, zero violations, all 40 sites.

**The most valuable finding of the project:** at the **substation aggregate** level, real PG&E
substations are large and **are not the bottleneck**, so the value of flexibility almost disappears.
The constraint lives at the **circuit** level. PG&E's own public Grid Needs Assessment data shows it:
in a sample of **2,000 circuits, 124** had a positive 2026 deficiency (up to 12.4 MW). Of those 2,000
rows, 538 carry a −99.99 "no data" sentinel, so the honest share is **124 of 1,462 circuits with data
= 8.5%**. That is precisely the data GRIDRUSH asks for as the next step.

---

## 10. Four operators, one policy, no tuning

The same frozen policy, evaluated on 2025 hourly data of four US grid operators:

| Region | 2025 peak | Net-value ratio | Compliant MW-months ratio | Violations |
|---|---|---|---|---|
| CAL — CAISO (California) | 43,860 MW | **4.30×** | 3.82× | 0 |
| TEX — ERCOT (Texas) | 83,597 MW | 3.41× | 2.79× | 0 |
| MIDA — PJM (Mid-Atlantic) | 160,560 MW | 4.07× | 3.57× | 0 |
| MIDW — MISO (Midwest) | 120,343 MW | 3.88× | 3.33× | 0 |

No per-region tuning. Headline uses CAL because it has the sharpest peak and the largest firm/flex gap.

---

## 11. Robustness: does 4.30× depend on the synthetic economics?

Re-evaluated with patched engine constants (same agent portfolio, same three baselines):

| Scenario | Net-value ratio | Compliant MW-months ratio |
|---|---|---|
| Base: margin $0.10/MW-month, SLA premium 1.25/1.00/0.80, penalty 5× | **4.30×** | 3.82× |
| Margin divided by 3 ($0.033/MW-month) | **4.30×** | 3.82× |
| Margin multiplied by 3 ($0.30/MW-month) | **4.30×** | 3.82× |
| Flat SLA premium (1.10/1.00/0.95) | 4.04× | 3.82× |
| SLA penalty doubled | 4.04× | 3.82× |
| Stress: margin/3 + flat SLA + penalty ×2 | 4.04× | 3.82× |

**Findings:** the net-value ratio is **invariant to the margin level** — the same prices scale the agent
and the baselines together. The **physical ratio (3.82×, 2,490.6 versus 651.3 contract-compliant
MW-months) contains no prices at all**. Only the SLA premium spread moves it, and it stays above 4×.
What is assumption-dependent is the **absolute dollar level** ($279.9M), not the comparison.

---

## 12. What is real and what is synthetic (say this before anyone asks)

**Real:**
- Hourly 2025 demand, day-ahead forecast and generation-by-fuel for the 12 largest US balancing
  authorities: EIA-930, public domain, 105,120 rows (8,760 hours × 12 operators), shipped with the
  project.
- The measured AC power-flow study on the real `mv_oberrhein` 20 kV feeder.
- Eight real PG&E substations: names, coordinates, facility ratings, 2026 loadings (public GRIP portal).

**Synthetic and documented:**
- Which sites sit inside a substation, site ceilings, fibre flags, permit days.
- Interconnection waits, battery capex, compute margin, SLA multipliers, SLA penalty.
- The 2025 year is replayed as a representative year over a 36-month horizon.

**Data-quality handling:** 7 corrupt demand rows (interpolated), 26 rows with an empty demand value
(interpolated), one 24-hour ERCOT gap (filled), and a physically implausible `solar_mw` column that is
**not used** for capacity or stress calculations.

---

## 13. Limitations and next steps

1. **The headline rests on synthetic economics.** The ratio is robust to the margin level and the
   physical ratio is price-free, but the absolute dollar figure is modelled. The project says so
   on screen and in its "what not to say" list.
2. **The baseline is honest but weak.** "All firm" yields only 651 MW-months at 200 MW of nameplate
   because firm capacity is capped by the tightest hour of the year. That is a real strategy, not a
   straw man — but it is a low bar, which is exactly why the real-PG&E result (1.22×) matters.
3. **The violation check is structural for flexible service** (see §6). The binding check is the SLA.
4. **The site model is synthetic**: no specific project site, no circuit-level interconnection study.
5. **Next steps:** real circuit-level ICA and queue data (that is the ask), AC power flow inside the
   optimisation for all regions, aggregation of many sites into one grid service (Track 4), and a
   longer-horizon operations loop that re-runs weekly as prices and queue positions move.

---

## 14. Project artefacts and how to run it

- `README.md` — what it is, results, layout, how to run.
- `results/FINAL_NUMBERS.md` — every frozen number and the "what not to say" list.
- `results/loop.json` — main run: 207 iterations, three baselines, per-site details.
- `results/loop_physics.json`, `results/physics_in_loop.json`, `results/physics_gate.json` — the
  physics-inside-the-loop run, the per-substation AC power-flow verdicts, and the measured limit.
- `results/loop_real.json`, `data/sites_CAL_real.json`, `results/pge_gna_sample.json` — the real
  PG&E run and its evidence.
- `results/sensitivity.json` — the robustness scenarios.
- `rsi_agent/` — the LLM proposer: `gen_0.py … gen_12.py`, `rsi_log.json`, `rsi_log2.json`, `BEST.md`, `BEST2.md`.
- `sim/` — `curves.py` (single source of truth for headroom), `engine.py` (hour-by-hour evaluator),
  `baselines.py` (three honest strategies), `powerflow.py`, `physics_gate.py`, `real_sites.py`,
  `assumptions.md` (every synthetic parameter with its source).
- `web/` — offline single-file dashboards: the stage dashboard, per-region dashboards, the physics
  page, the real-data page, and `live_server.py` (an 11-second live run streamed to the browser).
- `pitch/` — the 3-minute verbatim script, cue card, 16-question Q&A defence, hooks, submission text,
  and a one-page PDF leave-behind.
- `docs/` — the public static site (GitHub Pages) with a top-level "download the whole project" link.

```bash
python3 loop/run.py --region CAL --iters 200 --seeds 4 --policy-file rsi_agent/gen_6.py
python3 web/build.py results/loop.json          # → single-file dashboard
/path/to/venv/python sim/physics_gate.py        # measured AC-PF limit (needs pandapower)
/path/to/venv/python loop/run_physics.py --warm-start results/loop.json
python3 sim/real_sites.py                       # rebuild the site model from PG&E GRIP
```

Everything is offline: no network, no API keys, no external services.

---

## 15. Q&A — the sixteen questions judges are most likely to ask

**Q1. Is this real data?** The demand shape is: EIA-930, 2025, 12 US operators, public domain. The
site geometry, timelines and costs are synthetic and labelled as such on screen and in
`sim/assumptions.md`. The AC power flow is real; the eight PG&E substations are real.

**Q2. Where is the power flow?** Two levels. The engine is an hourly headroom verifier (the shape of
utility ICA data). On top, `pandapower` runs a real AC power flow on a real 20 kV feeder: base case
0.9756 p.u., 8.2 MW spare, our five largest sites need 31.8 MW, so they cannot share one feeder.
And the measured limit is enforced *inside* the optimiser, with all eight substations passing.

**Q3. Why is the firm baseline so weak?** Because firm capacity is capped by the substation's tightest
hour — a real property of firm service, not a straw man. It connects essentially nothing by month 12.
That is the point: the queue is slow and firm capacity is scarce.

**Q4. Isn't this just optimisation — where is the agent?** There is a real loop with an archive:
propose, verify against all 8,760 hours, keep the best. 200 parametric generations, then seven where
an LLM agent rewrote the policy code; one generation failed and is kept in the log. The policy also
repairs its own plan. The learning curve is in the dashboard.

**Q5. What does the agent learn?** That the trade is per site, not global: 99.99% where stress hours
are rare (premium ×1.25), 99% where the grid is congested, refuse where neither works. And it learns
that firm and batteries are dominated in this model.

**Q6. Could you compete with "just schedule work at midday"?** Scheduling assumes the connection
already exists. GRIDRUSH decides **whether the connection happens at all**, at what MW and under
which availability contract — and proves it over the full year plus a real power flow. That is the
difference between using the grid and getting onto it.

**Q7. What about the 4.30× if your prices are wrong?** The ratio is invariant to the margin level
(4.30× at ⅓×, 1× and 3× margin); flattening the SLA premium and doubling the penalty still gives
4.04×; the physical ratio 3.82× contains no prices. The absolute dollar level ($279.9M) is modelled.

**Q8. Why only 1.22× on real PG&E data?** Because at substation-aggregate level those substations are
large and not the bottleneck, so flexibility buys little. PG&E's own Grid Needs Assessment shows the
constraint at circuit level: 124 of 1,462 circuits with data (8.5%) are already deficient for 2026.
That is the data we ask for.

**Q9. Why no batteries?** In this model a battery costs $0.35M/MW + $0.25M/MWh and only buys
availability the flexible contract already provides. The exact per-site dynamic program makes
batteries redundant at these prices. That is a result, not an omission.

**Q10. Is "zero violations" meaningful?** For a flexible-only portfolio it is structural: flexible
load is clipped to headroom by construction. We say that explicitly. The binding constraint is each
site's SLA, which is enforced with zero breach energy; violations would matter for a firm-heavy
portfolio — a next step.

**Q11. Why 99% availability — isn't that bad?** It is a priced choice: 99% means 87.6 hours a year of
curtailment, and it pays ×0.80. The agent buys 99% only where the alternative is no connection. 16 of
32 sites are at 99.99%.

**Q12. How fast does it run?** ~3.7 ms per 40-site × 8,760-hour evaluation; the full loop in seconds;
the whole dashboard is a single offline HTML file; the live run streams to a browser in 11 seconds.

**Q13. What would you do with utility data?** Replace the synthetic site model with circuit-level ICA
and queue data, run AC power flow for every region, then aggregate many sites into a single grid
service. The loop and the evaluator do not change.

**Q14. Is this an aggregator / VPP?** Not yet — it plans connections. Aggregation of the resulting
fleet into one grid resource is Track 4 and an explicit next step.

**Q15. Why should the grid operator care?** Because it converts curtailed-hour capacity into
connection capacity: the agent finds the sites and contract terms that add MW **without** adding peak
load, and it quantifies what that is worth.

**Q16. What is the one-sentence pitch?** "You told us connecting takes seven to ten years and asked
what a 98% availability contract would change; we built the agent that answers it — 4.3× the value,
85 MW online by month 12, zero modelled violations — and when we put real AC power flow inside the
loop it honestly drops to 2.39×, which is exactly the data we are asking for."

---

## 16. The three-minute demo, in beats

| Time | Beat | What is on screen | What to say (essential) |
|---|---|---|---|
| 0:00 | Problem | dashboard open, nothing clicked | "Connecting a data centre takes seven to ten years. Someone in this room asked: what if it only needs 98% availability? The utility said: we're trying." |
| 0:20 | Approach | click: site map | "40 sites, 8 substations. Per site: skip, firm, flexible, or flexible plus battery. A verifier replays all 8,760 hours of 2025. Real demand data, synthetic geometry — and we say so." |
| 0:50 | Result | click: three strategies | "All firm: zero megawatts at month twelve, $65M. All non-firm: 173 MW, but minus $450M after 1.15M MWh of SLA breach. GRIDRUSH: 85.4 MW, plus $280M, zero violations, every site inside its SLA. It connects 32 sites and says no to eight." |
| 1:20 | Why | click: three-year plan | "Three years: four times more value." |
| 1:40 | Stress | click: worst day | "At six p.m. the naive plan must shed twenty-eight megawatts. GRIDRUSH never sheds more than one." |
| 2:00 | Learning | click: `Replay loop` | "Every dot is one plan: proposer writes it, the evaluator scores it, the archive keeps the best. The fast search plateaus at 179; then the LLM rewrites the policy and jumps to 280. 207 iterations — tonight's run, not a mock-up." |
| 2:30 | Expand | score curve stays | "Next: real feeders, real physics inside the loop (it costs 44% and we report it), real signals. One utility engineer and one circuit-level dataset is what we ask for." |

**60-second version:** Problem (7–10 years, 98% question, "we're trying") → what the agent decides
(40 sites, 8 substations, four choices, three availability tiers) → result (0 / 173 / 85.4 MW, 4.30×,
zero violations) → learning (207 iterations, 179 → 280) → ask (real circuit-level data).

---

## 17. Glossary for an audience outside power systems

- **Interconnection** — the process (and queue) for permission to connect a load or generator to the
  grid. For large loads it can take years.
- **Firm service** — capacity guaranteed at all times; the customer cannot be curtailed. Scarce and
  slow to obtain.
- **Non-firm / flexible / step-up service** — capacity that can be reduced in grid stress hours;
  faster and larger, but availability must be contractually bounded.
- **Headroom** — how much additional load a substation or feeder can carry in a given hour.
- **Curtailment** — reducing a site's consumption when the grid is stressed.
- **SLA / availability** — the promised fraction of hours the site can run; e.g. 99.9% allows 8.76
  hours a year of curtailment.
- **ICA / hosting capacity** — a utility's published estimate of how much generation or load a feeder
  can host. PG&E publishes 576 hourly values per line section.
- **AC power flow** — the physics calculation that determines voltages and line/transformer loading
  for a given set of loads.
- **N-1** — the grid's ability to survive the loss of one element; not simulated here (next step).
- **RSI (recursive self-improvement)** — an agent loop where the agent proposes changes, an evaluator
  scores them, and the best survive — including, here, the agent rewriting its own policy code.
- **LOLP / "nines"** — loss-of-load probability; "six nines" (99.9999%) is the reliability hyperscalers
  buy. Our premium tiers start at 99.99%.

---

## 18. Closing statement (for the presentation's final slide)

GRIDRUSH turns the interconnection queue from a wait into a decision. It does not claim the grid is
free — it shows, with a measured AC power flow, exactly how expensive the real physics is (a 44%
haircut), and it shows where the constraint really lives: not at the substation, but at the circuit.
The value of the project is that all of this is **computed, logged and reproducible**: every baseline,
every region, every iteration, and every honest caveat lives in the repository, and the number on
screen can be regenerated in seconds.
