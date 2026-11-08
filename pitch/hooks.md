# GRIDRUSH — hooks: killer one-liners

> Every number has a source. `catalog id` = a resource in the hackathon repo
> (`python3 scripts/find.py <id>`); "speech" = a verbatim quote from the stage (locator = character
> position in the transcript `~/Downloads/Untitled 19.md` — the file has no timecodes); "our spike" =
> computed from `gridrush/data/us_grid_hourly_2025.csv` (real EIA-930, 12 operators);
> "loop.json" = `gridrush/results/loop.json`.
>
> Rule: **one number per slide, one number per paragraph.** On stage — at most three hooks from
> the list. If you say two numbers in a row, the second one is lost.

---

## Top 10

| # | One-liner (English — say it as is) | Number | Source |
|---|---|---|---|
| 1 | "Connecting a data center to the grid today takes seven to ten years." | 7–10 years | **speech**, PG&E (David, partnerships team), characters 27 187 (≈47.7% of the recording) |
| 2 | "Three strategies, same forty sites: wait for firm power — zero megawatts at month twelve. Sign everything non-firm — one hundred seventy-three megawatts, and minus four hundred fifty million dollars. GRIDRUSH — eighty-five megawatts, plus two hundred eighty million." | 0 / 173 / 85 MW | **loop.json** (final). This is your main slide: three columns, two numbers on each |
| 3 | "The engineer from PG&E said a load that curtails a few hot days a year could connect much faster. Someone in the room asked: so guaranteed capacity only 98% of the time? The utility answer: we're trying." | 98% | **speech**, characters 27 605–28 585 (≈48.5–50.2%) |
| 4 | "We ask compute to be flexible for about two percent of the hours in the year. In exchange, it gets months of running time." | 2.0% of the hours in the year (160–177 h per operator, all 12) | **our spike**: top-1% of demand OR top-1% of ramp, 12 operators. Recomputed by me at 04:28: BPAT 160, the rest 175–177; the ±2 h spread depends on the quantile method. Slide caption: "flex-worthy hours, 2025 EIA-930" |
| 5 | "ERCOT has about 410 gigawatts of large-load requests on file — about 87% data centers — against 7.5 gigawatts actually approved to energize since 2022." | 410 GW vs 7.5 GW | `ercot-legislative-update-2026` (410 GW, ~87%, as of 26.03.2026) + `ercot-constraints-2025` (7 502 MW since Jan. 2022) |
| 6 | "CAISO's peak in 2025 was 43,860 megawatts — and it arrived at eight in the evening, not at noon." | 43 860 MW, 2025-08-21 20:00 | **our spike** (real EIA-930). The peak is in the evening, so flexibility is valuable precisely in the evening |
| 7 | "On 8 March 2025, CAISO's net load fell to minus 1,140 megawatts at one in the afternoon, then climbed 22,682 megawatts in six hours." | −1 140 → +22 682 MW | **our spike**: net load = demand − solar, 08.03.2025 13:00 → 19:00 |
| 8 | "Five million dollars. That is what one megawatt of available capacity is worth, for three to four years." | $5M / MW / 3–4 years | **speech**, Arham, characters 20 085 (≈35.3%). Our $1.2M/MW-year is the same number divided by the term |
| 9 | "Nearly 100 gigawatts of new load could run on capacity that already exists — if it accepts limited curtailment during grid stress." | ~100 GW | `duke-rethinking-load-growth-2025` (Duke Nicholas Institute, 2025, 22 largest BAs) |
| 10 | "On 22 July 2026, nearly 4,000 megawatts of data center load in Virginia disconnected unexpectedly. Earlier events were about 1,500." | 4 000 MW | `pjm-load-transfer-event-2026` (PJM / Dominion review, Aug. 2026) |

---

## The same loop, four regions (defuses "you tuned it for California")

All four were re-measured with the final `gen_6` policy — that is the proof of "no tuning".

| Region | ratio net | ratio MW·month | net, $M | MW @12 | violations |
|---|---|---|---|---|---|
| CAL — CAISO | **4.30×** | 3.82× | 279.91 | 85.4 | 0 |
| TEX — ERCOT | **3.41×** | 2.79× | 304.46 | 84.1 | 0 |
| MIDA — PJM | **4.07×** | 3.57× | 275.30 | 82.4 | 0 |
| MIDW — MISO | **3.88×** | 3.33× | 277.84 | 81.3 | 0 |

**One-liner:** "The same policy, four operators, **three point four to four point three times**
the value, and zero violations — no per-region tuning."

> The particular strength of this table: MW@12 is 81–85 everywhere, violations 0 everywhere. One
> policy, four different markets. This is the best answer to "you tuned it for one region".

---

## In reserve (for Q&A and the "problem" slide)

| # | One-liner | Number | Source |
|---|---|---|---|
| 11 | "In MISO, large loads ask for a connection in 18 to 36 months; the fast track exists — non-firm service and firm-service step-up." | 18–36 months | `miso-large-load-integration`, `miso-firm-service-step-up` |
| 12 | "Half a megawatt to ten megawatts sits below the large-load rules — ERCOT's threshold is 25 megawatts." | 0.5–10 MW < 25 MW | `ercot-nprr1234`, `pge-ica` |
| 13 | "PG&E publishes 576 hourly capacity values per line section — and calls them 'directional, not a guarantee'." | 576 values | `pge-grip-guide` |
| 14 | "A field demo in Phoenix cut an AI cluster's power by 25% for three hours, software only." | −25% / 3 h | `emerald-phoenix-2025` (preprint, arXiv 2507.00909) |
| 15 | "Twelve US grid operators moved 3,513 terawatt-hours in 2025 — that is the dataset we load in one line." | 3 513 TWh | **our spike** (sum of `demand_mw` over 12 BAs, 2025) |
| 16 | "The median interconnection request waits over five years; only 13% of requests from 2000 to 2020 ever reached operation." | >5 years / 13% | `lbnl-queued-up` (2026 edition) |
| 17 | "A 320-megawatt promise for 2028 became closer to 150. The power you were promised is not the power you get." | 320 → 150 MW | **speech**, Sean (AGI House), characters 45 391 (≈79.7%) |

