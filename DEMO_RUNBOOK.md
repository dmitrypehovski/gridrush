# GRIDRUSH — day plan (for you, the solo participant)

Everything below is in Pacific Time (PT), the event time at AGI House SF.
Stage and submission clocks: **submission 17:00**, **demo 18:30**, the talk is 3 minutes.

---

## 1. What we're building (one sentence, memorize it)

> "GRIDRUSH is an agent that decides which compute loads to connect, with what firm/flexible
> capacity and what SLA, to get the most MW·months over 36 months at zero grid violations.
> It answers an audience question with a number: 'what if 98% availability?'"

The project lives in `gridrush/`. Everything runs offline, no network, no API keys.

## 2. The key numbers (final, from `results/loop.json`)

| What | Value |
|---|---|
| Agent net value | **+$279.9M** over 36 months (CAL) |
| Best "honest" strategy (all firm, wait for the queue) | $65M and **0 MW by month 12** |
| Naive "all non-firm at max" | 173 MW by month 12, but **−$449.5M** |
| **Ratio** | **4.30×** on net value, 3.82× on sellable MW·months |
| Sellable MW by month 12 | **85.4 MW** vs 0 |
| Grid violations | **0 MWh** |
| Sites connected | 32 of 40 (the agent can say "no") |
| Stress day | CAISO 2025-08-21, peak **43,860 MW at 20:00**, sun already 4.4 GW |
| Evening peak: the naive portfolio must shed **28 MW**, the agent — **1.9 MW** | the key flexibility slide |
| Loop | 207 iterations: 200 mutator (plateau ~179) + 7 LLM generations (jump to **279.9**) |
| SLA mix | 16 sites 99.99% (×1.25), 6 × 99.9%, 10 × 99% (×0.80) |

## 3. What to open on stage (checklist 10 minutes before)

1. `open /Users/dmitrypehovski/Documents/deepseek-harness/default-workspace/gridrush/web/dashboard.html`
   — one tab, full screen. The map is now **geographic** (coordinates from `data/sites.json`),
   the learning curve is already fully drawn on load; `Replay loop` restarts the animation.
   **Screen:** **1920×1080, zoom 100%** — that's the ideal mode. If the projector/laptop gives
   less (1280×800, 1366×768), the dashboard switches to compact mode on its own. **Do not set
   zoom >100%** — at 125% everything breaks.
2. Check: the **three strategies** are visible (firm / non-firm / GRIDRUSH), the **Replay loop**
   button, the map of 8 substations, the stacked bar "MW by month", "worst day".
3. A separate tab: `gridrush/web/physics.html` — real AC power flow (in case of the question
   "where's the physics?"). This is NOT shown in the main three minutes, only for Q&A.
4. Backup: record a 3-minute screencast of the demo to your phone/QuickTime in advance (17:30).
   If the browser dies — you play the recording and talk.
5. Phone in your pocket, Wi-Fi off (the demo is offline), notifications off.

## 4. Talk timing (3:00)

| Time | What | Screen |
|---|---|---|
| 0:00–0:20 | The problem: 7–10 years to interconnect; the audience question about 98% | you click nothing |
| 0:20–0:50 | What the agent does, data honesty (real EIA-930 / synthetic geometry) | map |
| 0:50–2:00 | **The three strategies** — this is the core. "Safe and useless" / "faster and worse" / "GRIDRUSH" | three-strategies card |
| 2:00–2:30 | Learning: **Replay loop** → "the parametric search plateaus at 179, the LLM agent rewrites the policy (exact DP) and jumps to 280; 207 iterations" | curve |
| 2:30–2:55 | Worst day + physics: "at the evening peak the naive portfolio must shed 28 MW, we shed 1 MW; and the real AC power flow: 8 MW of headroom on the feeder, our 5 largest sites need 32 — that's a siting problem, not a megawatt problem" | worst day, then the curve |
| 2:55–3:00 | Ask: real feeders (PG&E GRIP, 576 values) + AC PF inside the loop + OpenADR | — |
| 2:45–3:00 | Ask: we need real hosting capacity + the queue from a utility/developer for one region | — |

