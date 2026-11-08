# GRIDRUSH — simulator assumptions (`sim/assumptions.md`)

**One line of honesty:** *real 2025 EIA-930 hourly shape; synthetic site geometry and
interconnection timelines, parameters documented here.* No number in this file is presented as a
measurement; everything synthetic is marked `SYN`, and every parameter has a source or an explicit
"synthetic, order of magnitude".

Assumptions version: **1** (`meta.assumptions_version = 1`). File owner: sim-engineer.
The model was frozen on 2026-11-08; from here on `sim/engine.py` and `sim/baselines.py` change only with bugfixes.

---

## 1. Data (real)

| What | Value | Source |
|---|---|---|
| Hourly series | 2025, 8 760 hours × 12 BA, `data/us_grid_hourly_2025.csv` (13.8 MB) | EIA-930 Hourly Electric Grid Monitor, public domain (`catalog: eia-930`) |
| Demo regions | CAL = CAISO (BA `CISO`), TEX = ERCOT (`ERCO`), PJM = PJM (`PJM`), MISO = MISO (`MISO`) | `ba` column in the CSV + `data/us_grid_summary_2025.csv` |
| Peaks (actual) | CAISO **43 860 MW**, 2025-08-21 20:00 PDT; ERCOT 83 597 MW 2025-08-18 18:00; PJM 160 560 MW 2025-06-23 18:00; MISO 120 343 MW 2025-07-24 16:00 | EIA-930, cross-checked against `spike-data/report.md` §1 |
| Load shape `u[h]` | `u = demand_mw / p95(demand_mw)` | CONTRACT §2 (frozen) |
| `stress_day` | the region's peak-demand day: CAL 2025-08-21, TEX 2025-08-18, PJM 2025-06-23, MISO 2025-07-24 | EIA-930, `grid.stress_day` |
| Replay | representative year 2025 repeats in each of the 36 months of the horizon; month `m` uses the hours of the same year | CONTRACT §2 |

**Data cleaning (mandatory to cite, source — `energy-hack/spike-data/report.md`):**

| Problem in the CSV | What was done | Effect |
|---|---|---|
| **7 corrupted demand rows** (a one-hour dip to <5 % of normal; worst CISO 2025-07-31 14:00 = 11 819 MW between 29 881/29 886) | iteratively: if `\|Δprev\|>8000` and `\|Δnext\|>8000` and `\|prev−next\|<3000` MW/h → average of the neighbours (`sim/data.py::_load_region_cached`) | CAISO mean +2.1 MW (<0.01 %); **peaks and their timing untouched** — all corrupted rows are dips, not peaks |
| ERCOT: a full NaN day 2025-12-05 (24 h) + 1 hour each in DUK/PJM | linear interpolation in time, then edge-fill; NaN in the output arrays = 0 | NaN never reaches `u` |
| `solar_mw` column is non-physical (negative at night, jumps of ±12–16 GW/h at the day boundary) | `clip(≥0)`, **not used** for capacity/headroom/stress_hours; only for the stress-day chart | the headroom model is computed from the demand shape only |
| Day chosen for the solar chart | 2025-08-21 (CAISO, evening peak at 20:00, solar still 4.4 GW at that hour) | the solar column behaves decently on that day (per the spike report) |

Observed maxima of `u`: CAL 1.298, TEX 1.104, PJM 1.254, MISO 1.197 (u_min 0.35–0.53).
"Flex-worthy" hours (top-1 % demand or ramp) in the data — **174–176 per BA** (`flex_hours.csv`).

---

## 2. Grid and sites (synthetic, `SYN`)

| Parameter | Value | Where from / why |
|---|---|---|
| Grid | 8 substations × 5 candidate sites = **40 sites** | hackathon scenario; CONTRACT §1 |
| Site size `max_mw` | **0.5–10 MW**, step 0.5 | hackathon scenario (0.5–10 MW) |
| Substation capacity `cap_mw` | **8–60 MW**, uniform | `SYN`; order of magnitude — a 12–60 MVA distribution substation |
| Substation load `lf` | "raw" value **0.45–0.82**, mapped linearly into `[0.45, min(0.82, 0.98/u_max)]` | `SYN`; the upper bound exists so that existing load **does not by itself violate** the substation limit (check "empty portfolio → 0 violations", `sim/test_engine.py`). For CAL it is actually `[0.45, 0.755]`, TEX `[0.45, 0.82]` |
| Existing load | `e[S,h] = lf[S]·cap_mw[S]·u[h]` | CONTRACT §2; "many distribution areas are already fully loaded" (Arham, speech) |
| Operating margin | `margin = 0.02·cap_mw` | CONTRACT §2; a typical 2 % operating reserve |
| Site headroom | `H[i,h] = cap − e − margin` (the same for the 5 sites of a substation) | CONTRACT §2 |
| `Hmax_mw` / `Hmin_mw` | max/min over hours; `Hmax` — the best (night) window, `Hmin` — the "peak" firm budget | CONTRACT §2 |
| Coordinates `x,y` | `SYN`, region bbox: CAL (−124.4…−114.1, 32.5…42.0), TEX (−106.6…−93.5, 25.8…36.5), PJM (−84.8…−74.0, 37.0…42.3), MISO (−97.5…−84.0, 37.0…47.5) | similar to the region map, not real substations |
| `fiber` | Bernoulli(0.7) | `SYN`; fibre presence — a plausible share of sites |
| `permit_days` | 20–120 days | `SYN`; local permits |
| `stress_hours` (in the JSON) | **176 h/yr** = top-2 % of hours by `u` (the "flex-worthy" window) | `SYN` definition, calibrated to the real number of flex hours 174–176/BA (spike report §4). Computed from the demand shape, not from solar |

