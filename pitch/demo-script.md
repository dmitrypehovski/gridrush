# GRIDRUSH — demo script, 3:00, verbatim

Solo speaker. **407 spoken words**, measured per beat below: that is 2:48 at 145 words per minute
and 2:37 at 155, so with natural pauses you land at about 2:55 — five seconds of slack before the
hard stop. Do not add words. Filled with final numbers from `results/loop.json` (Lead, engine
frozen); placeholders left: **`{{ITERATIONS}}`** and **`{{REPO_URL}}`** (Appendix A).

Only this file is read on stage. Everything else is preparation.

**Speaking level:** short sentences, present tense, no acronyms spoken aloud except "SLA" and
"PG&E". Numbers are written as you say them, so you never translate digits live.

---

## 0. Before you walk up (5 minutes earlier)

| # | Check | Why |
|---|---|---|
| 1 | `web/dashboard.html` open in **one** tab, already loaded from `results/loop.json` | no file dialogs on stage |
| 2 | Full screen, browser zoom **125%** | judges read the big numbers |
| 3 | The **`Replay loop`** button visible without scrolling; then scroll back up | you must not hunt for it at 2:00 |
| 4 | The **three-strategy card** is on the first screen (firm / non-firm / GRIDRUSH) | it carries the whole pitch now |
| 5 | Cursor parked bottom-left; Do Not Disturb on; Wi-Fi off (dashboard is offline) | no pop-ups |
| 6 | Backup: pre-recorded screen capture of the whole 3 minutes on the desktop | if the browser dies |
| 7 | Confirm with **dashboard-builder** before 17:00: button label is exactly `Replay loop`, and the map colours are green = firm, amber = flexible, grey = skipped | if they differ, change two words here, not the dashboard |
| 8 | Water on the table, phone in pocket | 3 minutes is dry |

> If the projector is low-resolution, drop the map beat (one sentence) and keep the
> three-strategy card and the Replay loop. Those two carry the pitch.

---

## 1. What is on screen, and when

| # | Panel | You show it for |
|---|---|---|
| 1 | **Map** — 8 substations, 40 sites, colour by mode | "what it chose, not me" |
| 2 | **Three-strategy card** — firm / non-firm / GRIDRUSH: MW at month 12 and net value | the core of the demo |
| 3 | **Three-year plan** — stacked bar of running MW, months 1→36 | the ratio |
| 4 | **Worst day** — 2025-08-22, existing load vs our compute vs violation | "there is no red" |
| 5 | **Score curve + `Replay loop`** — iterations, animated on click | the learning beat |

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

### ⏱ 0:20 – 0:50 · APPROACH · 61 words (25 s)

**SCREEN:** click once — the **map** appears. Point at the legend, not at the dots.

> So we answer it with a number. GRIDRUSH is an agent that plans speed to power. Forty sites,
> eight substations. It chooses per site: skip, firm, flexible, or flexible plus a battery.
> A verifier replays all eight thousand seven hundred sixty hours of 2025 and checks violations
> and SLA. Real 2025 demand data. Synthetic site geometry — and we say so.

**CUES:** "and we say so" is the honesty line: look at the judges. If you stumble, drop the words
"per site" — the sentence still works.

---

### ⏱ 0:50 – 2:00 · LIVE RESULT · three strategies · 180 words (74 s — overruns its slot by 4 s,
recovered in the expand beat; if you must cut, cut the map sentence)

**SCREEN:** click — **three-strategy card**. Read it top to bottom, one strategy per sentence.

> Offline on my laptop. Same forty sites, three strategies.
>
> One: sign everything firm and wait for the queue. That is what everybody does today.
> Sixty-five million dollars of compute margin over three years — and zero megawatts at month
> twelve. Safe, and useless.
>
> Two: sign everything non-firm, at maximum. Fast — one hundred seventy-three megawatts by month
> twelve. But eighty-seven hours of curtailment a year breaks the contract; the penalties make it
> minus two hundred five million. Faster, and worse.
>
> Three: GRIDRUSH. Seventy megawatts by month twelve, two hundred two million of compute margin,
> zero network violations, every site inside its SLA. It connects nineteen sites — and says no to
> twenty-one.

**SCREEN:** stay on the card. Do **not** click. Point at the "19 of 40" number.

