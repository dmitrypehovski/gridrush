# GRIDRUSH — demo script, 3:00, verbatim

**FROZEN.** Numbers from `results/FINAL_NUMBERS.md`, `results/loop.json` and `results/powerflow.json`
(CAL / CAISO, 2026-11-08). No placeholders left.

Solo speaker. **418 spoken words**, measured per beat below: 2:52 at 145 words per minute, 2:41 at
155 — with pauses and clicks you land at about 2:56. Do not add words.

Only this file is read on stage. Everything else is preparation.

---

## 0. Before you walk up (5 minutes earlier)

| # | Check | Why |
|---|---|---|
| 1 | `web/dashboard.html` open in **one** tab, already loaded from `results/loop.json` | no file dialogs on stage |
| 2 | Full screen, browser zoom **125%** | judges read the big numbers |
| 3 | The **`Replay loop`** button visible without scrolling; then scroll back up | you must not hunt for it at 2:00 |
| 4 | The **three-strategy card** is on the first screen (firm / non-firm / GRIDRUSH) | it carries the whole pitch |
| 5 | Cursor parked bottom-left; Do Not Disturb on; Wi-Fi off (dashboard is offline) | no pop-ups |
| 6 | Backup: pre-recorded screen capture of the whole 3 minutes on the desktop | if the browser dies |
| 7 | Confirm with **dashboard-builder**: button label is exactly `Replay loop`, map colours green = firm / amber = flexible / grey = skipped | if they differ, change two words here |
| 8 | Water on the table, phone in pocket | 3 minutes is dry |

> If the projector is low-resolution, drop the map sentence and keep the three-strategy card and the
> Replay loop. Those two carry the pitch.

---

## 1. What is on screen, and when

| # | Panel | You show it for |
|---|---|---|
| 1 | **Map** — 8 substations, 40 sites, colour by mode | "what it chose, not me" |
| 2 | **Three-strategy card** — firm / non-firm / GRIDRUSH: MW at month 12 and net value | the core of the demo |
| 3 | **Three-year plan** — stacked bar of running MW, months 1→36 | four times the value |
| 4 | **Worst day** — 2025-08-21, existing load vs our compute vs curtailment | "no red" |
| 5 | **Score curve + `Replay loop`** — 207 iterations, animated on click | the learning beat |

---

## 2. The script

### ⏱ 0:00 – 0:20 · PROBLEM · 39 words

**SCREEN:** nothing yet. Dashboard open, nothing clicked. Look at the room, not the screen.

> Today on this stage, a PG&E engineer said: connecting a data centre takes seven to ten years.
> Then someone asked: what if a load needs guaranteed capacity only ninety-eight percent of the
> time? The utility answer was: we're trying.

**CUES:** "seven to ten years" slowly — it is the anchor. Pause one beat after "we're trying."
Do not smile there: it is the opening, not a joke.

---

### ⏱ 0:20 – 0:50 · APPROACH · 52 words (21 s — 4 s slack)

**SCREEN:** click once — the **map** appears. Point at the legend, not at the dots.

> We answer it with a number. GRIDRUSH plans speed to power. Forty sites, eight substations.
> Per site it chooses: skip, firm, flexible, or flexible plus battery. A verifier replays all eight
> thousand seven hundred sixty hours of twenty twenty-five for violations and SLA. Real demand data,
> synthetic geometry — and we say so.

**CUES:** "and we say so" is the honesty line: look at the judges. If you stumble, drop "per site" —
the sentence still works.

---

### ⏱ 0:50 – 2:00 · LIVE RESULT · three strategies · 168 words (69 s — fits its slot exactly)

**SCREEN:** click — **three-strategy card**. Read it top to bottom, one strategy per sentence.

> Same forty sites, three strategies.
>
> One: sign everything firm and wait for the queue. Sixty-five million dollars of compute margin
> over three years — and zero megawatts at month twelve. Safe, and useless.
>
> Two: sign everything non-firm, at maximum. Fast — one hundred seventy-three megawatts by month
> twelve. But eighty-seven hours a year of curtailment breaks the contract; penalties make it minus
> four hundred fifty million. Faster, and worse.
>
> Three: GRIDRUSH. Eighty-five megawatts by month twelve, two hundred eighty million of compute
> margin, zero network violations, every site inside its SLA. It connects thirty-two sites — and
> says no to eight.

**SCREEN:** stay on the card. Do **not** click. Point at the "32 of 40" number.

> Ninety-nine point nine nine percent where the grid is calm, ninety-nine percent where the
> alternative is no connection at all. It asks compute for about two percent of the hours — and gets
> months of running time.