Parameters of the 8 substations (CAL): `cap` = [12.0, 48.6, 30.8, 45.6, 58.9, 36.0, 34.1, 11.7] MW,
`lf` = [0.566, 0.588, 0.520, 0.679, 0.563, 0.546, 0.650, 0.726],
`Hmin` (peak headroom) = [2.9, 10.5, 9.4, 4.5, 14.7, 9.8, 4.6, 0.4] MW (sum 56.8 MW),
`Hmax` (best hour) = [9.2, 36.9, 24.2, 33.1, 45.3, 27.9, 25.1, 8.3] MW.

---

## 3. Interconnection timelines (synthetic, `SYN`)

| Mode | Months to energize | Where from |
|---|---|---|
| `firm` | `T_firm ∈ [18, 36]` | MISO: "requests seek connection in 18 to 36 months" (`catalog: miso-large-load-integration`, ref P08); LBNL Queued Up: median request-to-operation > 5 years for generation (`catalog: lbnl-queued-up`) |
| `flex` (non-firm / step-up) | `T_flex ∈ [5, 10]` | MISO Firm Service Step Up (`catalog: miso-firm-service-step-up`, ref S47); ERCOT batch studies (`catalog: ercot-batch-zero`, ref S38) |
| `battery` (flex + onsite battery) | `T_on = T_flex + 1…3` months | Lead's correction: **a battery does not jump the queue**; the site still connects non-firm, the battery merely lowers net consumption in stress hours. `SYN`, but conservative |
| `T` in the metrics | `delivered = Σ mw·max(0, 36−T)·avail` | CONTRACT §2 |

---

## 4. Economics (synthetic, `SYN`)

