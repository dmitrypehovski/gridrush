# GRIDRUSH — Q&A defence: 14 опасных вопросов

> **FROZEN.** Числа из `results/FINAL_NUMBERS.md`, `results/loop.json`, `results/powerflow.json`.
> Формат: вопрос по-английски (так его зададут) + русская пометка, зачем спрашивают, + готовый
> ответ дословно, 2–3 предложения. Учить наизусть не надо: выучи первые 6 слов каждого ответа.
>
> Три правила: **не знаешь — скажи «I don't know» и добавь, как проверишь**; каждую цифру сразу
> переводи в решение («поэтому мы…»); **$280M — это не «мы заработали»** (это modelled compute
> margin за 36 месяцев на синтетическом портфеле).

---

## Q1. «Is this real data?» — *самый частый*

> Partly — and we say which part. The hourly demand and the load shape are real 2025 EIA-930 data
> for twelve US operators: public domain, all eight thousand seven hundred sixty hours. The sites,
> the substation capacities and the interconnection timelines are synthetic, parameterised from this
> repo and from what was said on stage, and every parameter is in the assumptions panel. So: real
> demand shape, synthetic geometry.

**Добивка:** «The comparison does not depend on the synthetic part being exact — all three
strategies use the same sites and the same timelines.»

**Если спросят про solar:** «The solar column in the EIA-930 starter set has non-physical artifacts,
so we do not use it for capacity or stress calculations — that is written down in
`sim/assumptions.md`. We build stress on demand and on evening ramps, which are clean.»

---

## Q2. «Why are your baselines so weak? Did you tune them to lose?»

> We did not invent weak strategies — we implemented the two things the market actually does. All
> firm and wait for the queue gives 0 MW at month 12: that is today's default, safe and slow.
> Sign everything non-firm at maximum is the shortcut everyone tries, and it does reach 172.6 MW at
> month 12 — but it breaches SLA by 1.15 million megawatt-hours and loses $449M. Both are in the
> JSON with all their numbers, and the non-firm one is genuinely faster than us; it just is not
> sellable.

**Не говорите** «the baseline is dumb». Говорите «the baseline is what people do».

---

## Q3. «Did you tune this for one region?»

> Same policy, same parameters, four operators, no per-region tuning: CAISO 4.30×, ERCOT 3.41×,
> PJM 4.07×, MISO 3.88×, each against that operator's own firm baseline — three point four to four
> point three times, with zero modelled violations in all four and 81 to 85 MW running by month 12.
> Nothing is fitted to California: the only thing that changes is the input file.

---

## Q4. «This is just optimization. Where is the agent?»

Самый вероятный вопрос от организаторов — их критерий «learning capabilities of your agents».

> An optimiser gives you one answer. This gives you a loop that gets better each run: a proposer
> writes a portfolio, an evaluator scores it, a **repair** step fixes what the evaluator flagged,
> and the archive keeps the best as the starting point for the next round. The proof is in the
> curve: 207 iterations, 200 from a fast parametric mutator that plateaus at 178.6 — and then seven
> generations where the LLM proposer rewrites the policy itself, exact per-substation DP, and jumps
> to 269.6 and then 279.9. The LLM log is in `rsi_agent/rsi_log.json`, so you can audit what it
> changed and why.

**Терминология из `theme/rsi.md`:** это **bounded RSI** — агент улучшает свой план и свой поиск,
не свои веса. Говорите именно так.

---

## Q5. «Why only 32 of 40 sites? Why not connect everything?»

> Because 8 sites fail on economics, not on capacity: their energise date is so late that the
> megawatt-months never repay the wait. The agent can say no — that is the difference between a plan
> and a wish list. Every skipped site and its reason are in the JSON.

**Добивка:** «A human with the same 40 sites would connect all of them and lose money on eight.»

---

## Q6. «Where is the power flow?» — *спросит любой энергетик*

Дословно одобренная формулировка — не пересказывать:

> Two levels. The main engine is an hourly capacity verifier on a headroom profile — the same shape
> of data a utility publishes (PG&E GRIC/ICA: 576 hourly values per line section). On top of that we
> validated the load class with a **real AC power flow**: pandapower's `mv_oberrhein`, a real 20 kV
> German MV feeder (179 buses, 2×25 MVA transformers). Base case converges at min V 0.9756 p.u.; our
> loads fit **8.2 MW of spare feeder capacity** with 0 violations (min V 0.9635 p.u. at 100%
> transformer loading). Our five largest sites total 31.8 MW — **they do not fit on one feeder**
> (71 violations, voltage collapse), which is exactly why the agent distributes across 8 substations
> and sizes each site to local headroom. Same loop, real physics: it confirms that 0.5–10 MW edge
> sites are the right unit.

**Если спросят «так нарушения могут быть на самом деле?»:** «On line thermal limits and voltages —
that is exactly what the AC validation adds: it says a single feeder cannot host the portfolio, and
the plan already spreads across eight substations. On the capacity limits we model, no.»
**Если `physics.html` не готов:** первые два предложения всё равно верны; скажите «results are in
the repo» и не называйте цифры по памяти.

---

## Q7. «What if 10 MW does not fit?»

> Then the agent does not fit 10. It picks any size from half a megawatt up to that site's actual
> headroom — so it may install 4 today and step up later; or split the load across substations. The
> AC check shows why this matters: one feeder gives 8.2 MW of spare capacity, the largest sites want
> 6 to 10 each. That choice is the search space, and per-site numbers are in the JSON.

---

## Q8. «Who pays? And is $280M real money?»

