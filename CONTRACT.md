# GRIDRUSH — contract (freeze #1, 2026-11-08)

> **GRIDRUSH** — a speed-to-power agent. The agent decides which compute loads to connect and with what
> firm/flexible capacity, in order to get the maximum MW·months of compute over 36 months with
> zero grid-limit violations and with the availability SLA met.

Hackathon: SF x MIT Hack Day: Energy (AGI House SF, 2026-11-08). Submission 17:00 PT, demo 18:30 PT.
Theme: grid-friendly compute. Tracks: 1 (sites), 2 (grid capacity), 3 (load management).
Contract owner: Lead. Change only through the Lead.

---

## 1. What exactly we simulate (and what we honestly label as synthetic)

**Real:** hourly load, forecast and generation by fuel for 2025 for 12 US BA
(`data/us_grid_hourly_2025.csv`, EIA-930, public domain). From it we take the annual load shape and the
solar generation shape for a region (CAISO / ERCOT / PJM / MISO).

**Synthetic, but parameterised from facts in the repo and the speech (mandatory in the assumptions table):**

| Parameter | Value | Where from |
|---|---|---|
| Grid | 8 substations × 5 candidate sites = 40 sites, 0.5–10 MW | hackathon scenario (0.5–10 MW) |
| Substation capacity `cap_mw` | 8–60 MW | synthetic |
| Existing substation load | `e[h] = lf * cap * u[h]`, `lf ∈ [0.6, 1.0]`, `u[h]=d[h]/p95(d)` | "many distribution areas are already fully loaded" (Arham, speech) |
| Firm interconnection wait | 18–36 months (by queue position) | MISO: requests seek connection in 18 to 36 months |
| Flex / step-up (non-firm) wait | 5–10 months | MISO Firm Service Step Up, ERCOT batch studies |
| Onsite battery | 4–7 months | synthetic |
| Cost of the interconnection option | firm: $0; flex: $0 + curtailment; battery: $0.35M/MW + $0.25M/MWh | synthetic, order of magnitude from the market |
| Compute margin | $0.10M per MW·month ($1.2M/MW·yr) | "$5M per MW over 3–4 years" (Arham, speech) |
| SLA | **the agent's choice, with a price**: 99.99% = 0.876 h/yr (revenue multiplier ×1.25), 99.9% = 8.76 h/yr (×1.0), 99.0% = 87.6 h/yr (×0.80) | the audience question about 98% and PG&E + "you get a premium for six nines", speech |
| Grid calibration | a real 20 kV MV feeder: measured headroom 2.9–5.1 MW/bus (pandapower mv_oberrhein) | AC power-flow spike (sim/POWERFLOW.md) |
| SLA penalty | 5× the margin per MW·h of curtailment over the budget | synthetic |

**No external APIs.** Everything is local; the demo must run without a network.

## 2. Model (deterministic, numpy, fast)

Hours: `h = 0..8759` (the year 2025 is replayed in each of the 36 months of the horizon: month `m`
uses the hours `hours_of_month(m)` of the same representative year).

For region `R`: `u[h] = demand_mw[h] / percentile(demand_mw, 95)`.

Substation `S`: `cap_mw[S]`, `lf[S]`.
Site `i` at substation `S(i)`: `max_mw[i] ∈ [0.5, 10]`.

```
e[S,h]    = lf[S] * cap_mw[S] * u[h]        # existing load of the substation
H[i,h]    = cap_mw[S(i)] - e[S(i),h] - 0.02*cap_mw[S(i)]   # free headroom of site i
Hmax[i]   = max_h H[i,h]
T_firm[i], T_flex[i], T_on[i]              # months to energize (own for each site)
```