**SCREEN:** click — **three-year plan**, then **worst-day chart**.

> Three years: four times more value. Worst day: no red. At six p.m. the naive plan must shed
> twenty-eight megawatts. GRIDRUSH never sheds more than one.

**CUES:** the three strategies are the demo — if you lose 20 seconds anywhere, cut the map sentence,
never this. Say "safe, and useless" flat, without a smile; the contrast is the argument. "six p.m. … twenty-eight megawatts … one" is the sentence judges remember: say both numbers slowly.

---

### ⏱ 2:00 – 2:30 · IMPROVEMENT · the Replay loop · 66 words (27 s, overlaps the animation)

**SCREEN:** scroll to the **score curve**. `Replay loop` is on it.

> The part the organisers asked for. I press Replay loop.

**SCREEN:** **click `Replay loop`.** The curve animates through all 207 iterations, counters tick,
the archive of kept plans fills in. Let it move while you talk.

> Every dot is one plan: proposer writes it, evaluator scores it, repair fixes it, archive keeps
> the best. Look at the jump: the fast search plateaus at one hundred seventy-nine; then the LLM
> rewrites the policy — exact per-substation DP — and jumps to two hundred eighty. Two hundred
> seven iterations. Tonight's run, not a mock-up.

**CUES:** the click is the most important physical action of the demo — click first, then speak.
Point at the plateau, then at the jump: that step is the RSI story. If nothing happens, say "and
here is the recorded run" and switch to the backup video. Do not debug on stage.

---

### ⏱ 2:30 – 2:55 · HOW IT EXPANDS · 70 words (29 s)

**SCREEN:** leave the score curve up. It is your evidence while you talk about the future.

> Next steps. One: real feeders — PG&E GRIP line sections, five hundred seventy-six values each.
> Two: real physics. We ran AC power flow on a twenty-kilovolt feeder: six and a half megawatts
> spare, our five biggest sites need thirty-two. Then that physics goes inside the loop — two point four times
> instead of four point three. That gap is the value of real utility data, exactly what we ask for.

**CUES:** count on your fingers: one, two. Slow down on "two point four instead of four point
three" — that is the honest cost of real physics, and the strongest thing you say in the last
minute. Do not apologise for it; sell it.

---

### ⏱ 2:55 – 3:00 · ASK · 22 words (9 s)

**SCREEN:** nothing changes.

> Ask: one utility engineer with a feeder we can model, and one flex contract to test. Thank you —
> repo is attached.

**CUES:** stop at 3:00 even mid-sentence. The clock is the enemy, not the content.

---

## 3. Pronunciation (practise these, nothing else is hard)

| Word | Say it as | Not as |
|---|---|---|
| curtailment | cur-**TAIL**-ment | "curtle-ment" |
| substation | **SUB**-stay-shun | "sub-stayshun" |
| megawatt | **MEG**-a-watt | "meega-watt" |
| proposer / evaluator | pro-**POH**-zer / ee-**VAL**-you-ay-tor | "pro-poser" flat |
| per-substation DP | "per-**SUB**-stay-shun dee-pee" | spell it letter by letter |
| twenty-eight / thirty-two | "twenty-eight" / "thirty-two" — both numbers by hand | do not rush them |
| PG&E | P-G-and-E | "peegee" |

Pace rule: **145 words per minute feels slow and sounds confident.** If you finish early, lengthen
the pause after "we're trying" — it is better than adding words.

---

## 4. If something breaks

| Failure | Say this | Do this |
|---|---|---|
| Dashboard will not open | "Let me show you the recorded run." | play the backup video, keep the same timing |
| Replay loop does nothing | "The animation is on the recording — here." | switch to the backup video at the curve |
| You lose your place | "Three strategies." | say 0 MW / −450 million / +280 million, then continue at How it expands |
| A judge interrupts | answer in one sentence, then: "I will show that number — one minute." | never argue mid-demo; the Q&A is where you win |

---

## 5. Four things you must not say (from `results/FINAL_NUMBERS.md`)

1. Never "real data" about sites, substations or timelines. Say: **"real 2025 EIA-930 demand shape;
   synthetic site geometry and interconnection timelines, documented."**
2. Never "zero violations" without **"in the model"** — we model headroom, not full power flow
   (full answer: `qa-defense.md`, Q6).
3. Never "we made $280M", "revenue" or "profit". It is **modelled compute margin over 36 months on
   this synthetic portfolio**.
4. Never quote a solar number — the column is non-physical and is not used in any capacity or
   stress calculation.