> The payer is the compute off-taker, and the $280M is not revenue — it is modelled compute margin
> over 36 months on this synthetic portfolio, at about $1.2 million per MW-year, which is the
> five-million-per-MW-over-three-to-four-years figure said on this stage, divided out. What we
> measure is how much of that margin is reachable given today's connection timelines: $280M with
> GRIDRUSH, $65M waiting for firm, negative if you sign everything non-firm. The utility pays
> nothing and receives capped, predictable curtailment plus telemetry.

---

## Q9. «Why not just put a battery everywhere?»

> The agent bought zero batteries across 32 sites — and that is a result, not an omission. Flexible
> service at 99.99% availability beat battery capex on this data: 0.35 million per MW plus 0.25
> million per MWh is real money, and batteries introduce their own violation risk. The battery option
> stays in the search space; on these timelines and these prices it loses, and the plan shows that.

---

## Q10. «Where does the SLA come from?»

> The menu is three tiers — 99.99, 99.9 and 99 percent — and the agent chooses per site where the
> premium is worth paying: here 16 sites at 99.99, 6 at 99.9 and 10 at 99, which is the trade the
> question on stage was about. Two details: two weeks a year is about 96 percent, so the 98 percent
> the engineer floated is the *tighter* promise; and we enforce the tier as an hours-per-year budget
> with a penalty, because as he said, ten minutes a day you can design for, two random hours you
> cannot.

**Добивка про куртейлмент:** «At the evening peak the naive portfolio must shed 28.4 MW. Ours sheds
at most 1.0 — and the site that sheds it is on a 99 percent tier, so it is contracted.»

---

## Q11. «Why is this not an Excel solver?»

> An LP or MILP would probably beat us on one fixed instance, and I would say that on stage. But it
> gives you neither an independent verifier you can audit after the fact, nor a policy that
> transfers — the best policy here was written by the LLM, in the loop, after the parametric search
> stalled. And the space is mixed: forty sites, four modes, continuous sizes, per-site SLA,
> thirty-six months of timing. That is a search, not one solve.

---

## Q12. «How does this scale to 300 regions?»

> The verifier is numpy and evaluates forty sites in under 100 milliseconds, so one region is a run
> of seconds — we already ran four. Three hundred regions is three hundred times the sites: same
> code, swap the region file, warm-start from the archive. The LLM stays at the proposal level,
> outside the inner loop, so it never becomes the bottleneck.

---

## Q13. «What will you do in the next two weeks?»

> Four things: real feeders instead of synthetic substations — PG&E GRIP and SCE ICA line sections;
> full AC power flow with N-1 inside the loop, not beside it; an OpenADR and price signal so
> curtailment follows money and carbon, not only capacity; and a reproducible public run. Then three
> conversations — one utility, one developer, one flex buyer — to check the $1.2M per MW-year
> against a real contract.

---

## Q14. «You are solo and had one day. What did you actually build?»

> The verifier, the three strategies, the loop with proposer, evaluator, repair and archive, the
> dashboard, the AC power flow validation and the LLM-in-the-loop log — all local, no external API.
> The inputs are public: the EIA-930 hourly CSV that ships with this repo, and catalog ids from the
> energy-hack repo. The honest framing is: I did not invent the grid data or the problem — I built
> the thing that searches for an answer and can prove it.

---

## Если судья дожмёт (5 быстрых добивок)

| Атака | Ответ |
|---|---|
| «98% — это просто скидка, вы продаёте продукт хуже» | «It is a different product, not a worse one: guaranteed capacity 99.99 or 99 percent, priced accordingly, with the tier chosen per site. The alternative today is a hundred percent guarantee and zero megawatts for seven years.» |
| «Ваши таймлайны выдуманы» | «Yes, and they are the first thing to replace — they come from MISO's eighteen-to-thirty-six-month request window, and the comparison is robust because all three strategies use the same timelines. Give me your queue position and I will rerun it in a minute.» |
| «Почему utility должен доверять плану агента?» | «Nobody should trust it — they should audit it. Every hour of the year is checked by a verifier separate from the optimiser, and the output is a table of sites, modes, MW and curtailment hours: the format a utility already reviews.» |
| «У вас в данных артефакт по солнцу» | «Yes — the EIA-930 starter set's solar column has non-physical artifacts, so we exclude it from capacity and stress calculations and say so in the assumptions. Stress is built on demand and evening ramps, which are clean.» |
| «Ваш агент просто перебирает варианты» | «The curve says otherwise: the parametric search plateaus at 178.6, and the jump to 279.9 comes from the LLM rewriting the policy structure, not from tuning a number. That is search over hypotheses — and the log shows each rewrite.» |

---

## Чего не говорить никогда

1. **Не** «real data» про сайты, подстанции, таймлайны. Только: «real 2025 EIA-930 demand shape;
   synthetic site geometry and interconnection timelines, documented».
2. **Не** «zero violations» без «in the model» / «of the capacity limits we model». Иначе Q6
   добивает. Во всех четырёх регионах теперь 0 MWh — но всё равно говорите «in the model».
3. **Не** «we made $280M», не «revenue», не «profit». Только: «modelled compute margin over 36
   months on this synthetic portfolio».
4. **Не** ссылайтесь на солнечную колонку из CSV — там нефизические артефакты (±12–16 GW/h).
5. **Не** обещайте «5 nines» и не называйте `mv_oberrhein` «нашим фидером» — это публичный
   немецкий тест-кейс, и мы используем его как валидацию класса нагрузки, а не как площадку.
6. **Не** «we beat an optimiser». Говорите «we give you the loop, the verifier and the curve».
