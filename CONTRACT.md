# GRIDRUSH — контракт (фриз №1, 2026-11-08)

> **GRIDRUSH** — speed-to-power agent. Агент решает, какие вычислительные нагрузки и с какой
> firm/гибкой мощностью подключить, чтобы получить максимум MW·месяцев compute за 36 месяцев при
> нулевых нарушениях сетевых лимитов и соблюдении SLA по доступности.

Хакатон: SF x MIT Hack Day: Energy (AGI House SF, 08.11.2026). Сабмит 17:00 PT, демо 18:30 PT.
Тема: grid-friendly compute. Треки: 1 (sites), 2 (grid capacity), 3 (load management).
Владелец контракта: Lead. Менять только через Lead.

---

## 1. Что именно симулируем (и что честно помечаем как синтетику)

**Реальное:** почасовая нагрузка, прогноз, генерация по топливу за 2025 для 12 US BA
(`data/us_grid_hourly_2025.csv`, EIA-930, public domain). Из него берём форму годовой нагрузки и
солнечной генерации для региона (CAISO / ERCOT / PJM / MISO).

**Синтетическое, но параметризованное по фактам из репо и спича (обязательно в таблицу допущений):**

| Параметр | Значение | Откуда |
|---|---|---|
| Сеть | 8 подстанций × 5 кандидатных сайтов = 40 сайтов, 0.5–10 MW | сценарий хакатона (0.5–10 MW) |
| Ёмкость подстанции `cap_mw` | 8–60 MW | синтетика |
| Существующая нагрузка подстанции | `e[h] = lf * cap * u[h]`, `lf ∈ [0.6, 1.0]`, `u[h]=d[h]/p95(d)` | «многие районы распределения уже полностью загружены» (Архам, спич) |
| Ожидание firm-подключения | 18–36 мес (по позиции в очереди) | MISO: заявки ищут подключение за 18–36 мес |
| Ожидание flex / step-up (non-firm) | 5–10 мес | MISO Firm Service Step Up, ERCOT batch studies |
| Onsite battery | 4–7 мес | синтетика |
| Стоимость возможности подключения | firm: $0; flex: $0 + куртейлмент; battery: $0.35M/MW + $0.25M/MWh | синтетика, порядок величин по рынку |
| Маржинальность compute | $0.10M за MW·месяц ($1.2M/MW·год) | «$5M за MW на 3–4 года» (Архам, спич) |
| SLA | **выбор агента с ценой**: 99.99% = 0.876 ч/год (премия ×1.25), 99.9% = 8.76 ч/год (×1.0), 99.0% = 87.6 ч/год (×0.80) | вопрос зала про 98% и PG&E + «за 6 nines платят премию», спич |
| Сеть-калибровка | реальный 20 кВ MV-фидер: measured headroom 2.9–5.1 МВт/шину (pandapower mv_oberrhein) | AC power-flow спайк (sim/POWERFLOW.md) |
| Штраф SLA | 5× маржинальность за MW·ч куртейлмента сверх бюджета | синтетика |

**Никаких внешних API.** Всё локально, демо должно работать без сети.

## 2. Модель (детерминированная, numpy, быстрая)

Часы: `h = 0..8759` (год 2025 воспроизводится в каждом из 36 месяцев горизонта: месяц `m`
использует часы `hours_of_month(m)` того же representative-года).

Для региона `R`: `u[h] = demand_mw[h] / percentile(demand_mw, 95)`.

Подстанция `S`: `cap_mw[S]`, `lf[S]`.
Сайт `i` на подстанции `S(i)`: `max_mw[i] ∈ [0.5, 10]`.

```
e[S,h]    = lf[S] * cap_mw[S] * u[h]        # существующая нагрузка подстанции
H[i,h]    = cap_mw[S(i)] - e[S(i),h] - 0.02*cap_mw[S(i)]   # свободный headroom сайта i
Hmax[i]   = max_h H[i,h]
T_firm[i], T_flex[i], T_on[i]              # месяцы до energize (у каждого сайта свои)
```

