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

## Что НЕ говорить

- «real data» без «synthetic site geometry»; «zero violations» без «in the model»;
  «we made $279.9M» (это modelled compute margin за 36 месяцев на синтетическом портфеле);
  любые solar-цифры из этого CSV (колонка нефизическая, не используется в расчётах).
