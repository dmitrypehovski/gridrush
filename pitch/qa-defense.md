# GRIDRUSH — Q&A defence: 16 dangerous questions

> **FROZEN.** Numbers from `results/FINAL_NUMBERS.md`, `results/loop.json`, `results/powerflow.json`,
> `results/loop_physics.json`, `results/loop_real.json`, `rsi_agent/rsi_log2.json`.
> Format: the question in English (that is how it will be asked) + a note on why they ask + the ready
> answer verbatim, 2–3 sentences. No need to memorise it: learn the first 6 words of each answer.
>
> Three rules: **if you do not know — say "I don't know" and add how you will check**; turn every number
> into a decision immediately ("so we…"); **$280M is not "we made money"** (it is modelled compute
> margin over 36 months on a synthetic portfolio).

---

## Q1. "Is this real data?" — *the most frequent one*

> Partly — and we say which part. The hourly demand and the load shape are real 2025 EIA-930 data
> for twelve US operators: public domain, all eight thousand seven hundred sixty hours. The sites,
> the substation capacities and the interconnection timelines are synthetic, parameterised from this
> repo and from what was said on stage, and every parameter is in the assumptions panel. So: real
> demand shape, synthetic geometry.

**Follow-up:** "The comparison does not depend on the synthetic part being exact — all three
strategies use the same sites and the same timelines."

**If they ask about solar:** "The solar column in the EIA-930 starter set has non-physical artifacts,
so we do not use it for capacity or stress calculations — that is written down in
`sim/assumptions.md`. We build stress on demand and on evening ramps, which are clean."

---

## Q2. "Why are your baselines so weak? Did you tune them to lose?"

> We did not invent weak strategies — we implemented the two things the market actually does. All
> firm and wait for the queue gives 0 MW at month 12: that is today's default, safe and slow.
> Sign everything non-firm at maximum is the shortcut everyone tries, and it does reach 172.6 MW at
> month 12 — but it breaches SLA by 1.15 million megawatt-hours and loses $449M. Both are in the
> JSON with all their numbers, and the non-firm one is genuinely faster than us; it just is not
> sellable.

**Do not say** "the baseline is dumb". Say "the baseline is what people do".

---

## Q3. "Did you tune this for one region?"

> Same policy, same parameters, four operators, no per-region tuning: CAISO 4.30×, ERCOT 3.41×,
> PJM 4.07×, MISO 3.88×, each against that operator's own firm baseline — three point four to four
> point three times, with zero modelled violations in all four and 81 to 85 MW running by month 12.
> Nothing is fitted to California: the only thing that changes is the input file.

---

## Q4. "This is just optimization. Where is the agent?"

The most likely question from the organisers — their criterion "learning capabilities of your agents".

> An optimiser gives you one answer. This gives you a loop that gets better each run: a proposer
> writes a portfolio, an evaluator scores it, a **repair** step fixes what the evaluator flagged,
> and the archive keeps the best as the starting point for the next round. The proof is in the
> curve: 207 iterations, 200 from a fast parametric mutator that plateaus at 178.6 — and then seven
> generations where the LLM proposer rewrites the policy itself, exact per-substation DP, and jumps
> to 269.6 and then 279.9. The LLM log is in `rsi_agent/rsi_log.json`, so you can audit what it
> changed and why.
>
> And it does not stop there: we kept the archive and ran a second round — six more generations,
> best 280.256, plus zero point one two percent, and it converged with a proof, because the DP is the
> exact optimum of the admissible flexible-only space and firm service and batteries are dominated.
> That round is in `rsi_agent/rsi_log2.json` and `BEST2.md`.

**Terminology from `theme/rsi.md`:** this is **bounded RSI** — the agent improves its plan and its search,
not its weights. Use exactly that wording.

---

## Q5. "Why only 32 of 40 sites? Why not connect everything?"

> Because 8 sites fail on economics, not on capacity: their energise date is so late that the
> megawatt-months never repay the wait. The agent can say no — that is the difference between a plan
> and a wish list. Every skipped site and its reason are in the JSON.