**Режимы сайта (решение агента):**
- `skip` — не подключаем.
- `firm`: `mw_firm[i] = min(0.5..min(Hmax[i], max_mw[i]), floor_alloc)`; energize в `T_firm`.
  Ограничение: `Σ_{i∈S, mode=firm} mw_firm[i] <= min_h H[i,h]` — общий лимит подстанции.
- `flex`: `mw[i] ∈ [0.5, min(Hmax[i], max_mw[i])]`, energize в `T_flex`; SLA сайта задаёт допустимое число
  куртейлмент-часов в год (0.876 / 8.76 / 87.6) и множитель выручки (1.25 / 1.0 / 0.8); в часе `h` сайт обязан
  снизить нагрузку до `max(0, H[i,h] - занято_другими)`; куртейлмент разрешён только в часы, где
  `e[S,h] + Σ_mw > cap_mw[S] - margin`. Число куртейлмент-часов за год `k(i)`.
- `flex+battery`: то же + батарея `B_mwh[i]`, `P_bat >= mw[i]`; в куртейлмент-часы батарея
  закрывает дефицит до исчерпания `B_mwh[i]` (пер-год), остаток — куртейлмент.
- `onsite` (опционально, если успеем): flex+battery+газ, газ в стресс-часы по $/MWh.

**Проверка (verifier), независимая от политики:** для каждого часа и подстанции
`violation_mwh += max(0, e[S,h] + Σ_i load_i[h] - cap_mw[S] + margin)`, где `load_i[h]` учитывает
firm/flex/battery. Должно быть 0.

**Доступность:** `avail[i] = 1 - curtailed_hours[i]/8760`; требование `avail[i] >= sla[i]`,
`sla[i] ∈ {0.999, 0.99}`. Нарушение — штраф (см. §1).

**Метрики (в этом порядке важности):**
1. `ratio_delivered = delivered_mwmonths / baseline_mwmonths` — основной headline
2. `delivered_mwmonths` = Σ_i mw[i] * max(0, 36 - T[i]) * avail[i]
3. `mw_at_month12` — сколько MW реально работает к 12-му месяцу (второй headline)
   + `compliant_mwmonths` — только продаваемый compute (SLA соблюдён)
4. `net_value_musd` = 0.10 * rev_weighted_mwmonths − capex − sla_penalty, где
   `rev_weighted = Σ mw·months·avail·mult(sla)`
5. `violations_mwh` = 0 (жёстко)
6. `iterations` — лог лучшего score по итерациям (для графика «агент учится»)

**score для лупа:** `score = net_value_musd - 10 * violations_mwh - 5 * sla_penalty_musd`

## 3. Владение файлами (не пересекаться!)

| Путь | Владелец | Что |
|---|---|---|
| `gridrush/data/` | Lead | CSV + `sites.json` (генерирует sim по seed) |
| `gridrush/sim/**` | **sim-engineer** | движок, evaluator, baseline, тесты, `results/sim_baseline.json` |
| `gridrush/loop/**` | **Lead** | поиск/эволюция, CLI, `results/loop.json` |
| `gridrush/web/**` | **dashboard-builder** | `dashboard.html` (single-file, offline) + `web/build.py` |
| `gridrush/pitch/**` | **pitch-writer** | pitch.md, demo-script.md, submission.md, qa-defense.md |
| `gridrush/rsi_agent/**` | **Lead** (через subagent) | LLM-in-the-loop политики + `rsi_log.json` |
| `gridrush/CONTRACT.md`, `README.md` | Lead | |

**Правило:** не редактировать чужие файлы. Нужно изменение контракта — сообщение Lead.

## 4. API симулятора (заморожено; sim-engineer реализует ровно это)

Файл `sim/engine.py`, Python 3.9, только `numpy`/`pandas` (без внешних установок, без сети).

```python
# sim/data.py
load_region(region: str) -> dict          # {"region","hours","demand_mw","solar_mw","u", "stress_day": "2025-08-22", "month_hours": {1..12: np.array(idx)}}
make_sites(region: str, n_substations: int = 8, per_substation: int = 5, seed: int = 7) -> list[dict]
    # site: {"id","substation","cap_mw","lf","max_mw","T_firm","T_flex","T_on","fiber","permit_days","x","y"}

# sim/engine.py
evaluate(region: str, portfolio: list[dict]) -> dict
    # portfolio item: {"site_id","mode":"skip|firm|flex|battery","mw":float,"sla":0.999|0.99,"battery_mwh":float}
    # -> {"score","delivered_mwmonths","mw_at_month12","net_value_musd","violations_mwh",
    #      "sla_breach_mwh","capex_musd","avail_by_site":{...},"monthly_mw":[36 floats],
    #      "modes":{...}, "curtail_hours_by_site":{...}}
```