---

## How to deliver it (more important than the numbers themselves)

| # | What to do | Why |
|---|---|---|
| 1 | Say the number **before** the explanation, pause 1 second, then the meaning | the room remembers the last 4 words, not the middle |
| 2 | On the slide — only the number and 3–4 words. Out loud — the whole sentence | people read the slide and listen to the speech |
| 3 | Hook #2 (three strategies) is the only one that must be a **picture**: three columns, each with MW and $ | this is the whole pitch in one frame |
| 4 | Hook #3 ("we're trying") — do not smile | it is the setup, not a joke |
| 5 | Hook #4 ("2% of hours") is the strongest new argument. Speak slowly — it is your deal price | it removes the "why do we need flexibility" objection |
| 6 | Hook #6 — do not claim that "the peak is always in the evening": for 5 of 12 operators the top ramp is not at 17–20 | one wrong detail kills trust in every number |
| 7 | Do not take more than three hooks for 3 minutes | the demo already has 12 numbers; 13 numbers = 0 numbers |
| 8 | Do not add a new hook at the end of the demo | the last line is the "ask", not "more statistics" |

**Recommended set:** #1 (0:00) → #3 (0:00–0:20) → #2 (0:50–1:45) → #4 (1:40). The rest —
for Q&A. Keep hook #15 for the answer to "how big is your dataset".

---

## Careful with wording (checked against the data — do not repeat the mistakes)

1. **The solar column in the CSV is non-physical** (artifacts of ±12–16 GW/h). Do not build
   arguments on it and do not say "solar was 4,389 MW at eight PM" — it sounds nice and can be
   refuted by one question from PG&E. Talk about the evening peak only through **demand**
   (43 860 MW at 20:00 — a fact) and through **evening ramps**.
2. **"The top ramp is always in the evening"** is true for CAISO, ERCOT, PJM, MISO, but not for 5 of 12
   operators. Say "in the four largest US grids" or "in our four regions".
3. **$202M is not revenue and not money earned.** Only: "modelled compute margin over 36
   months on this synthetic portfolio".
4. **Do not call synthetic data real data.** The only permitted formula: "real 2025
   EIA-930 demand shape; synthetic site geometry and interconnection timelines, documented".
5. `GridCare raised $60,000,000` — heard second-hand, the company is not verified. Do not say the name until
   you confirm it; the number can be dropped entirely.

---

## Appendix — verbatim stage fragment (the main one, for the slide and for Q&A)

Keep this block as it is: it must not be paraphrased in your own words.

> **PG&E (David):** "if you can reduce your availability, here's part of the tension, right? Down
> to like 98% or something like that, there's probably just 2 weeks out of the year, maybe, or
> even a few days out of the year, where our load is really, really high when it gets really hot,
> right? Like, if you're willing to, or if the data center is willing to curtail their load, uh,
> you know, for a few days out of the year, that could drastically improve the chances and the
> speed of which they could connect for a couple of reasons. Like, number one, the number of sites
> that become available increases, and then the alternative gets a lot easier."
>
> **Arham:** "Typically, when people are building a data center, they reserve a certain amount of
> capacity from the grid. So way you're describing wouldn't work."
>
> **PG&E:** "But what if it was guaranteed capacity for 98% of the time?"
>
> **Host:** "But is that how power companies work?"
>
> **PG&E:** "**We're trying.**"

The arithmetic worth knowing: 98% availability = 175 hours a year ≈ 7.3 days. "Two weeks a
year" = 336 hours ≈ 96.2%. So 98% is a **tighter** promise than the engineer's example.
Say: "his 98 percent is the tighter promise — we took that one".

---

## What else was said on stage (quotable, not for the slide)

| Idea | Verbatim | Why we need it |
|---|---|---|
| The distribution grid is already fully loaded | "We have many areas where the distribution is actually already being fully consumed" (Arham, 15 545, ≈27%) | explains the "skipped" sites |
| The utility has already handed out the capacity | "we, at the utility, have already built out a bunch of physical infrastructure, and a lot of the demand, or the load, has already been taken up" (PG&E, 26 410, ≈46%) | same |
| Years in the queue, days for warehouses | "some sites have been in the interconnection queue for a year, versus some have been approved in days" (Arham, 18 312, ≈32%) | why 0.5–10 MW |
| Already doing it on the distribution side for Tesla | "we actually do this on the distribution side … for Tesla, like for superchargers … small footprints" (PG&E, 28 876, ≈51%) | removes "that never happens" |
| Predictable downtime vs random | "if they know that I might lose energy for like 10 minutes a day … just have a massive battery that's ready for it. But if you have 10 minutes per day versus 2 hours, on a random day, then the batch is not ready for it" (Arham, 24 213, ≈42.5%) | the case for the SLA budget |
| Judges' criteria | "the technical aspect, a … loop … energy system, innovation simulation … a technical demo … and the learning capabilities of your agents as well" (organizer, 56 413, ≈99%) | exactly what we are showing |
| Prize | "a single price, a $300 Amazon gift card" (organizer, 55 201, ≈97%) | context |