> It is not one decision, it is a decision per site: ninety-nine point nine nine percent where the
> grid is calm, ninety-nine percent where the alternative is no connection at all. It asks compute
> for about two percent of the hours — and gets months of running time in return.

**SCREEN:** click — **three-year plan**, then **worst-day chart**.

> Three years: three times more megawatt-months than all-firm. Worst day of the year: no red —
> zero violations.

**CUES:** the three strategies are the demo now — if you lose 20 seconds anywhere, cut the map
sentence, never this. Say "safe, and useless" flat, without a smile; it is the contrast that lands.

---

### ⏱ 2:00 – 2:20 · IMPROVEMENT · the Replay loop · 44 words (18 s + animation)

**SCREEN:** scroll to the **score curve**. `Replay loop` is on it.

> Now the part the organisers asked for: learning. I press Replay loop.

**SCREEN:** **click `Replay loop`.** The curve animates from iteration 0 to {{ITERATIONS}}, counters
tick, the archive of kept plans fills in. Let it move while you talk.

> Every dot is one plan. The proposer writes it, the evaluator breaks it, the repair step fixes
> it, the archive keeps the best. {{ITERATIONS}} iterations of that. Tonight's run, not a mock-up.

**CUES:** the click is the most important physical action of the demo — click first, then speak.
If nothing happens, say "and here is the recorded run" and switch to the backup video. Do not
debug on stage.

---

### ⏱ 2:20 – 2:50 · HOW IT EXPANDS · 56 words (23 s)

**SCREEN:** leave the score curve up. It is your evidence while you talk about the future.

> Three next steps. One: real feeders — swap synthetic substations for PG&E GRIP line sections,
> five hundred seventy-six hourly values per section. Two: real physics — pandapower power flow
> with N-1 outages instead of a headroom model. Three: real signal — OpenADR and hourly prices, so
> curtailment follows money and carbon. Same loop, four regions already.

**CUES:** count on your fingers: one, two, three. It stops you speeding up.

---

### ⏱ 2:50 – 3:00 · ASK · 26 words (11 s)

**SCREEN:** nothing changes.

> Ask: one utility engineer with a feeder we can model, and one flexible-load contract to test
> against. Thank you — repo link is in the submission.

**CUES:** stop at 2:58, even mid-sentence. The clock is the enemy, not the content.

---

## 3. Pronunciation (practise these, nothing else is hard)

| Word | Say it as | Not as |
|---|---|---|
| curtailment | cur-**TAIL**-ment | "curtle-ment" |
| substation | **SUB**-stay-shun | "sub-stayshun" |
| megawatt | **MEG**-a-watt | "meega-watt" |
| headroom | **HED**-room | "head-rum" |
| proposer / evaluator | pro-**POH**-zer / ee-**VAL**-you-ay-tor | "pro-poser" flat |
| PG&E | P-G-and-E | "peegee" |
| ninety-nine point nine nine | say "ninety-nine, point nine nine" then stop | do not add "%" twice |

Pace rule: **145 words per minute feels slow and sounds confident.** If you finish early, lengthen
the pause after "we're trying" — it is better than adding words.

---

## 4. If something breaks

| Failure | Say this | Do this |
|---|---|---|
| Dashboard will not open | "Let me show you the recorded run." | play the backup video, keep the same timing |
| Replay loop does nothing | "The animation is on the recording — here." | switch to the backup video at the curve |
| You lose your place | "Three strategies." | say 0 MW / −205 million / +202 million, then continue at How it expands |
| A judge interrupts | answer in one sentence, then: "I will show that number — one minute." | never argue mid-demo; the Q&A is where you win |

---

## 5. Four things you must not say (honesty guardrails, `CONTRACT.md` §7)

1. Never "real data" about sites, substations or timelines. Say: **"real 2025 EIA-930 demand shape;
   synthetic site geometry and interconnection timelines, documented."**
2. Never "zero violations" without **"in the model"** — we model headroom, not full power flow
   (full answer: `qa-defense.md`, Q5).
3. Never "the agent gets better at everything". It gets better at **this score**.
4. Never quote a solar number on stage. The `solar_mw` column in the CSV has non-physical artefacts
   (±12–16 GW/h); we cite demand and evening ramps only.

---

## Appendix A — numbers used here, and what is still open

