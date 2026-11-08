# GRIDRUSH — hooks: «убойные» однострочники

> Каждая цифра — с источником. `catalog id` = ресурс в репо хакатона
> (`python3 scripts/find.py <id>`); «спич» = дословная цитата со сцены (локейтор — позиция в
> символах транскрипта `~/Downloads/Untitled 19.md`, таймкодов в файле нет); «наш спайк» =
> посчитано по `gridrush/data/us_grid_hourly_2025.csv` (real EIA-930, 12 операторов);
> «loop.json» = `gridrush/results/loop.json`.
>
> Правило: **одна цифра на слайд, одна цифра на абзац.** На сцене — максимум три хука из
> списка. Если произносите две цифры подряд, вторая теряется.

---

## 10 главных

| # | Однострочник (English — говорите как есть) | Цифра | Источник |
|---|---|---|---|
| 1 | "Connecting a data center to the grid today takes seven to ten years." | 7–10 лет | **спич**, PG&E (David, partnerships team), символы 27 187 (≈47.7% записи) |
| 2 | "Three strategies, same forty sites: wait for firm power — zero megawatts at month twelve. Sign everything non-firm — one hundred seventy-three megawatts, and minus four hundred fifty million dollars. GRIDRUSH — eighty-five megawatts, plus two hundred eighty million." | 0 / 173 / 85 MW | **loop.json** (final). Это ваш главный слайд: три столбика, два числа на каждом |
| 3 | "The engineer from PG&E said a load that curtails a few hot days a year could connect much faster. Someone in the room asked: so guaranteed capacity only 98% of the time? The utility answer: we're trying." | 98% | **спич**, символы 27 605–28 585 (≈48.5–50.2%) |
| 4 | "We ask compute to be flexible for about two percent of the hours in the year. In exchange, it gets months of running time." | 2.0% часов года (160–177 ч на оператора, все 12) | **наш спайк**: топ-1% спроса ИЛИ топ-1% рампа, 12 операторов. Пересчитано мной 04:28: BPAT 160, остальные 175–177; отклонение ±2 ч зависит от метода квантиля. Подпись на слайде: "flex-worthy hours, 2025 EIA-930" |
| 5 | "ERCOT has about 410 gigawatts of large-load requests on file — about 87% data centers — against 7.5 gigawatts actually approved to energize since 2022." | 410 GW vs 7.5 GW | `ercot-legislative-update-2026` (410 GW, ~87%, на 26.03.2026) + `ercot-constraints-2025` (7 502 MW с янв. 2022) |
| 6 | "CAISO's peak in 2025 was 43,860 megawatts — and it arrived at eight in the evening, not at noon." | 43 860 MW, 2025-08-21 20:00 | **наш спайк** (real EIA-930). Пик — вечерний, поэтому гибкость ценна именно вечером |
| 7 | "On 8 March 2025, CAISO's net load fell to minus 1,140 megawatts at one in the afternoon, then climbed 22,682 megawatts in six hours." | −1 140 → +22 682 MW | **наш спайк**: net load = demand − solar, 08.03.2025 13:00 → 19:00 |
| 8 | "Five million dollars. That is what one megawatt of available capacity is worth, for three to four years." | $5M / MW / 3–4 года | **спич**, Arham, символы 20 085 (≈35.3%). Наш $1.2M/MW-год — это же число, поделённое на срок |
| 9 | "Nearly 100 gigawatts of new load could run on capacity that already exists — if it accepts limited curtailment during grid stress." | ~100 GW | `duke-rethinking-load-growth-2025` (Duke Nicholas Institute, 2025, 22 крупнейших BA) |
| 10 | "On 22 July 2026, nearly 4,000 megawatts of data center load in Virginia disconnected unexpectedly. Earlier events were about 1,500." | 4 000 MW | `pjm-load-transfer-event-2026` (PJM / Dominion review, авг. 2026) |

---

## Одна и та же петля, четыре региона (снимает «вы подогнали под Калифорнию»)

Все четыре перемерены финальной политикой `gen_6` — это и есть доказательство «без тюнинга».

| Регион | ratio net | ratio MW·мес | net, $M | MW @12 | violations |
|---|---|---|---|---|---|
| CAL — CAISO | **4.30×** | 3.82× | 279.91 | 85.4 | 0 |
| TEX — ERCOT | **3.41×** | 2.79× | 304.46 | 84.1 | 0 |
| MIDA — PJM | **4.07×** | 3.57× | 275.30 | 82.4 | 0 |
| MIDW — MISO | **3.88×** | 3.33× | 277.84 | 81.3 | 0 |

**Однострочник:** "The same policy, four operators, **three point four to four point three times**
the value, and zero violations — no per-region tuning."

> Отдельная сила этой таблицы: MW@12 везде 81–85, violations везде 0. Одна политика, четыре разных
> рынка. Это лучший ответ на «вы подогнали под один регион».

---

## В запасе (для Q&A и слайда «проблема»)