The verbatim English script is in `gridrush/pitch/demo-script.md` (415 words = ~2:51 at 145 wpm).
**Your personal risk is overrunning.** Aim for 2:45. If rehearsal comes out >3:00, cut in this
order: (1) the map line in Approach, (2) the third how-it-expands bullet (OpenADR/signal),
(3) the AC fact (it's in Q&A). Do NOT cut: the three strategies, "28 → 1", the 179→280 jump.
Three fallback lines and the 60-second version are in `pitch/cue-card.md`.

## 5. Submission (17:00)

The ready text: `gridrush/pitch/submission.md` (check that the `{{...}}` placeholders are replaced).
If the form asks for a repo link — a local folder won't do, so:
- option A (the right one): `git init` in `gridrush/`, push to your GitHub (2 minutes).
- option B: attach the `gridrush.zip` archive (but then write "repo attached" in the form).
Tell me — I'll build the archive and/or help with `git init` in one command.

## 6. What to say if asked (short answers; the wording is your call)

1. **Is this real data?** Real hourly load/solar for 2025 across 12 operators (EIA-930,
   public domain). The synthetic parts are labeled too: site geometry, capacities, queue timelines,
   costs. All parameters are in `sim/assumptions.md`, and the screen says "synthetic".
2. **Where's the agent here, isn't this just optimization?** There's a proposer→simulator→score→keep
   loop. In `loop/` there's a run over 180 generations with a log of every iteration (the curve
   from −1245 to +202). In `rsi_agent/` it's the same, but with an LLM proposer: the agent writes
   the policy code, the simulator judges it, the best one stays. Plus the agent repairs itself:
   `repair_portfolio` — plan→check→shrink MW to fit the SLA.
3. **Isn't the baseline a straw man?** Three strategies, all in JSON: "all firm" is what people
   actually do (safe and slow); "all non-firm" is a realistic greedy strategy — it honestly wins
   on MW by month 12 (173 MW) and honestly loses on money (−$449.5M because of SLA).
4. **Where does the SLA come from?** Straight from the stage: "98% availability → drastically
   improve speed", "people pay a premium for 6 nines". We put a price on it: 99.99% = ×1.25,
   99.9% = ×1.0, 99% = ×0.80.
5. **Where's the power flow?** The main engine is an hourly verifier over the headroom profile
   (the same logic as PG&E ICA: 576 hourly values per feeder). Separately, we ran a real AC power
   flow on a German 20 kV feeder (pandapower, mv_oberrhein): it converges, 0 violations, headroom
   2.9–5.1 MW per bus — `web/physics.html`. Next step: replace the profile with AC PF.
6. **Why only 32 sites?** Connecting all 40 is impossible without violations; the agent picks
   the ones where MW·months per unit of headroom are highest. "Knowing how to say no" is part of
   the result.
7. **Who pays?** The compute offtaker; we model contract margin (~$1.2M/MW-year) and how much of
   it is achievable at all given today's interconnection timelines.
8. **What's next?** Replace the synthetic parts: real hosting capacity (PG&E GRIP/ICA) and queue
   data (ERCOT batch data), AC power flow + N-1, then aggregating sites into one grid service
   (track 4).

## 7. Schedule until the demo

| Time PT | What |
|---|---|
| 13:00 | Lunch. Do nothing — eat and talk to people (judges are people too). |
| 13:30 | Numbers frozen (`results/FINAL_NUMBERS.md`). A working dashboard + the pitch. Read it aloud 2 times. |
| 14:30 | Final numbers freeze. Nothing changes after this. |
| 15:30 | Rehearse the 3 minutes aloud with a timer, 2–3 times. Record the screencast. |
| 16:30 | Submission text final, repo/archive ready. |
| 17:00 | **Submission deadline.** |
| 17:00–18:20 | Rest, water, one more rehearsal. |
| 18:30 | Demo. |

## 7.5 If a judge asks you to "run it live" — LIVE RUN