All values are final from `results/loop.json` (Lead, engine frozen).

| Thing said on stage | Value | JSON path |
|---|---|---|
| MW at month 12, all-firm | **0** | `baselines.*.mw_at_month12` (firm strategy) |
| Net value, all-firm, 36 months | **$65.1M** | same baseline |
| MW at month 12, all non-firm | **173** | `baselines.max_mw_no_flex.*` |
| Net value, all non-firm | **−$205.4M** | same baseline (SLA penalties) |
| MW at month 12, GRIDRUSH | **69.8** | `best.mw_at_month12` |
| Net value, GRIDRUSH | **+$202.4M** | `best.net_value_musd` |
| MW-months, all-firm → GRIDRUSH | **651 → 2050 (3.15×)** | `comparison.ratio_mwmonths` |
| Sites connected | **19 of 40** | count `best.sites` with mode ≠ skip |

**Still open (2 placeholders):**

| Placeholder | Where it appears | How to fill |
|---|---|---|
| `{{ITERATIONS}}` | 2:00 beat, twice | `len(json.load(open("results/loop.json"))["iterations"])` — read as "one hundred fifty" |
| `{{REPO_URL}}` | Ask beat (spoken as "in the submission") and `submission.md` | the public repo link |

```python
# python3 pitch/fill.py   (run from gridrush/) — writes filled copies to pitch/_stage/
import json, pathlib
d = json.load(open("results/loop.json"))
val = {"ITERATIONS": str(len(d["iterations"])),
       "REPO_URL": "https://github.com/<you>/gridrush"}
out = pathlib.Path("pitch/_stage"); out.mkdir(exist_ok=True)
for name in ("submission.md", "demo-script.md"):
    txt = (pathlib.Path("pitch") / name).read_text()
    for k, v in val.items():
        txt = txt.replace("{{%s}}" % k, v)
    (out / name).write_text(txt)
print("filled ->", out, val)
```

> After filling, read `pitch/_stage/demo-script.md` aloud once: one pass catches any sentence a
> number made ungrammatical. If `iterations` is exactly 150, say "one hundred fifty"; if 200+,
> say "over two hundred".

---

## Appendix B — the on-stage quotes used here (verbatim from the transcript)

| Used at | Speaker | Verbatim |
|---|---|---|
| 0:00 | PG&E (David, partnerships team) | "speed to power is basically, right now, if you're a data center or if you want to connect a data center to the grid, it'll take you 7 to 10 years to do that." |
| 0:00 | same | "if you can reduce your availability … down to like 98% or something like that, there's probably just 2 weeks out of the year, maybe, or even a few days out of the year, where our load is really, really high when it gets really hot … if the data center is willing to curtail their load … for a few days out of the year, that could drastically improve the chances and the speed of which they could connect." |
| 0:00 | 98% line is PG&E; who asks the follow-up is **unclear in the recording** — do not attribute it | "But what if it was guaranteed capacity for 98% of the time?" → host: "But is that how power companies work?" → PG&E: "**We're trying.**" |
| Q&A only | same | "we actually do this on the distribution side … for Tesla, like for superchargers and those kinds of sites, like small footprints." |
| Q&A only | Arham (Stanford Energy Club) | "if there is more energy that's available, each megawatt would be would $5000000 uh for 3 to 4 years." |

Transcript has no timestamps. Locator: characters 27,187–28,585 of the file (≈48–50% of the
recording, the middle of the morning session).

---

## Appendix C — one-page cue card (print this)

```
BEFORE: dashboard full screen 125% · three-strategy card first · Replay loop in view · Wi-Fi off

0:00  look up                "seven to ten years ... we're trying."
0:20  CLICK map              "real 2025 demand shape, synthetic geometry — we say so."
0:50  CLICK 3 strategies     "firm: 0 MW, $65M. non-firm: 173 MW, -$205M. GRIDRUSH: 70 MW, +$202M."
1:30  point "19 of 40"       "one decision per site ... 2% of hours for months of running time."
1:45  CLICK plan + worst day "three times more megawatt-months. No red: zero violations."
2:00  CLICK Replay loop      "proposer, evaluator, repair, archive. Tonight's run."
2:20  three fingers          "feeders / physics / signal."
2:50  stop at 2:58           "one utility engineer, one contract. Thank you."
```