---

## Appendix A — the frozen numbers (no placeholders left)

Source: `results/FINAL_NUMBERS.md`, `results/loop.json`, `results/powerflow.json`.

| Thing said on stage | Value | Where |
|---|---|---|
| MW at month 12, all-firm | **0** | `comparison.baseline_mw12` |
| Margin, all-firm, 36 months | **$65.1M** | `comparison.baseline_net_value_musd` |
| MW at month 12, all non-firm | **172.6** | `comparison.naive_mw12` |
| Net value, all non-firm | **−$449.5M** | `comparison.naive_net_value_musd` (1.15M MWh SLA breach) |
| MW at month 12, GRIDRUSH | **85.4** | `best.mw_at_month12` |
| Margin, GRIDRUSH | **+$279.9M** | `best.net_value_musd` |
| MW-months, compliant | **651.3 → 2490.6 (3.82×)** | `comparison.ratio_compliant_mwmonths` |
| Net value ratio | **4.30×** | `comparison.ratio_net_value` |
| Sites connected | **32 of 40** | `comparison.sites_energized` |
| Violations / SLA breach | **0.000 / 0.000 MWh** | `best.violations_mwh`, `best.sla_breach_mwh` |
| Iterations | **207** (200 mutator + 7 LLM) | `len(iterations)` |
| Learning curve | **108.4 → 279.9**; plateau 178.6; LLM jump 178.6 → 269.6 → 279.9 | `iterations[].score` |
| SLA mix | **16× 99.99%, 6× 99.9%, 10× 99%** | `best.sites[].sla` |
| Curtailment at 18:00 | naive **28.4 MW**, agent **1.0 MW** | `grid.stress_day.curtail_mw_naive` / `curtail_mw` |
| Curtailment at 20:00 (peak 43,860 MW) | naive **18.2 MW**, agent **0.0 MW** | same |
| AC power flow (validation) | base min V **0.9756 p.u.**; feeder fits **8.2 MW** of our load class (min V **0.9635 p.u.**, 0 violations); five biggest sites **31.8 MW** → **71 violations** | `results/powerflow.json` |
| AC admission limit | **6.53 MW** per 20 kV feeder — first violation at **7.03 MW** (min V 0.95785 p.u. at 100% loading) | `results/physics_gate.json`, `sim/physics_gate.py` |
| **Physics in the loop** | **2.39×, $155.5M, 1313 MW·months, 44.7 MW@12, 29 sites, 8/8 substations AC-PF clean** | `results/loop_physics.json`, `loop/run_physics.py` |
| Cost of real physics | **−44.5% net value** versus the profile model (6.5 MW per real feeder, not the 20–60 MW synthetic ceilings allowed) | `results/FINAL_NUMBERS.md` |
| Stress day | **2025-08-21** | `grid.stress_day` |
| Repository | **attached as `gridrush.zip`** (offline; no keys; every baseline, every region, every iteration in `results/loop.json`) | — |

> One sentence on stage already carries the AC result ("six and a half megawatts spare, five biggest
> sites need thirty-two"). Everything else above is Q&A ammunition only — do not recite the table.

---

## Appendix B — the on-stage quotes used here (verbatim from the transcript)

| Used at | Speaker | Verbatim |
|---|---|---|
| 0:00 | PG&E (David, partnerships team) | "speed to power is basically, right now, if you're a data center or if you want to connect a data center to the grid, it'll take you 7 to 10 years to do that." |
| 0:00 | same | "if you can reduce your availability … down to like 98% or something like that, there's probably just 2 weeks out of the year, maybe, or even a few days out of the year, where our load is really, really high when it gets really hot … if the data center is willing to curtail their load … for a few days out of the year, that could drastically improve the chances and the speed of which they could connect." |
| 0:00 | the 98% line is PG&E; **who asked the follow-up is unclear in the recording** — do not attribute it | "But what if it was guaranteed capacity for 98% of the time?" → host: "But is that how power companies work?" → PG&E: "**We're trying.**" |
| Q&A only | same | "we actually do this on the distribution side … for Tesla, like for superchargers and those kinds of sites, like small footprints." |
| Q&A only | Arham (Stanford Energy Club) | "if there is more energy that's available, each megawatt would be would $5000000 uh for 3 to 4 years." |

Transcript has no timestamps. Locator: characters 27,187–28,585 of the file (≈48–50% of the
recording, the middle of the morning session).

---

## Appendix C — one-page cue card

Print `pitch/cue-card.md`. It is the only thing you hold on stage.