```python
# sim/baselines.py
BASELINES = {"all_firm_greedy": fn, "queue_order": fn, "max_mw_no_flex": fn}
# каждая: (region, sites) -> portfolio list[dict]
```

Требования: `evaluate` < 100 мс на 40 сайтов; детерминированно; без print; `sim/run.py` пишет
`results/sim_baseline.json` (см. §5) по всем 4 регионам.

## 5. Формат `results/*.json` (заморожено; его читает дашборд)

```json
{
  "meta": {"project":"GRIDRUSH","generated_at":"...","region":"CAL","horizon_months":36,
           "n_sites":40,"n_substations":8,"assumptions_version":1},
  "regions": [{"code":"CAL","name":"CAISO","peak_mw":43860,"peak_local":"2025-08-22 20:00"}],
  "sites": [{"id":"S03-2","substation":"S03","cap_mw":22.0,"max_mw":6.0,"x":-121.9,"y":37.7,
             "T_firm":27,"T_flex":7,"Hmax_mw":9.4,"stress_hours":412}],
  "grid": {"region":"CAL","demand_mw":[8760],"solar_mw":[8760],"u":[8760],
           "stress_day":{"date":"2025-08-22","local_hours":[1,2],"demand_mw":[],"solar_mw":[],
                         "cap_factor":[]}},
  "baselines": {"all_firm_greedy":{"label":"All firm, biggest headroom first",
      "delivered_mwmonths":0,"mw_at_month12":0,"net_value_musd":0,"violations_mwh":0,"ratio":1.0}},
  "iterations": [{"iter":0,"score":0.0,"delivered_mwmonths":0,"violations_mwh":0.0,"best":true}],
  "best": {"label":"GRIDRUSH agent","params":{},"delivered_mwmonths":0,"mw_at_month12":0,
      "net_value_musd":0,"violations_mwh":0,"sla_breach_mwh":0,"capex_musd":0,
      "monthly_mw":[36],
      "sites":[{"id":"S03-2","mode":"flex","mw":4.5,"sla":0.999,"battery_mwh":0,
                "energize_month":7,"curtail_hours":6.2,"avail":0.9993}]},
  "comparison": {"ratio_mwmonths":3.1,"ratio_mw12":8.0,"violations":"0 MWh","sla":"99.9%"},
  "run_log": ["iter 0 ...","iter 1 ..."]
}
```

**Дашборд обязан уметь:** (1) анимировать `iterations` (curve score + счётчики), (2) сложенный
bar `monthly_mw` по режимам, (3) карту 8 подстанций × 5 сайтов с цветом режима, (4) stress-day
chart (demand vs headroom vs curtailment), (5) KPI cards `comparison`, (6) таблицу допущений.
Стиль: тёмный, чистый, крупные числа, без CDN/интернета, один `.html`.

## 6. Что должно быть готово к 16:40 PT (жёсткий стоп)

1. `python3 sim/run.py` → `results/sim_baseline.json` с 4 регионами и 3 baseline-политиками ✅
2. `python3 loop/run.py` → `results/loop.json` c ≥150 итерациями и лучшей политикой ✅
3. `web/dashboard.html` открывается локально из `results/loop.json`, всё анимируется ✅
4. `pitch/submission.md` + `pitch/demo-script.md` (3 мин, дословно) ✅
5. `README.md` с таблицей допущений и источниками ✅

## 7. Честность (важнее красоты)

- Никогда не называть синтетику реальными данными. Везде: «real 2025 EIA-930 shape; synthetic site
  geometry and interconnection timelines, parameters documented».
- Любая цифра в питче имеет источник: либо `catalog` id из репо, либо транскрипт спича, либо
  `sim/assumptions.md`.
- Baseline должен быть добросовестным (не strawman): 3 разных baseline, в JSON видно все.