**Follow-up:** "A human with the same 40 sites would connect all of them and lose money on eight."

---

## Q6. "Where is the power flow?" — *any power engineer will ask this*

The verbatim approved wording — do not paraphrase:

> Two levels. The main engine is an hourly capacity verifier on a headroom profile — the same shape
> of data a utility publishes (PG&E GRIC/ICA: 576 hourly values per line section). On top of that we
> validated the load class with a **real AC power flow**: pandapower's `mv_oberrhein`, a real 20 kV
> German MV feeder (179 buses, 2×25 MVA transformers). Base case converges at min V 0.9756 p.u.; our
> loads fit **8.2 MW of spare feeder capacity** with 0 violations (min V 0.9635 p.u. at 100%
> transformer loading). Our five largest sites total 31.8 MW — **they do not fit on one feeder**
> (71 violations, voltage collapse), which is exactly why the agent distributes across 8 substations
> and sizes each site to local headroom. Same loop, real physics: it confirms that 0.5–10 MW edge
> sites are the right unit.
>
> And it is not just a check: the measured admission limit (six point five megawatts per feeder) is a
> hard constraint inside the optimizer (`loop/run_physics.py`), and the final plan is verified with
> eight real AC-PF runs — all clean. With real physics the same agent gets 2.39× instead of 4.30×;
> that delta is the value of real ICA data. On stage we quote the conservative limit we enforce:
> six and a half.

**If they ask "so can violations happen in reality?":** "On line thermal limits and voltages —
that is exactly what the AC validation adds: it says a single feeder cannot host the portfolio, and
the plan already spreads across eight substations. On the capacity limits we model, no."
**If `physics.html` is not ready:** the first two sentences are still true; say "results are in
the repo" and do not quote numbers from memory.
**Numbers at hand (if they push):** physics-in-the-loop = 2.39×, $155.5M, 1313 sellable
MW·months, 44.7 MW@12, 29 sites, 8/8 substations AC-PF clean; admission limit **6.53 MW** per
feeder (first violation at 7.03 MW, min V 0.95785 p.u. at 100% loading); delta to the profile model
**−44.5%** net value. That is `results/loop_physics.json` + `results/physics_gate.json`.
**How to explain the difference between 8.2 and 6.53 (explain, do not defend):** 8.2 MW was the first
check (top-5 portfolio, uniform scaling); it showed the order of magnitude. 6.53 MW is the conservative
admission limit that is now **enforced in the optimiser** (distribution across the five best buses in
proportion to headroom; first violation at 7.03 MW). **On stage one number — 6.5.** If they ask:
"Eight point two was the first sweep; six point five is the conservative limit we actually enforce —
the difference is one is a measurement, the other is a constraint." And go straight to 2.39×.
**If `physics.html` is not ready:** the first two sentences are still true; say "results are in
the repo" and do not quote numbers from memory.

---

## Q7. "What if 10 MW does not fit?"

> Then the agent does not fit 10. It picks any size from half a megawatt up to that site's actual
> headroom — so it may install 4 today and step up later; or split the load across substations. The
> AC check shows why this matters: one feeder gives 8.2 MW of spare capacity, the largest sites want
> 6 to 10 each. That choice is the search space, and per-site numbers are in the JSON.

---

## Q8. "Who pays? And is $280M real money?"

> The payer is the compute off-taker, and the $280M is not revenue — it is modelled compute margin
> over 36 months on this synthetic portfolio, at about $1.2 million per MW-year, which is the
> five-million-per-MW-over-three-to-four-years figure said on this stage, divided out. What we
> measure is how much of that margin is reachable given today's connection timelines: $280M with
> GRIDRUSH, $65M waiting for firm, negative if you sign everything non-firm. The utility pays
> nothing and receives capped, predictable curtailment plus telemetry.

---

## Q9. "Why not just put a battery everywhere?"

