# GRIDRUSH — Q&A defence: 14 опасных вопросов

> Формат: **вопрос по-английски** (так его зададут) + русская пометка, зачем спрашивают, +
> **готовый ответ дословно**, 2–3 предложения. Учить наизусть не надо: выучи первые 6 слов
> каждого ответа, дальше говори своими.
>
> Золотое правило: **не знаешь — скажи «I don't know» и добавь, как проверишь за неделю.**
> Второе правило: каждую цифру сразу переводи в решение («поэтому мы…»).
> Третье (после 15:00): **$202M — это не «мы заработали».** Это modelled compute margin за 36
> месяцев на синтетическом портфеле. Не говорите "we made" и "revenue".

---

## Q1. «Is this real data?» — *самый частый*

> Partly — and we say which part. The hourly demand and the load shape are real 2025 EIA-930 data
> for twelve US operators: public domain, all eight thousand seven hundred sixty hours. The sites,
> the substation capacities and the interconnection timelines are synthetic, parameterised from this
> repo and from what was said on this stage, and every parameter is in the assumptions panel. So:
> real demand shape, synthetic geometry.

**Добивка:** «The comparison does not depend on the synthetic part being exact — all three
strategies use the same sites and the same timelines.»

**Если спросят про solar** (одобренная формулировка, отвечать уверенно, не извиняясь): «The solar
column in the EIA-930 starter set has non-physical artifacts, so we do not use it for capacity or
stress calculations — that is written down in `sim/assumptions.md`. We build stress on demand and on
evening ramps, which are clean.»

---

## Q2. «Why are your baselines so weak? Did you tune them to lose?»

> We did not invent weak strategies — we implemented the two things the market actually does. All
> firm and wait for the queue gives 0 MW at month 12: that is today's default, safe and slow. Sign
> everything non-firm at maximum is the shortcut everyone tries, and it does reach 173 MW at month
> 12 — but it breaks the SLA and loses $205M. Both are in the JSON with all their numbers, and the
> non-firm one is genuinely faster than us; it just is not sellable.

**Не говорите** «the baseline is dumb». Говорите «the baseline is what people do».

---

## Q3. «Did you tune this for one region?»

> Same loop, same parameters, four regions, no per-region tuning: CAISO 3.11×, ERCOT 2.60×, PJM
> 2.49×, MISO 2.68×, all against that region's own firm baseline. Three of the four are at zero
> violations; PJM shows 0.2 MWh over the year, and we print it instead of hiding it. The method is
> not fitted to California — the only thing that changes is the input file.

---

## Q4. «This is just optimization. Where is the agent?»

Самый вероятный вопрос от организаторов — их критерий «learning capabilities of your agents».

> An optimiser gives you one answer. This gives you a loop that gets better each run: a proposer
> writes a portfolio, an evaluator scores it, a **repair** step fixes the violations the evaluator
> found, and the archive keeps the best plans as the starting point for the next round. The
> improvement curve is the deliverable — I am selling the loop that produces plans, not one plan. On
> top of that there is a separate LLM-in-the-loop log in `rsi_agent/`, where the model proposes the
> structure — where flexibility is worth trying, where a battery helps — so you can audit the
> reasoning, not just the number.

**Терминология из `theme/rsi.md`:** это **bounded RSI** — агент улучшает свой план и свой поиск,
не свои веса. Говорите именно так, это язык организаторов.

---

## Q5. «Why only 19 of 40 sites? Why not connect everything?»

> Because 21 sites fail on economics, not on capacity: their energise date is so late that the
> megawatt-months never repay the wait or the battery. The agent can say no — that is the difference
> between a plan and a wish list. Every skipped site and its reason are in the JSON.

**Добивка:** «A human with the same 40 sites would connect all of them and lose money on 21.»

---

## Q6. «Where is power flow?» — *спросит любой энергетик*

Не врать. Слабость превращаем в честность + показываем отдельную валидацию.

> The main engine is an hourly verifier on a headroom profile — the same logic utility ICA screens
> use, and PG&E's ICA publishes 576 hourly values per line section and calls them "directional, not
> a guarantee". Separately, we validate the load class with real AC power flow: pandapower on a real
> German 20 kV medium-voltage feeder — it converges, zero violations, minimum voltage {{V_MIN}} p.u.,
> headroom 2.9–5.1 MW per bus. The next step is to replace the headroom profile with full AC power
> flow inside the loop.

**Если спросят «так нарушения могут быть на самом деле?»:** «On line thermal limits and voltages —
that is exactly what the pandapower validation adds. On the capacity limits we model, no.»
**Подстановка:** `{{V_MIN}}` ← `results/powerflow.json` (поле с минимальным напряжением,
`min_v_pu`), читается как «zero point nine eight five p.u.». Если файла ещё нет — уберите
предложение с цифрой и оставьте «results are in the repo».