There is a real live run in the browser (a separate page; it doesn't touch the main dashboard):

```bash
cd /Users/dmitrypehovski/Documents/deepseek-harness/default-workspace/gridrush
python3 web/live_server.py
```

**Do not close the terminal running the server** — the link only lives while the process runs
(`ERR_CONNECTION_REFUSED` = the server isn't running or you stopped it with Ctrl+C). If you
open it late on stage and see `DONE` — press the **`Run again`** button in the top-right corner.

`http://127.0.0.1:8767/` opens — **11 seconds**, and you watch it happen: the score climbs
$0 → $279.9M, the log shows the parametric search giving way to the local one (the agent edits
the plan site by site: `S07-5 → flex 4.0 MW @ 0.9990`), and in the end the LLM policy kicks in
and delivers the final **$279.9M / 85.4 MW / 0 violations**.

What to say: "This is live, not a recording: the proposer writes a plan, the verifier replays all
eight thousand seven hundred sixty hours, the archive keeps the best. Twelve seconds. The last jump
is the policy the LLM rewrote during the day."

Final-state screenshot for the backup: `web/qa_live_run.png` (the state before the Run again
button appears).

**Important:** the main dashboard (`web/dashboard.html`) opens as a file and **needs no server**.
The live run is a separate option — "show that it's really computing right now". If the stage
isn't ready to wait 11 seconds — don't start it; show `Replay loop` and say "the same run,
replayed".

## 7.55 Physics-in-the-loop and all regions (for Q&A and "show me more")

- **`web/dashboard_physics.html`** — the variant where the real AC power flow is built into the
  loop as an admission constraint (6.53 MW per substation, all 8 substations clean): **2.39× /
  $155.5M**. It answers "where's the power flow?" with no caveats: it's inside the optimization.
- **`web/regions.html`** — four operators (CAL/TEX/PJM/MISO) + the physics-in-the-loop card,
  with links to `dashboard_<REGION>.html`. It answers "did you tune this for one region?".
- Rebuild: `<venv>/python sim/physics_gate.py` → `<venv>/python loop/run_physics.py
  --warm-start results/loop.json --budget 2500` → `python3 web/build.py results/loop_physics.json
  -o web/dashboard_physics.html`; `python3 web/build_regions.py`.

## 7.57 Real PG&E data (for Q&A "isn't it all synthetic?")

- `sim/real_sites.py` — pulls the public **PG&E GRIP Data Portal** (ArcGIS REST, no key):
  8 real substations with real coordinates, facility rating and 2026 load
  (SAN RAMON 302/137 MW, CLAYTON 193/125, STOCKDALE 327/275, etc.).
- Run on them: `GRIDRUSH_SITES=real python3 loop/run.py --region CAL --iters 80 --seeds 1
  --policy-file rsi_agent/gen_6.py --out results/loop_real.json`, then
  `python3 web/build.py results/loop_real.json -o web/dashboard_real.html`.
- Result: **1.22×, 397.7 MW@12, 11,533 MW·months, 0 violations**. The honest conclusion: at the
  aggregate substation level the real PG&E substations are large and are not the bottleneck;
  the limit lives at the feeder level — in a sample of 2,000 GNA circuits **124 circuits (6.2%)
  are already deficient in 2026** (up to 12.4 MW). That is exactly the ask: circuit-level ICA.
- See: `web/regions.html` (third block) and `web/dashboard_real.html`; screenshot
  `web/qa_real_dashboard.png`.

## 7.6 One-pager for judges

`pitch/GRIDRUSH-one-pager.pdf` — a single A4 landscape page: the three strategies, KPIs, the
learning curve, "how it learns", physics, real/synthetic, launch commands. You can print 3–5
copies and leave them after the demo, or send it in the form as a supplement. Rebuild:
`python3 pitch/build_onepager.py` (reads `results/loop.json`), then print to PDF from Chrome
(see `pitch/MAKE_PDF.md`).

## 8. Fallbacks

- If the dashboard didn't open — you have `results/loop.json` and the static numbers; you can
  talk through the table in §2 with no screen.
- If the numbers go sideways — "final calibration", don't apologize, keep going with the three
  strategies.
- If you're short on time — cut the map and how-it-expands, but the three strategies + Replay loop
  stay.
