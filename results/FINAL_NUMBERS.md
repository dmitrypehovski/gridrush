# GRIDRUSH — FINAL NUMBERS (frozen 2026-11-08 ~13:00 PT)

Источник: `results/loop.json` (region = CAL / CAISO), движок `sim/engine.py` заморожен
sim-engineer'ом (детерминизм проверен, `sim/test_engine.py` 26/26 ok).

## Главная таблица (для слайда и сабмита)

| Стратегия | MW online к 12-му месяцу | Contract-compliant MW·месяцы | Net value |
|---|---|---|---|
| All **firm**, wait for the queue (`queue_order`) | **0** | 651.3 | **$65.1M** |
| Sign **everything non-firm** at max MW (`max_mw_no_flex`) | 172.6 | 1447.9 (из 3384 gross) | **−$449.5M** |
| **GRIDRUSH agent** (`gen_6`, LLM-written policy) | **85.4** | **2490.6** | **+$279.9M** |

Ratios: **4.30×** net value, **3.82×** contract-compliant MW·months, **85.4 MW vs 0 MW** к 12-му
месяцу. Нарушения сети: **0.000 MWh**. SLA breach: **0.000 MWh** (у каждого сайта свой SLA
соблюдён). Подключено **32 сайта из 40** (агент отказался от 8).

## Петля обучения

`iterations` = **207** точек: 200 итераций параметрического мутатора + 7 поколений LLM-пропозера
(`rsi_agent/gen_0..gen_6`, лог `rsi_agent/rsi_log.json`). Кривая best-so-far: **108.4 → 279.9**.

Ключевой момент истории: параметрический поиск упирается в плато **~178.6**; LLM-агент переписывает
политику (точный DP по подстанциям, flex-only) и прыгает **178.6 → 269.6 → 279.9** (+57%).

## Портфель агента

- 32 сайта, все `flex`, суммарно **~104 MW** (из 208.5 MW nameplate по 40 сайтам)
- SLA-микс: **16 сайтов 99.99%** (премия ×1.25), **6 сайтов 99.9%** (×1.00), **10 сайтов 99%** (×0.80)
- батареи не используются (в модели доминируются flex@99.99% и создают риск нарушений)
- energize: месяцы 5–12 (firm-очередь 18–36 месяцев)

## Stress day (for worst-day chart)

- `grid.stress_day.date` = **2025-08-21** (CAISO), peak **43,860 MW at 20:00 local**
- required curtailment в 20:00: **agent ≈ 1.9 MW**, **naive-портфель ≈ 28 MW**
  (точные ряды: `grid.stress_day.curtail_mw`, `curtail_mw_naive`)

## Data facts (can cite)

- 12 US balancing authorities, 3,513 TWh, hourly 2025, EIA-930 public domain
- CAISO duck curve worst day 2025-03-08: net load −1,140 MW at 13:00 → +22,682 MW за 6 часов
- flex-worthy hours (top-1% demand OR top-1% ramp): 2.0% года, 160–177 часов на оператора
- ERCOT: 410 GW large-load requests (87% data centers) vs 7.5 GW approved since 2022
- 1 MW за 3–4 года = $5M (со сцены); подключение 7–10 лет (PG&E, со сцены)

## Четыре региона, одна и та же политика (без тюнинга)

| регион | ratio net | ratio MW·мес | net $M | compliant MW·мес | MW@12 | violations |
|---|---|---|---|---|---|---|
| CAL (CAISO) | **4.30×** | 3.82× | 279.91 | 2490.6 | 85.4 | 0 |
| TEX (ERCOT) | 3.41× | 2.79× | 304.46 | 2491.7 | 84.1 | 0 |
| MIDA (PJM) | 4.07× | 3.57× | 275.30 | 2415.7 | 82.4 | 0 |
| MIDW (MISO) | 3.88× | 3.33× | 277.84 | 2390.4 | 81.3 | 0 |

Источник: `results/loop_{CAL,TEX,MIDA,MIDW}.json` (та же `rsi_agent/gen_6.py`, `--iters 60 --seeds 1`).
Формулировка для судей: «the same policy, four operators, 3.4–4.3× and zero violations — no per-region
tuning».

## Physics-in-the-loop (закрывает «AC power flow вне петли»)