**Если `physics.html` не готов к 18:30:** первые два предложения всё равно верны, но не обещайте
цифры — скажите «we are validating it on a real 20 kV feeder tonight, results in the repo».

---

## Q7. «What if 10 MW does not fit?»

> Then the agent does not fit 10. It picks any size from half a megawatt up to that site's actual
> headroom — so it may install 4 today and step up later; or add a battery to cover the tight hours;
> or split the load across substations. That choice is the search space, and per-site numbers are in
> the JSON. We never assume the maximum.

---

## Q8. «Who pays? And is $202M real money?»

> The payer is the compute off-taker, and the $202M is not revenue — it is modelled compute margin
> over 36 months on this synthetic portfolio, at about $1.2 million per MW-year, which is the
> five-million-per-MW-over-three-to-four-years figure said on this stage, divided out. What we
> measure is how much of that margin is reachable given today's connection timelines: $202M with
> GRIDRUSH, $65M waiting for firm, negative if you sign everything non-firm. The utility pays
> nothing and receives capped, predictable curtailment plus telemetry.

---

## Q9. «Why not just put a battery everywhere?»

> Because a battery does not create grid capacity — it only moves the site's own draw by a few
> hours, and a 10 MW site with a four-hour battery still needs headroom in the other 8,756 hours. We
> price it honestly: 0.35 million per MW plus 0.25 million per MWh, so the search only buys battery
> where it converts curtailment hours into availability cheaply. Look at the site table — batteries
> appear at only some sites.

---

## Q10. «Where does the SLA come from?»

> The menu is per site: 99.99, 99.9 or 99 percent, and the agent chooses where the premium is worth
> paying — 99.99 where the grid is calm, 99 where the alternative is no connection at all. One
> detail we computed: two weeks a year is about 96 percent, so the 98 percent the PG&E engineer
> floated on stage is actually the *tighter* promise. And we enforce it as an hours-per-year budget
> with a penalty, because as he said, ten minutes a day you can design for; two random hours you
> cannot.

**Побочный эффект:** вы показываете, что посчитали арифметику зала.

---

## Q11. «Why is this not an Excel solver?»

> An LP or MILP would probably beat us on one fixed instance, and I would say that on stage. But it
> gives you neither an independent verifier you can audit after the fact, nor a policy that
> transfers — the loop re-proposes for a new region instead of you re-modelling it by hand. And the
> space is mixed: forty sites, four modes, continuous sizes, a per-site SLA and thirty-six months of
> timing. That is a search, not one solve.

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

## Если судья дожмёт (4 быстрых добивки)

| Атака | Ответ (одно-два предложения) |
|---|---|
| «98% — это просто скидка, вы продаёте продукт хуже» | «It is a different product, not a worse one: guaranteed capacity 99.99 or 99 percent, priced accordingly, with the tier chosen per site. The alternative today is a hundred percent guarantee and zero megawatts for seven years.» |
| «Ваши таймлайны выдуманы» | «Yes, and they are the first thing to replace — they come from MISO's eighteen-to-thirty-six-month request window, and the comparison is robust because all three strategies use the same timelines. Give me your queue position and I will rerun it in a minute.» |
| «Почему utility должен доверять плану агента?» | «Nobody should trust it — they should audit it. Every hour of the year is checked by a verifier separate from the optimiser, and the output is a table of sites, modes, MW and curtailment hours: the format a utility already reviews.» |
| «У вас в данных артефакт по солнцу» | «Yes — the EIA-930 starter set's solar column has non-physical artifacts, so we exclude it from capacity and stress calculations, and say so in the assumptions. Stress is built on demand and evening ramps, which are clean.» |
| «Ваш агент просто перебирает варианты» | «It does more than recombine values: the archive changes what the next proposal looks like, and the LLM log shows structural choices — which sites to try as flexible, where a battery is worth buying. That is search over hypotheses, not tuning one number.» |

---

## Чего не говорить никогда

1. **Не** «real data» про сайты, подстанции, таймлайны. Только: «real 2025 EIA-930 demand shape;
   synthetic site geometry and interconnection timelines, documented».
2. **Не** «zero violations» без «in the model» / «of the limits we model». Иначе Q6 вас убьёт.
   В четырёх регионах у PJM 0.2 MWh — произносите это сами, до того как спросят.
3. **Не** «we made $202M», не «revenue», не «profit». Только: «modelled compute margin over 36
   months on this synthetic portfolio».
4. **Не** ссылайтесь на солнечную колонку из CSV — там нефизические артефакты (±12–16 GW/h).
   Про пик говорите demand и вечерние рампы.
5. **Не** «five nines» и не обещайте 99.999%.
6. **Не** «we beat an optimiser». Говорите «we give you the loop, the verifier and the curve».