> The agent bought zero batteries across 32 sites — and that is a result, not an omission. Flexible
> service at 99.99% availability beat battery capex on this data: 0.35 million per MW plus 0.25
> million per MWh is real money, and batteries introduce their own violation risk. The battery option
> stays in the search space; on these timelines and these prices it loses, and the plan shows that.

---

## Q10. "Where does the SLA come from?"

> The menu is three tiers — 99.99, 99.9 and 99 percent — and the agent chooses per site where the
> premium is worth paying: here 16 sites at 99.99, 6 at 99.9 and 10 at 99, which is the trade the
> question on stage was about. Two details: two weeks a year is about 96 percent, so the 98 percent
> the engineer floated is the *tighter* promise; and we enforce the tier as an hours-per-year budget
> with a penalty, because as he said, ten minutes a day you can design for, two random hours you
> cannot.

**Follow-up on curtailment:** "At the evening peak the naive portfolio must shed 28.4 MW. Ours sheds
at most 1.0 — and the site that sheds it is on a 99 percent tier, so it is contracted."

---

## Q11. "Why is this not an Excel solver?"

> An LP or MILP would probably beat us on one fixed instance, and I would say that on stage. But it
> gives you neither an independent verifier you can audit after the fact, nor a policy that
> transfers — the best policy here was written by the LLM, in the loop, after the parametric search
> stalled. And the space is mixed: forty sites, four modes, continuous sizes, per-site SLA,
> thirty-six months of timing. That is a search, not one solve.

---

## Q12. "How does this scale to 300 regions?"

> The verifier is numpy and evaluates forty sites in under 100 milliseconds, so one region is a run
> of seconds — we already ran four. Three hundred regions is three hundred times the sites: same
> code, swap the region file, warm-start from the archive. The LLM stays at the proposal level,
> outside the inner loop, so it never becomes the bottleneck.

---

## Q13. "What will you do in the next two weeks?"

> Four things: real feeders instead of synthetic substations — PG&E GRIP and SCE ICA line sections;
> full AC power flow with N-1 inside the loop, not beside it; an OpenADR and price signal so
> curtailment follows money and carbon, not only capacity; and a reproducible public run. Then three
> conversations — one utility, one developer, one flex buyer — to check the $1.2M per MW-year
> against a real contract.

---

## Q14. "You are solo and had one day. What did you actually build?"

> The verifier, the three strategies, the loop with proposer, evaluator, repair and archive, the
> dashboard, the AC power flow validation and the LLM-in-the-loop log — all local, no external API.
> The inputs are public: the EIA-930 hourly CSV that ships with this repo, and catalog ids from the
> energy-hack repo. The honest framing is: I did not invent the grid data or the problem — I built
> the thing that searches for an answer and can prove it.

---

## Q15. "Are there any real data in this project besides the load?"

They are checking whether everything except one CSV is synthetic.

> Yes. The hourly demand shape is real 2025 EIA-930 for twelve operators, and we also rebuilt the site
> model on the public PG&E GRIP Data Portal — eight real PG&E substations with real names, real
> coordinates, facility ratings and 2026 loadings (`sim/real_sites.py`). What is still synthetic is
> documented and labelled: which candidate sites sit inside a substation, the interconnection
> timelines, and the costs.

**If they ask "which substations?"** — name two or three from `results/FINAL_NUMBERS.md`:
SAN RAMON (Mission) 302.2 / 136.9 MW, STOCKDALE (Kern) 327.1 / 275.2 MW, CLAYTON (Diablo)
193.1 / 124.9 MW. These are public PG&E data, no key required, with coordinates and 2026 loadings.

---

## Q16. "Why is the ratio only 1.22× on real data, and not 4.3×?"

The smartest question of all — answer confidently: this is not a failure but a localisation of the constraint.

> Because at the substation aggregate level those real PG&E substations are large and are not the
> bottleneck — so flexibility buys little there. PG&E's own Grid Needs Assessment shows where the
> constraint actually lives: in a 2,000-circuit sample, 124 circuits are already deficient for 2026,
> by up to 12.4 MW. That is why the next step is circuit-level ICA, and it is exactly the data we ask
> for.

