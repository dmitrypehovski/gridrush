# GRIDRUSH — submission text

> Paste sections 1–9 in order. Numbers are final from `results/loop.json`. One placeholder left:
> `{{REPO_URL}}`. Prose is ~350 words, headings excluded — if the form has a hard 300-word cap,
> cut the two parentheticals in §7 first, they are the least load-bearing.

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
2022 (`ercot-legislative-2026`, `ercot-constraints-2025`). He then asked: what if a load needs
guaranteed capacity only 98% of the time and curtails on a few hot days? He said that would
"drastically improve the chances and the speed" of connecting.

## 5. What the agent does

Over 8 substations × 5 sites (0.5–10 MW each, below ERCOT's 25 MW large-load rules) it chooses per
site: skip, firm, flexible, or flexible + battery. A deterministic verifier replays all 8,760 hours
of 2025 for capacity violations and SLA breaches; the best portfolios enter an archive and
the next proposal starts from there. An evaluation runs in under 100 ms.

## 6. Real vs synthetic

**Real:** hourly 2025 demand and load shape for 12 US balancing authorities (EIA-930, public
domain). **Synthetic and documented:** site geometry, substation capacity, timelines, costs —
labelled on screen, never called real.

## 7. Result

Against the two strategies operators use today — all firm (0 MW at month 12; $65.1M of modelled
margin over 36 months) and all non-firm (173 MW at month 12, but −$205.4M after SLA penalties) —
GRIDRUSH delivers **69.8 MW at month 12, +$202.4M of margin, 3.15× more
compliant megawatt-months (651 → 2050), zero modelled violations**. It connects 19 of 40 sites. The
same loop, with no per-region tuning, gives **2.5–3.1× on CAISO, ERCOT, PJM and MISO 2025 data**;
PJM's 0.2 MWh is reported, not hidden.

## 8. How it expands

Real feeders (PG&E GRIP, SCE ICA) instead of synthetic ones; real physics (`pandapower` AC power
flow, N-1) instead of a headroom model, already validated on a real 20 kV feeder; real signal
(OpenADR, prices, carbon).

## 9. Repo

{{REPO_URL}} — offline, no keys; every baseline, every region and every iteration in
`results/loop.json`.
