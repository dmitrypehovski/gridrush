# LinkedIn post — GRIDRUSH (SF × MIT Hack Day: Energy, 8 Nov 2026)

> Primary version, ready to paste. Attach one image: the stage dashboard screenshot
> (`web/qa_final_1.png`) or the 3D view (`/gridrush/viz.html`). Links at the bottom.

---

Connecting a data centre to the grid takes 7–10 years. Building one takes 2–3.

That gap was the whole point of SF × MIT Hack Day: Energy at AGI House this weekend, where the
theme was "grid-friendly compute". A PG&E engineer said it plainly on stage: seven to ten years to
interconnect. Someone in the room asked the obvious question — what if a load only needs 98%
availability and curtails on a few hot days? The answer was: "we're trying."

So I answered it with a number instead of an opinion.

GRIDRUSH is an agent that plans speed to power. For 40 candidate edge sites on 8 substations it
decides, per site: connect or refuse, firm or flexible, how many MW, and which availability tier to
buy (99.99% with a revenue premium, 99.9%, or 99% with a bigger curtailment budget). A deterministic
verifier replays all 8,760 hours of 2025 and scores every plan; the agent keeps what wins.

What it produced:

→ 85.4 MW online by month 12 — versus 0 MW for "sign everything firm and wait for the queue"
→ 4.30× the net value of the best honest baseline (3.82× in physical units: 2,490.6 vs 651.3
  sellable megawatt-months)
→ 32 of 40 sites connected, 8 refused — saying no is part of the result
→ The "just sign everything non-firm at max" strategy looks fast (173 MW) and loses $449.5M to SLA
  penalties. Speed without reliability is not a business.

The part I'm proudest of is the learning loop, because it actually learned: 207 iterations, with the
fast search plateauing at 179 — and then an LLM-written policy jumping to 280. One generation failed
completely (empty portfolio, score 115) and it's still in the log.

And the part I'm most careful about: honesty. I added real AC power flow (pandapower, a real 20 kV
feeder) and the number honestly drops to 2.39× — a 44% haircut. I rebuilt the model on real PG&E
substations (public GRIP portal) and it drops to 1.22×, which locates the real constraint at the
circuit level, not the substation. The site geometry and economics are synthetic and documented as
such. The ratio is invariant to the price level; the physical ratio has no prices in it at all.

Three things I'm taking away:
1. The interesting agent problems are not "can it write code" but "can you build a verifier good
   enough that the agent's improvement means something".
2. Real physics is the fastest way to find out your model is flattering you.
3. One day is enough to build something honest if you decide upfront what you will not claim.

Thank you to AGI House SF, Sundai Club, RSIhouse.ai, Autolab, Superradiant, Stanford Energy Club and
the judges for a genuinely well-run day.

Project (offline, no keys — dashboards, deck, 3D view, every iteration):
https://dmitrypehovski.github.io/gridrush/
Code: https://github.com/dmitrypehovski/gridrush

#EnergyAI #GridComputing #AIagents #RecursiveSelfImprovement #DataCenters #EnergyTransition #Hackathon

---

## Shorter variant (if you prefer ~600 characters)

Connecting a data centre to the grid takes 7–10 years; building one takes 2–3. At SF × MIT Hack Day:
Energy we built GRIDRUSH — an agent that decides which edge compute to connect, at what MW, and under
which availability tier (99.99% / 99.9% / 99%), verified over all 8,760 hours of 2025.

Result: 85.4 MW online by month 12 vs 0 for "all firm", 4.30× the net value of the best honest
baseline, 32 of 40 sites connected. With real AC power flow inside the loop it honestly drops to
2.39× — that gap is the value of real utility data.

207 iterations, plateau at 179, then an LLM-written policy jumped to 280.
Project: https://dmitrypehovski.github.io/gridrush/

#EnergyAI #AIagents #Hackathon

---

## Russian variant (для смешанной аудитории)

Подключение дата-центра к сети занимает 7–10 лет. Строительство — 2–3 года.

На хакатоне SF × MIT Hack Day: Energy в AGI House мы построили GRIDRUSH — агента, который решает,
какие вычислительные площадки подключить, на сколько МВт и с каким SLA (99.99% / 99.9% / 99%),
проверяя план по всем 8 760 часам 2025 года.

Результат: 85,4 МВт работают к 12-му месяцу против 0 у стратегии «всё firm и в очередь»; 4,30×
ценности относительно лучшей честной стратегии; подключено 32 площадки из 40. Когда мы встроили в
оптимизацию реальный AC power flow, результат честно упал до 2,39× — эта разница и есть ценность
реальных данных сетевых компаний.

207 итераций: быстрый поиск упирается в 179, затем LLM переписывает политику и прыгает до 280.

Проект: https://dmitrypehovski.github.io/gridrush/
Код: https://github.com/dmitrypehovski/gridrush

#EnergyAI #AIagents #Hackathon