Реальный AC power flow (`pandapower`, `mv_oberrhein`, настоящий 20 кВ фидер) измеряет
**допустимую добавку нагрузки на подстанцию: 6.53 МВт** (первое нарушение на 7.03 МВт;
при лимите min V 0.95785 p.u., загрузка 100.0%). Этот лимит встроен в петлю как admission
constraint: поиск обязан раскладывать compute по подстанциям, а финальный план проверяется
8 реальными AC-PF прогонами.

| вариант | net value | ratio | compliant MW·мес | MW@12 | AC-PF |
|---|---|---|---|---|---|
| профильная модель (ICA-style headroom) | **$279.9M** | **4.30×** | 2490.6 | 85.4 | не проверялся |
| **physics-in-the-loop** | **$155.5M** | **2.39×** | 1313 | 44.7 | **8/8 подстанций clean** |

Дельта **−44.5% net value**: настоящий фидер берёт ~6.5 МВт новой нагрузки, а не 20–60 МВт,
которые допускали синтетические ёмкости. Это и есть цена реальной физики — и ценность реальных
ICA-данных утилиты. Команды: `<venv>/python sim/physics_gate.py` (лимит), затем
`<venv>/python loop/run_physics.py --warm-start results/loop.json --budget 2500` (оптимизация),
`python3 web/build.py results/loop_physics.json -o web/dashboard_physics.html`.

## Реальные данные PG&E вместо синтетических ёмкостей

`sim/real_sites.py` тянет публичный PG&E GRIP Data Portal (ArcGIS REST, без ключа):
8 реальных подстанций PG&E — реальные имена, координаты, суммарный facility rating и
**загрузка 2026** (слой DFCircuitsView), отсортированы по реальному запасу:

| подстанция | дивизион | rating | load 2026 | lf |
|---|---|---|---|---|
| SAN RAMON | Mission | 302.2 MW | 136.9 MW | 0.453 |
| CLAYTON | Diablo | 193.1 | 124.9 | 0.647 |
| CAMP EVERS | Central Coast | 100.4 | 38.5 | 0.383 |
| TASSAJARA | Diablo | 184.2 | 130.2 | 0.707 |
| STOCKDALE | Kern | 327.1 | 275.2 | 0.841 |
| WOODWARD | Fresno | 174.6 | 124.5 | 0.713 |
| FIGARDEN | Fresno | 225.4 | 180.2 | 0.799 |
| COTTLE | Yosemite | 112.9 | 70.5 | 0.624 |

Запуск: `python3 sim/real_sites.py` → `GRIDRUSH_SITES=real python3 loop/run.py --region CAL ...`
→ `results/loop_real.json` → `web/dashboard_real.html`.

**Результат: 1.22×, 397.7 MW@12, 11 533 MW·мес, 0 нарушений, все 40 сайтов.**
Честный вывод: на **агрегатном уровне подстанции** реальные PG&E-подстанции крупные и не являются
узким местом — премия за гибкость почти исчезает. Ограничение живёт на уровне фидера: в выборке
2 000 цепей PG&E GNA **124 цепи (6.2%) уже дефицитны на 2026** (до 12.4 МВт). Это ровно тот
следующий шаг, который заявлен в ask.

## RSI: второй раунд (закрывает «один прогон за день»)

Архив сохраняется, поэтому петлю можно продолжить: раунд 2 стартовал с `gen_6` (279.9082) и
записал `gen_7 … gen_10`. Лучший — **gen_9 = 280.256 (+0.12%)**: политика сошлась, и это честный
результат (в per-substation exact DP для flex-only улучшать нечего). `gen_10` ухудшился (−1.4) и
был отвергнут правилом keep-best. Логи: `rsi_agent/rsi_log.json`, `rsi_agent/rsi_log2.json`,
`rsi_agent/BEST2.md`. Headline остаётся на `gen_6`; раунд 2 — доказательство возобновляемости.

## Регионы как first-class

`web/regions.html` — одна страница со всеми четырьмя операторами (CAL 4.30× · TEX 3.41× ·
MIDA 4.07× · MIDW 3.88×, violations 0 везде) + карточка physics-in-the-loop со ссылками на
`dashboard_<REGION>.html`. Сборка: `python3 web/build_regions.py`.

## Что НЕ говорить

- «real data» без «synthetic site geometry»; «zero violations» без «in the model»;
  «we made $279.9M» (это modelled compute margin за 36 месяцев на синтетическом портфеле);
  любые solar-цифры из этого CSV (колонка нефизическая, не используется в расчётах).