| # | Однострочник | Цифра | Источник |
|---|---|---|---|
| 11 | "In MISO, large loads ask for a connection in 18 to 36 months; the fast track exists — non-firm service and firm-service step-up." | 18–36 мес | `miso-large-load-integration`, `miso-firm-service-step-up` |
| 12 | "Half a megawatt to ten megawatts sits below the large-load rules — ERCOT's threshold is 25 megawatts." | 0.5–10 MW < 25 MW | `ercot-nprr1234`, `pge-ica` |
| 13 | "PG&E publishes 576 hourly capacity values per line section — and calls them 'directional, not a guarantee'." | 576 значений | `pge-grip-guide` |
| 14 | "A field demo in Phoenix cut an AI cluster's power by 25% for three hours, software only." | −25% / 3 ч | `emerald-phoenix-2025` (preprint, arXiv 2507.00909) |
| 15 | "Twelve US grid operators moved 3,513 terawatt-hours in 2025 — that is the dataset we load in one line." | 3 513 TWh | **наш спайк** (сумма `demand_mw` по 12 BA, 2025) |
| 16 | "The median interconnection request waits over five years; only 13% of requests from 2000 to 2020 ever reached operation." | >5 лет / 13% | `lbnl-queued-up` (2026 edition) |
| 17 | "A 320-megawatt promise for 2028 became closer to 150. The power you were promised is not the power you get." | 320 → 150 MW | **спич**, Sean (AGI House), символы 45 391 (≈79.7%) |

---

## Как подавать (важнее самих цифр)

| # | Что делать | Почему |
|---|---|---|
| 1 | Цифру говорите **до** объяснения, пауза 1 секунда, потом смысл | зал запоминает последние 4 слова, а не середину |
| 2 | На слайде — только цифра и 3–4 слова. Вслух — предложение целиком | слайд читают, речь слушают |
| 3 | Хук #2 (три стратегии) — единственный, который должен быть **картинкой**: три столбика, на каждом MW и $ | это весь питч в одном кадре |
| 4 | Хук #3 («we're trying») — не улыбайтесь | это завязка, не шутка |
| 5 | Хук #4 («2% часов») — самый сильный новый аргумент. Говорите медленно, это ваша цена сделки | снимает возражение «зачем нам гибкость» |
| 6 | Хук #6 — не утверждайте, что «пик всегда вечером»: у 5 из 12 операторов топ-рампа не в 17–20 | одна неверная деталь убивает доверие ко всем цифрам |
| 7 | Не берите больше трёх хуков на 3 минуты | в демо уже 12 чисел; 13 чисел = 0 чисел |
| 8 | В конце демо не добавляйте новый хук | последняя фраза — «ask», не «ещё статистика» |

**Рекомендуемый набор:** #1 (0:00) → #3 (0:00–0:20) → #2 (0:50–1:45) → #4 (1:40). Остальное —
в Q&A. Хук #15 держите для ответа «насколько велик ваш датасет».

---

## Осторожно с формулировками (проверено на данных, не повторяйте ошибок)

1. **Солнечная колонка в CSV нефизическая** (артефакты ±12–16 ГВт/ч). Не стройте на ней
   аргументы и не произносите «solar was 4,389 MW at eight PM» — это красиво звучит и может быть
   опровергнуто одним вопросом PG&E. Про вечерний пик говорите только через **demand**
   (43 860 MW в 20:00 — факт) и через **вечерние рампы**.
2. **«Топ-рампа всегда вечером»** — верно для CAISO, ERCOT, PJM, MISO, но не для 5 из 12
   операторов. Говорите «in the four largest US grids» или «in our four regions».
3. **$202M — не выручка и не заработанные деньги.** Только: «modelled compute margin over 36
   months on this synthetic portfolio».
4. **Не называйте синтетику реальными данными.** Единственная разрешённая формула: «real 2025
   EIA-930 demand shape; synthetic site geometry and interconnection timelines, documented».
5. `GridCare raised $60,000,000` — со слуха, компания не проверена. Не произносите имя, пока не
   подтвердите; цифру можно опустить совсем.

---

## Appendix — дословный фрагмент со сцены (главный, для слайда и для Q&A)

Сохраните этот блок как есть: его нельзя пересказывать своими словами.

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

Арифметика, которую стоит знать: 98% доступности = 175 часов в год ≈ 7,3 дня. «Две недели в
году» = 336 часов ≈ 96,2%. То есть 98% — **более жёсткое** обещание, чем пример инженера.
Говорите: «his 98 percent is the tighter promise — we took that one».

---

## Что ещё звучало со сцены (можно цитировать, не на слайд)

| Мысль | Дословно | Зачем нам |
|---|---|---|
| Распределённая сеть уже загружена | «We have many areas where the distribution is actually already being fully consumed» (Arham, 15 545, ≈27%) | объясняет «skipped» сайты |
| Utility уже раздала мощность | «we, at the utility, have already built out a bunch of physical infrastructure, and a lot of the demand, or the load, has already been taken up» (PG&E, 26 410, ≈46%) | то же |
| Очередь годами, а склады — за дни | «some sites have been in the interconnection queue for a year, versus some have been approved in days» (Arham, 18 312, ≈32%) | почему 0.5–10 MW |
| Уже делают на distribution для Tesla | «we actually do this on the distribution side … for Tesla, like for superchargers … small footprints» (PG&E, 28 876, ≈51%) | снимает «так не бывает» |
| Простой предсказуемый vs случайный | «if they know that I might lose energy for like 10 minutes a day … just have a massive battery that's ready for it. But if you have 10 minutes per day versus 2 hours, on a random day, then the batch is not ready for it» (Arham, 24 213, ≈42.5%) | обоснование SLA-бюджета |
| Критерии судей | «the technical aspect, a … loop … energy system, innovation simulation … a technical demo … and the learning capabilities of your agents as well» (организатор, 56 413, ≈99%) | ровно то, что мы показываем |
| Приз | «a single price, a $300 Amazon gift card» (организатор, 55 201, ≈97%) | контекст |
