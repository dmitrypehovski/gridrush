# GRIDRUSH — submission text

> Paste sections 1–9 in order. **No placeholders left** — numbers frozen in
> `results/FINAL_NUMBERS.md`. Prose is ~350 words, headings excluded; if the form has a hard
> 300-word cap, cut the two parentheticals in §7 first, they are the least load-bearing.

## 1. Title

**GRIDRUSH — a speed-to-power agent for grid-friendly compute**

## 2. One-liner

GRIDRUSH decides which compute loads to connect, how big, and how flexible, to maximise
megawatt-months over 36 months with zero modelled grid violations and every site inside its SLA.

## 3. Track

**1 + 2 + 3** — sites, grid capacity at the edge, load management.

## 4. Problem

A data centre connection takes 7 to 10 years — a PG&E engineer said so on stage today. ERCOT holds
about 410 GW of large-load requests, 87% data centres, against 7,502 MW approved to energise since
2022 (`ercot-legislative-update-2026`, `ercot-constraints-2025`). He then asked: what if a load needs
guaranteed capacity only 98% of the time and curtails on a few hot days? He said that would
"drastically improve the chances and the speed" of connecting.

## 5. What the agent does

Over 8 substations × 5 sites (0.5–10 MW each, below ERCOT's 25 MW large-load rules) it chooses per
site: skip, firm, flexible, or flexible + battery. A deterministic verifier replays all 8,760 hours
of 2025 for capacity violations and SLA breaches; the best portfolios enter an archive and the next
proposal starts from there. An evaluation runs in under 100 ms. The loop ran 207 iterations: 200
from a parametric mutator, then 7 generations where an LLM proposer rewrote the policy itself.

## 6. Real vs synthetic

**Real:** hourly 2025 demand and load shape for 12 US balancing authorities (EIA-930, public domain).
**Synthetic and documented:** site geometry, substation capacity, timelines, costs — labelled on
screen, never called real.

We also rebuilt the site model on the public PG&E GRIP Data Portal (8 real substations, real
coordinates, facility ratings and 2026 loadings — `sim/real_sites.py`); the flexibility premium drops
to 1.22× at substation aggregate level, which locates the real constraint at the circuit level
(PG&E GNA: 124 of 2,000 sampled circuits already deficient for 2026).

## 7. Result

Against the two strategies operators use today — all firm (0 MW at month 12; $65.1M of modelled
margin over 36 months) and all non-firm (172.6 MW at month 12, but −$449.5M after 1.15M MWh of SLA
breach) — GRIDRUSH delivers **85.4 MW at month 12, +$279.9M of margin, 4.30× the net value, 3.82×
more compliant megawatt-months (651 → 2491), zero modelled violations, zero SLA breach**. It
connects 32 of 40 sites and refuses the other 8. At the evening peak the naive portfolio must shed
28.4 MW; GRIDRUSH sheds at most 1.0 MW. Same policy on CAISO/ERCOT/PJM/MISO: **4.30× / 3.41× /
4.07× / 3.88×** — 3.4–4.3×, zero violations, no tuning (`web/regions.html`).

## 8. How it expands

Real feeders (PG&E GRIP, SCE ICA) instead of synthetic ones; real physics — AC power flow
(`pandapower`) on a real 20 kV feeder already shows 8.2 MW of spare capacity for our load class with
zero violations, against 32 MW for our five largest sites. We already feed that limit back into the
loop: with measured physics inside the optimizer the same agent reaches **2.39× (net $155.5M, 1313
sellable MW·months, all 8 substations AC-PF clean) instead of 4.30×** — the delta is exactly the data
we ask for. Next: real feeder data per substation, and real signal (OpenADR, prices, carbon).

## 9. Repository

Repository: attached as `gridrush.zip` (offline; no keys; every baseline, every region, every
iteration in `results/loop.json`).
