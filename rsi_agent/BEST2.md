# RSI round 2 — continual improvement from the archive

**Start:** `gen_6.py` (round-1 best: score **279.9082**, net $279.9M, 2490.6 compliant MW·months).
**Method:** the archive persists; the proposer resumes from `gen_6` and wrote six more generations,
each scored by the same all-8,760-hour verifier. No changes to `sim/`, `loop/`, `results/`.

| gen | score | net $M | MW @12 | compliant MW·mo | kept | what it tried |
|---|---|---|---|---|---|---|
| 7 | 279.9082 | 279.91 | 85.39 | 2490.6 | no | reference: exact copy of gen_6 (round-1 best) |
| 8 | 280.2268 | 280.23 | 85.51 | 2493.6 | no | DP over the ACHIEVABLE prefix set per substation (<=600 states), repair replaced by an exact replica of the engine's float ops + shave loop |
| 9 | 280.2560 | 280.26 | 85.51 | 2493.8 | yes | same as gen_8 with EPS=1e-5 and MW kept to 6 decimals — fixes the 0.01 MW flooring loss |
| 10 | 278.5042 | 278.50 | 85.03 | 2479.9 | no | pairwise MW transfer between sites on the same substation — regressed |
| 11 | -5428.8665 | 110.54 | 9.33 | 686.0 | no | tried mixing firm sites back in — 553 MWh of violations, rejected |
| 12 | 280.2560 | 280.26 | 85.51 | 2493.8 | yes | consolidation of the gen_9 logic (re-implementation check) |

**Result: 280.2560 = +0.124% over round 1** (gen_9).
Invariants hold: `violations = 0`, `sla_breach = 0`, `compliant == delivered` (2493.85), 32 sites,
all flex, SLA mix 16 / 6 / 10.

**Why this is a plateau, not a wall.** The DP over the *achievable* prefix set per substation is an
exact optimisation of the admissible flex-only space. Firm is dominated: 18–36 months versus 5–10,
and forcing 28 firm sites breaks `min(H)` → 553 MWh of violations. Batteries are negative on all 32
candidate sites (`T_on = T_flex + 1..3` plus $0.35M/MW + $0.25M/MWh capex, no availability gain).
So 280.256 is the optimum of this model.

**What actually changed vs round 1:** `gen_6` solved the right problem on an incomplete candidate
lattice — it lost chains that stop a site exactly on a SLA-tier breakpoint and push the remainder to
a neighbour; and its `floor(x*100)/100` + offset plus a second `floor` inside `repair_portfolio` cost
0.37 $M, more than any structural idea. `gen_8` carries the achievable prefix set through the DP and
replaces `repair_portfolio` with an exact replica of the engine's float operations.

**One generation regressed and was rejected** (`gen_10`: −1.4; `gen_11`: violations) — the
keep-best rule works, and the log keeps the failures on purpose.

Shipped headline policy remains `gen_6`; `gen_9` is kept as round-2 evidence.