| Parameter | Value | Where from / why |
|---|---|---|
| Compute margin | **$0.10M per MW·month** ($1.2M/MW·yr) | "$5M per MW over 3–4 years" (Arham, speech) → ≈$1.25–1.7M/MW·yr; we take the lower bound |
| Battery capex | **$0.35M/MW + $0.25M/MWh** | `SYN`, order of magnitude from the US market (a 4-hour system ≈ $1.35M/MW); CONTRACT §1 |
| Battery model | `B_mwh` — usable energy of one daily cycle, DoD 90 %, 1 cycle/day (365/yr); discharge "worst hours first" within the day; `P_bat ≥ mw` | reading of "per-year" in CONTRACT as an annual cycle budget; that is how a 4-hour battery physically works |
| SLA (price of the choice, Lead's correction from the stage) | `0.9999` → budget **0.876 h/yr**, revenue multiplier **1.25**; `0.999` → **8.76 h/yr**, **1.00**; `0.99` → **87.6 h/yr**, **0.80** | "you get a premium for six nines, but 99 % only works if you are ready to curtail"; budget = (1−SLA)·8760 |
| Availability | `avail = 1 − curtailed_hours/8760` | CONTRACT §2 |
| SLA breach | `breach = mw·max(0, curtailed_hours − budget_h)` MW·h; penalty `5 × margin_per_mwh × breach` | CONTRACT §1/§2: 5× the margin per MW·h over the budget; `margin_per_mwh = $0.10M/730` |
| Revenue | `delivered = Σ mw·months·avail` (without the multiplier); `net = 0.10·rev_weighted − capex − penalty` | Lead addendum: `rev_weighted = Σ mult(sla)·mw·months·avail` |
| Loop `score` | `net − 10·violations_mwh − 5·sla_penalty` | CONTRACT §2 |

---

## 5. Checks the model must pass

1. **Empty portfolio → 0 violations** (existing load does not by itself violate the substation limit).
2. **Firm above `Hmin` → `violations_mwh > 0`**: firm is not curtailed, the verifier independently recomputes
   `Σ(e + Σload − (cap − margin))` for every hour and every substation. The verifier does not trust the policy.
3. **Flex with oversubscription → 0 violations**, but `curtail_hours` grows and `avail` falls.
4. **The 99.9 % curtailment budget (8.76 h/yr) really does cap MW**: a site with `avail < sla` gets
   a penalty; the `max_mw_no_flex` baseline pays **1 150 268 MWh** over the budget and lands at **−$449.4M** net
   value (while its gross MW·months is the highest — 3384).
5. **Determinism**: seed=7 → the same sites and the same `evaluate()` (tests, `sim/test_engine.py`).

Test results: `python3 sim/test_engine.py` → **26/26 ok**, `evaluate()` ≈ **3.7 ms** for 40 sites ×
8760 h (budget 100 ms).

---

## 6. Calibration: the baselines are honest, not strawmen

CAL (demo region), 36 months, `results/sim_baseline.json`:

| Policy | MW | delivered MW·months | MW by month 12 | net $M | SLA breach MWh | violations |
|---|---|---|---|---|---|---|
| `all_firm_greedy` — everything firm, FCFS, wait for the queue | 56.0 | **385.5** | 0 | 38.6 | 0 | 0 |
| `queue_order` — firm, queue by `T_firm` | 55.9 | **651.3** | 0 | 65.1 | 0 | 0 |
| `max_mw_no_flex` — everything non-firm at max, no discipline | 172.6 | 3384.0 (gross) / **1447.9 compliant** | 172.6 | **−449.4** | 1 150 268 | 0 |
| GRIDRUSH agent (loop, 200 iterations, winning portfolio from `results/loop.json`) | 85.4 | **2490.6** | **85.4** | **279.9** | 0 | 0 |
| Reference policy from `sim/run.py` (gradient fallback when `loop.json` is absent) | 85.5 MW signed | **2414.4** | **85.5** | **250.0** | 0 | 0 |

Why this is fair:
* **Firm ≠ 0:** 385–651 MW·months, ~56 MW signed. Zero by month 12 is a direct consequence of `T_firm` 18–36;
  that is exactly the status quo we beat, not a fiction.
* **Firm is impossible with zero headroom:** at substation S08 peak headroom is 0.4 MW, so the firm budget
  is ~0 — as it should be ("distribution areas are already fully loaded").
* **`max_mw_no_flex` is not a strawman:** it wins on gross MW·months (3384) and MW by month 12
  (172.6), but pays SLA penalties down to −$449M net; exactly what the "speed without reliability" story is about.
* **Ratio** in the JSON: **3.82×** by compliant MW·months and **4.30×** by net value against `queue_order`;
  `max_mw_no_flex` is the counterexample on net value (largest gross, but negative value).
* **Reproducibility:** `python3 sim/run.py` from a clean cache twice yields an identical JSON (except
  `generated_at`/`wall_s`); `best` mirrors `results/loop.json`, recomputed by the same `evaluate()`.
* `best` in the JSON is a **stub** per CONTRACT §5: if `loop.json` is absent, `run.py` substitutes a deterministic
  reference policy (3.71× / 3.84×) so that the format and the dashboard do not break.

Regions (delivered MW·months / net $M, `regional_benchmarks`):

| | all_firm | queue_order | max_mw_no_flex |
|---|---|---|---|
| CAL (CAISO) | 385.5 / 38.6 | 651.3 / 65.1 | 3384.0 / −449.4 |
| TEX (ERCOT) | 540.4 / 54.0 | 892.4 / 89.2 | 3304.0 / −497.7 |
| PJM | 401.9 / 40.2 | 676.1 / 67.6 | 3333.4 / −479.8 |
| MISO | 421.9 / 42.2 | 717.0 / 71.7 | 3230.6 / −541.6 |

CAL was chosen as the main one: the sharpest evening peak (43 860 MW at 20:00 on 21.08.2025), the highest `u_max`
(1.298), the strongest solar curve and the widest "firm vs flex" gap — the most readable story.
TEX gives a bigger absolute (ERCOT is larger), but a less dramatic ratio.

---

## 7. Deviations from CONTRACT.md (all additions, nothing broken)

1. **`lf` effective ceiling** `min(0.82, (1−margin)/u_max)`, so that the empty portfolio does not violate the limit.
   In CAL that is 0.755, in TEX 0.82. The formula for `e` is unchanged.
2. **SLA — 3 tiers with revenue multipliers** (1.25/1.00/0.80) instead of 2 tiers — Lead's correction from the stage;
   `delivered_mwmonths` stays without a multiplier, `rev_weighted_mwmonths` was added.
3. **`T_on = T_flex + 1…3`** (the battery does not jump the queue) — Lead's correction.
4. **Battery: a daily cycle** (DoD 90 %, 365/yr) — reading of "per-year" in CONTRACT; otherwise the battery
   is energetically meaningless.
5. **`stress_hours`** = the flex-worthy window (top-2 % of `u`), not "hours with H < max_mw" (the latter gave
   3000+ h on loaded substations — an artifact).
6. **`ratio_mw12 = null`**: `queue_order`/`all_firm` give 0 MW by month 12 (queue 18–36 months), so the
   ratio is unbounded (∞); the JSON carries `ratio_mw12_note`. `comparison.ratio_mwmonths` and `ratio_net_value`
   are computed against `queue_order`.
7. **Additional JSON keys** (the dashboard may ignore them): `regional_benchmarks`, `baselines[*].compliant_*`,
   `rev_weighted_mwmonths`, `best.source`, `grid.stress_day.headroom_mw/curtail_mw/u`, `sites[*].lf/T_on/fiber/permit_days/Hmin_mw`.
8. **`best`/`iterations` — a stub per the §5 schema**; if `results/loop.json` exists, `best` is assembled from
   the loop's winning portfolio and **recomputed by the same `evaluate()`** (one source of truth). `iterations`
   stays an empty array — the learning curve is owned by `loop/run.py`.
9. **`regions[].code` = CAL/TEX/PJM/MISO (CONTRACT §5), plus `eia_code` = CAL/TEX/MIDA/MIDW and `aliases`;
   `site_curves()`/`evaluate()` accept any of them** (`CISO`, `ERCO`, `MIDA`, `MIDW` — aliases). This is one
   and the same region; there is no second source of truth.
10. **`grid.stress_day.date` — the local date of the peak** (CAL: `2025-08-21`, evening peak 20:00 PDT 43 860 MW).
    In CONTRACT §5 the example shows `2025-08-22` — that is the UTC date (`2025-08-22T03:00Z`); we use the BA
    local calendar (like `local_time_end` in EIA-930), otherwise the evening peak "slides" to the next day.
11. **The verifier counts grid consumption (`load`), and the battery discharge behind the site**: the battery lowers
    curtailment/raises `avail`, but does not create substation load. Plus a 1e-6 MW tolerance for float noise.
12. **`evaluate()` returns additional fields** (`curtail_mwh_by_site`, `energize_month_by_site`, `sla_by_site`,
    `mw_by_site`, `battery_mwh_by_site`, `sla_penalty_musd`, `rev_weighted_mwmonths`) — additions only.

---

## 8. The most contentious assumptions (ready answers for Q&A)

1. **`T_firm` 18–36 months.** MISO: "requests seek connection in 18 to 36 months" (P08,
   `catalog: miso-large-load-integration`); LBNL Queued Up — median > 5 years for generation, 1.5–3 years for large
   loads. We took MISO's lower bound — that is **conservative in favour of firm**, i.e. the baseline
   is not artificially understated.
2. **Battery $0.35M/MW + $0.25M/MWh.** Order of magnitude: a 4-hour BESS ≈ $1.0–1.5M/MW in the US 2025–2026
   (NREL ATB, LBNL). In the model the battery capex **does not pay back** if the MW already fits in the peak headroom —
   which is why `best` buys almost no battery. This is an honest conclusion, not curve-fitting (see §7.4).
3. **`lf` up to 0.95?** No: in CONTRACT the table says `lf ∈ [0.6, 1.0]`, but at `u_peak ≈ 1.30` that would put
   existing load above `cap` at peak (physically impossible, and it breaks the invariant "empty portfolio →
   0 violations"). Hence the ceiling `(1−margin)/u_max`; the actual `lf` range is 0.45–0.82. The meaning is preserved:
   at S08 peak headroom is 0.4 MW out of 11.7 MW — the substation is "fully loaded".
4. **SLA multipliers 1.25/1.00/0.80.** From the stage: "you get a premium for six nines; 99 % only if you are ready
   to curtail". The absolute values are `SYN`; the sign and the order are chosen so that the SLA choice is a real
   economic decision rather than a dominated option; this is checked by the agent choosing 0.9999 only
   at sites where it holds availability (0 MWh breach).
5. **`u = demand/p95`.** CONTRACT §2; p95 is the "typical evening peak", peak/p95 = 1.30 (CAL) — the real
   CAISO peakiness ratio.
6. **36-month horizon + 2025 replay.** CONTRACT §2; one representative year, not a forecast.
7. **Economics $0.10M/MW·month.** From "$5M per MW over 3–4 years" (speech) → $1.25–1.7M/MW·yr; we take $1.2M,
   i.e. slightly conservative — the ratio is not inflated.
