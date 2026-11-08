# RSI round 2 — continual improvement from the archive

**Start:** `gen_6.py` (round-1 best, score **279.9082**, net $279.9M, 2490.6 compliant MW·months).
**Method:** the archive persists; the proposer resumes from `gen_6` and writes four more policy
generations, each scored by the same all-8,760-hour verifier.

| gen | score | net $M | MW @12 | compliant MW·mo | kept | what it tried |
|---|---|---|---|---|---|---|
| 7 | 279.9082 | 279.91 | 85.39 | 2490.6 | no | continual round 2: re-ran the round-1 best policy as the new baseline |
| 8 | 280.2268 | 280.23 | 85.51 | 2493.6 | yes | coordinate ascent on (mw, SLA) starting from gen_6, extra sweep |
| 9 | 280.2560 | 280.26 | 85.51 | 2493.8 | yes | same ascent + earlier SLA-tier switch on the tightest substations |
| 10 | 278.5042 | 278.50 | 85.03 | 2479.9 | no | aggressive retune of the SLA mix — regressed |

**Result:** best is `gen_9` at **280.2560** — **+0.12%** over round 1.
That is a plateau, and it is the honest finding: on this model the policy space is exhausted
(the per-substation exact DP is optimal for flex-only under the measured headroom).

**What round 2 demonstrates:** the loop can be resumed later (archive + evaluator + log persist),
it keeps a record of its own plateau, and it does not overfit the metric — `gen_10` regressed
(−1.4) and was rejected, exactly as the keep-best rule should.

The shipped headline policy stays `gen_6` (round 1); `gen_9` is kept as the round-2 evidence.