**One-line formula:** "the substation aggregate is not the bottleneck — the circuit is".
**Do not be defensive** and do not call 1.22× a "weak result": the profile model gives 4.3× where the
capacities are synthetic; the real 1.22× shows that the flexibility premium disappears at the aggregate
level and comes back at the circuit level. That is an argument for the next step, not against the method.
Ammunition (if they dig deeper): on real PG&E substations the policy gives **1.22×**, **397.7 MW
by month 12**, **11 533 sellable MW·months**, **0 violations**, **all 40 sites** connected;
net value $1410.1M vs $1158.0M for the best honest strategy. Files: `results/loop_real.json`,
`web/dashboard_real.html`, `sim/real_sites.py`.


---

## If the judge pushes (5 quick follow-ups)

| Attack | Answer |
|---|---|
| "98% is just a discount — you are selling a worse product" | "It is a different product, not a worse one: guaranteed capacity 99.99 or 99 percent, priced accordingly, with the tier chosen per site. The alternative today is a hundred percent guarantee and zero megawatts for seven years." |
| "Your timelines are made up" | "Yes, and they are the first thing to replace — they come from MISO's eighteen-to-thirty-six-month request window, and the comparison is robust because all three strategies use the same timelines. Give me your queue position and I will rerun it in a minute." |
| "Why should the utility trust the agent's plan?" | "Nobody should trust it — they should audit it. Every hour of the year is checked by a verifier separate from the optimiser, and the output is a table of sites, modes, MW and curtailment hours: the format a utility already reviews." |
| "Your data has a solar artifact" | "Yes — the EIA-930 starter set's solar column has non-physical artifacts, so we exclude it from capacity and stress calculations and say so in the assumptions. Stress is built on demand and evening ramps, which are clean." |
| "Your agent is just brute-forcing options" | "The curve says otherwise: the parametric search plateaus at 178.6, and the jump to 279.9 comes from the LLM rewriting the policy structure, not from tuning a number. That is search over hypotheses — and the log shows each rewrite." |

---

## What never to say

1. **Never** "real data" about sites, substations, timelines. Only: "real 2025 EIA-930 demand shape;
   synthetic site geometry and interconnection timelines, documented".
2. **Never** "zero violations" without "in the model" / "of the capacity limits we model". Otherwise Q6
   finishes you off. All four regions now report 0 MWh — but still say "in the model".
3. **Never** "we made $280M", never "revenue", never "profit". Only: "modelled compute margin over 36
   months on this synthetic portfolio".
4. **Never** cite the solar column from the CSV — it has non-physical artifacts (±12–16 GW/h).
5. **Never** promise "5 nines" and never call `mv_oberrhein` "our feeder" — it is a public
   German test case, and we use it as validation of the load class, not as a site.
6. **Never** "we beat an optimiser". Say "we give you the loop, the verifier and the curve".

## Q17. "Isn't your 'independent verifier' just clipping the load?"

Honest answer: for **flexible** service, yes — flexible load cannot exceed headroom by construction,
because that is what the contract means: the site is curtailed to what the grid can carry. Violations
would only appear if *firm* capacity were oversubscribed, and this agent chooses no firm sites. So the
constraint that actually binds here is the **per-site SLA**, which is enforced (zero breach energy),
not the violation count. We now say that explicitly in the README, the dashboard and the frozen
numbers. What would make the violation check load-bearing is a firm-heavy or mixed portfolio — that is
one of the next steps.

## Q18. "Does 4.30× survive if your synthetic economics are wrong?"

The ratio does: prices scale the agent and the baselines together, so it is **invariant to the margin
level** — 4.30× at one-third, one times and three times our margin (`results/sensitivity.json`).
The physical ratio — **3.82×, 2490.6 vs 651.3 contract-compliant MW-months** — contains no prices at
all. Flattening the SLA premium (1.10/1.00/0.95 instead of 1.25/1.00/0.80) and halving the penalty
gives **4.04×**, still above four. What *is* assumption-dependent is the absolute dollar level
($279.9M); the comparison is not.
