# GRIDRUSH — submission (short version, ~300 words)

> Use this if the form enforces a 300–400 word limit. The full text (with the physics-in-the-loop
> and PG&E real-data paragraphs) is in `submission.md`; both are true, this one just moves the
> extras into Q&A (Q6, Q15, Q16 in `qa-defense.md`).

## 1. Title

**GRIDRUSH — a speed-to-power agent for grid-friendly compute**

## 2. Track

1 + 2 + 3 — sites, grid capacity at the edge, load management.

## 3. Problem

Connecting a data centre takes 7–10 years (PG&E, on stage today), while ERCOT holds ~410 GW of
large-load requests — about 87% data centres — against 7.5 GW approved to energise since 2022.
The room then asked the utility: what if a load needs guaranteed capacity only ~98% of the time
and curtails on a few hot days? The answer was: *we're trying*. GRIDRUSH answers with a number.

## 4. What the agent does

Over 8 substations × 5 candidate sites (0.5–10 MW), the agent decides per site: skip, firm,
flexible, or flexible + battery — and which availability tier to buy (99.99% / 99.9% / 99%, each
with its own revenue premium). A deterministic verifier replays all 8,760 hours of 2025 and counts
capacity violations and SLA breaches; the best plans enter an archive and the next proposal starts
there. The loop is real: 200 generations of a parametric proposer, then seven where an LLM proposer
rewrote the policy itself, plus a self-repair pass that shrinks MW until every site's SLA holds.

## 5. Result

Against the two strategies operators use today — all firm (0 MW at month 12, $65.1M of modelled
margin) and all non-firm at max MW (172.6 MW, but −$449.5M after 1.15M MWh of SLA breach) —
GRIDRUSH delivers **85.4 MW at month 12, +$279.9M, 4.30× the net value, 3.82× more sellable
megawatt-months (651 → 2491), zero modelled violations, zero SLA breach**. It energises 32 of 40
sites and refuses the other 8. The same policy, with no per-region tuning, gives 3.4–4.3× on
CAISO, ERCOT, PJM and MISO 2025 data (`web/regions.html`).

## 6. Real vs synthetic

**Real:** hourly 2025 demand for 12 US balancing authorities (EIA-930, public domain); site model
optionally rebuilt on the public PG&E GRIP Data Portal (8 real substations, real coordinates,
facility ratings and 2026 loadings). **Synthetic and documented:** which sites sit inside a
substation, connection timelines and costs.

## 7. How it expands

Real feeders (PG&E GRIP line sections); real physics inside the loop — measured AC power flow gives
6.53 MW of new load per MV feeder, and feeding that back into the optimiser gives 2.39× instead of
4.30×; real grid signals (OpenADR, prices, carbon). Circuit-level ICA is the first data we ask for.

## 8. Repository

Attached as `gridrush.zip` — offline, no keys; every baseline, every region and every iteration in
`results/loop.json`.
