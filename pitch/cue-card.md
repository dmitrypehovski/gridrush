# GRIDRUSH — cue card

**One page. Phone or print. Glance, do not read.** Numbers frozen 2026-11-08.

---

### 0:00 — PROBLEM

- **"seven to ten years"** ← slow down, it is the anchor
- "98% of the time… **the utility answer: we're trying.**"
- one beat of silence. no smile.

### 0:20 — APPROACH *(click: map)*

- "**40 sites, 8 substations**, four choices per site"
- "8,760 hours of 2025 — **violations and SLA**"
- "real demand data, synthetic geometry — **and we say so**"

### 0:50 — RESULT *(click: three-strategy card)*

- firm: **0 MW**, $65M — "safe, and useless"
- non-firm: **173 MW**, **−$450M** — "faster, and worse"
- GRIDRUSH: **85 MW**, **+$280M**, no red
- "**32 sites** — and no to eight"
- "**2% of the hours** for months of running time"

*(click: plan)* "**four times** more value. no red."
*(click: worst day)* "the naive plan **sheds 28 MW** — GRIDRUSH **never more than one**."

### 2:00 — LEARNING *(click: `Replay loop`)*

- "**proposer, evaluator, repair, archive**"
- "**plateaus at 179** → the LLM rewrites the policy → **280**"
- "**207 iterations**. tonight's run, not a mock-up."

### 2:30 — EXPANDS *(three fingers)*

- "feeders / physics / signal"
- "**8 MW spare** on a real feeder; our five biggest sites need **32**"
- "**a siting problem, not a megawatt problem**"

### 2:55 — ASK

- "**one utility engineer, one flex contract.** thank you — repo is attached."

---

## THE 7 NUMBERS

```
   4.3×      $280M      $65M      −$450M
   85 MW     0 MW       32/40
```

*(net ratio · margin · firm margin · non-firm loss · MW@12 · firm MW@12 · sites)*

---

## IF YOU GET LOST — 3 phrases

1. **"Three strategies, same forty sites."** → point at the card, carry on.
2. **"Zero megawatts at month twelve — and eighty-five."** → breathe.
3. **"The loop gets better each run — let me show you the curve."** → click Replay loop.

**Never say:** "real data" (sites are synthetic) · "zero violations" without **"in the model"** ·
"we made $280M" (it is *modelled compute margin*) · any solar number.

---

## THE 60-SECOND VERSION

1. Data centres wait **seven to ten years** for power. On this stage, PG&E said a load that curtails
   a few hot days a year could connect much faster.
2. GRIDRUSH plans that trade: **40 sites, 8 substations**, firm / flexible / battery, chosen site by
   site over **36 months**.
3. A verifier replays **all 8,760 hours of 2025** and checks violations and SLA — one evaluation,
   **under 100 milliseconds**.
4. Three strategies, same sites: firm gives **0 MW** at month 12; all non-firm gives **173 MW** but
   loses **$450M**; GRIDRUSH gives **85 MW** and **$280M** of modelled margin — **4.3×**.
5. **Zero violations in the model**, every site inside its SLA, **32 of 40** sites — the agent can
   say no.
6. Same policy, **four operators, no tuning: 3.4 to 4.3× and zero violations**. Real AC power flow says **8 MW spare** on
   one feeder versus **32 MW** for our five biggest sites: a siting problem, not a megawatt problem.