**Site modes (the agent's decision):**
- `skip` — do not connect.
- `firm`: `mw_firm[i] = min(0.5..min(Hmax[i], max_mw[i]), floor_alloc)`; energize at `T_firm`.
  Constraint: `Σ_{i∈S, mode=firm} mw_firm[i] <= min_h H[i,h]` — the substation-wide limit.
- `flex`: `mw[i] ∈ [0.5, min(Hmax[i], max_mw[i])]`, energize at `T_flex`; the site's SLA sets the allowed number of
  curtailment hours per year (0.876 / 8.76 / 87.6) and the revenue multiplier (1.25 / 1.0 / 0.8); in hour `h` the site must
  reduce load to `max(0, H[i,h] - occupied_by_others)`; curtailment is allowed only in hours where
  `e[S,h] + Σ_mw > cap_mw[S] - margin`. Number of curtailment hours per year `k(i)`.
- `flex+battery`: the same + a battery `B_mwh[i]`, `P_bat >= mw[i]`; in curtailment hours the battery
  covers the deficit until `B_mwh[i]` is exhausted (per year), the remainder is curtailment.
- `onsite` (optional, if we have time): flex+battery+gas, gas in stress hours at $/MWh.

**Verification (verifier), independent of the policy:** for every hour and substation
`violation_mwh += max(0, e[S,h] + Σ_i load_i[h] - cap_mw[S] + margin)`, where `load_i[h]` accounts for
firm/flex/battery. Must be 0.

**Availability:** `avail[i] = 1 - curtailed_hours[i]/8760`; requirement `avail[i] >= sla[i]`,
`sla[i] ∈ {0.999, 0.99}`. A violation incurs a penalty (see §1).

**Metrics (in this order of importance):**
1. `ratio_delivered = delivered_mwmonths / baseline_mwmonths` — the main headline
2. `delivered_mwmonths` = Σ_i mw[i] * max(0, 36 - T[i]) * avail[i]
3. `mw_at_month12` — how much MW is actually running by month 12 (second headline)
   + `compliant_mwmonths` — sellable compute only (SLA met)
4. `net_value_musd` = 0.10 * rev_weighted_mwmonths − capex − sla_penalty, where
   `rev_weighted = Σ mw·months·avail·mult(sla)`
5. `violations_mwh` = 0 (hard)
6. `iterations` — log of the best score per iteration (for the "the agent learns" chart)

**score for the loop:** `score = net_value_musd - 10 * violations_mwh - 5 * sla_penalty_musd`

## 3. File ownership (do not overlap!)

| Path | Owner | What |
|---|---|---|
| `gridrush/data/` | Lead | CSV + `sites.json` (sim generates it by seed) |
| `gridrush/sim/**` | **sim-engineer** | engine, evaluator, baselines, tests, `results/sim_baseline.json` |
| `gridrush/loop/**` | **Lead** | search/evolution, CLI, `results/loop.json` |
| `gridrush/web/**` | **dashboard-builder** | `dashboard.html` (single-file, offline) + `web/build.py` |
| `gridrush/pitch/**` | **pitch-writer** | pitch.md, demo-script.md, submission.md, qa-defense.md |
| `gridrush/rsi_agent/**` | **Lead** (via subagent) | LLM-in-the-loop policies + `rsi_log.json` |
| `gridrush/CONTRACT.md`, `README.md` | Lead | |

**Rule:** do not edit other people's files. Need a contract change — message the Lead.

## 4. Simulator API (frozen; sim-engineer implements exactly this)

File `sim/engine.py`, Python 3.9, only `numpy`/`pandas` (no external installs, no network).

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
# each: (region, sites) -> portfolio list[dict]
```

Requirements: `evaluate` < 100 ms for 40 sites; deterministic; no prints; `sim/run.py` writes
`results/sim_baseline.json` (see §5) for all 4 regions.

## 5. `results/*.json` format (frozen; the dashboard reads it)

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

**The dashboard must be able to:** (1) animate `iterations` (score curve + counters), (2) a stacked
bar `monthly_mw` by mode, (3) a map of 8 substations × 5 sites coloured by mode, (4) a stress-day
chart (demand vs headroom vs curtailment), (5) KPI cards `comparison`, (6) an assumptions table.
Style: dark, clean, large numbers, no CDN/internet, a single `.html`.

## 6. What must be ready by 16:40 PT (hard stop)

1. `python3 sim/run.py` → `results/sim_baseline.json` with 4 regions and 3 baseline policies ✅
2. `python3 loop/run.py` → `results/loop.json` with ≥150 iterations and the best policy ✅
3. `web/dashboard.html` opens locally from `results/loop.json`, everything animates ✅
4. `pitch/submission.md` + `pitch/demo-script.md` (3 min, verbatim) ✅
5. `README.md` with the assumptions table and sources ✅

## 7. Honesty (more important than beauty)

- Never call synthetic data real. Everywhere: "real 2025 EIA-930 shape; synthetic site
  geometry and interconnection timelines, parameters documented".
- Every number in the pitch has a source: either a `catalog` id from the repo, or the speech transcript, or
  `sim/assumptions.md`.
- The baseline must be honest (not a strawman): 3 different baselines, all visible in the JSON.
