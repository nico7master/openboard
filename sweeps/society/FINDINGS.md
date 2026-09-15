# Society in Motion — Findings (spec 2026-09-13-society-in-motion-study.md)

**51 runs, 650 ticks, 1000 citizens, seeds 7/42/123.** First study to measure (a)
two-lever interactions within seed (`AB − A − B + base`), (b) lever SEQUENCING
(same lever, different timing), and (c) full society timelines (wealth classes,
bread price, real wage, dividends per head, firm concentration, event logs —
snapshot at t=2, every 50 ticks).

Status: IN PROGRESS — pairs 1–2 complete and analyzed below; pair 3 and the
sequencing arms are appended when their cells land. Raw data:
`sweeps/society/<arm>_s<seed>.json`; numbers: `sweeps/society/ANALYSIS.json`.

---

## The baseline society (new — nobody had looked)

Every arm starts from the same founding: **124 coops founded at once**, bread at
price 300 (index 100), wages 800, wealth split top-1% 741bp / middle 9007bp /
bottom-20% 252bp, one coop holding 17% of firm money.

By tick 50 in EVERY world, bread collapses to **index ~12** (society massively
overproduces food) and real wages jump from 2 to 10–15. Over the run:

- **Equality improves on its own:** top-1% share falls 741→~320bp, bottom-20%
  rises 252→~930bp. The dividend engine (200/head/tick) plus equal start means
  capitalism-in-miniature does NOT re-concentrate — with one exception (pair 2,
  below).
- **Firms do not become leviathans:** the top coop's money share falls 174→~5bp.
- **But hunger is chronic and chaotic:** mid-run, 170–780 of 1000 citizens are in
  unmet need in waves, despite cheap bread, stable wages, and stable dividends.
  Hunger in this economy is a PRODUCTION-VOLATILITY problem, not a price or
  wealth problem. This is the single most important baseline fact for the game:
  a rich, equal, deflating economy still has hungry decades.

---

## Pair 1 — Spoilage(week-scale) × Disasters: NO trap, harms just add

**Verdict: ✅ No interaction.** The two rules we feared might kill together are
independent. Interaction effects across seeds: Gini +20/−12/+89bp, production
−1,258/+368/−511 (±0.5–1.7%), unmet −890/+66/−377 — all inside the chaos band.
Both safe-alone ⇒ safe-together.

| Cell (median of 3 seeds) | Gini | Produced | Unmet | Longest hungry streak |
|---|---|---|---|---|
| base | 2,590 | 73,516 | 371 | 50 |
| spoil_long | 2,582 | 73,773 | 508 | 114 |
| disaster | 2,598 | 73,419 | 616 | 74 |
| both | 2,593 | 73,284 | 357 | 78 |

### Society stories (seed 42 timelines)

- **Base world:** a golden age (t=50–150: zero hunger, real wage 10–13), then
  recurrent hunger eras (peaks of 779 at t=300, 671 at t=600) with full recovery
  between. Insolvencies tick along at 1–6/snapshot; nobody dies.
- **Adding week-scale rot:** the SAME golden age, then the SAME waves — rot's
  only distinct fingerprint is an early hunger window at t=50 (401 unmet vs 1 in
  base: the first harvests partially rot before the supply chain matures) and a
  slightly elevated floor of hunger later. Nothing compounds.
- **Adding disasters:** nearly identical to base (shock markers visible at
  t=450–600); the shocks are absorbed by the buffer stock.
- **Both:** startup rot window + slightly deeper late waves (759 at t=500).
  The society reads as "base world with a rougher adolescence" — not a death
  spiral in any seed.

---

## Pair 2 — Skills × Research(fixed): the first NEGATIVE interaction found

**Verdict: ⚠️ Sub-additive (crowding).** Research alone is the strongest
prosperity lever in the study (+8,934 production median, hunger ELIMINATED in
all seeds from t≈100). Skills alone are mildly costly (−2,006 production: trainees
don't work) and only modestly anti-hunger. TOGETHER: production lands
**2,296–6,434 BELOW the additive prediction in all 3 seeds** — the same direction
everywhere. Pull research into a trained society and you do NOT get both levers'
full values.

| Cell (median of 3 seeds) | Gini | Produced | Unmet | Pool end |
|---|---|---|---|---|
| base2 | 2,590 | 73,516 | 371 | 1.69B |
| skills_on | 2,727 | 71,510 | 239 | 1.67B |
| research_fixed | 2,618 | 82,450 | **0** | 0.66B |
| both | 3,116 | 77,360 | **0** | 0.65B |

Interaction per seed: produced −2,915/−2,296/−6,434; Gini −109/−484/**+702**
(s123); unmet 306/145/−93 (noise).

### Society story (seed 123, the strongest crowding case)

- **Research alone:** bread deflates hardest (index 9), real wage 13–17, hunger
  ZERO from t=100 to the end. The society buys its way out of famine with its
  pool (2.09B→0.69B — the reserve floor doing its job: it never collapses).
- **Skills added on top:** even cheaper bread (index 8), the best real wages of
  the study (15–19), still zero hunger — but total production is ~4.8k lower
  than research alone. Mechanism: skilled workers command +3%/level wages and
  spend hours training; once research already lifted productivity, those hours
  and premiums buy less marginal output (classic diminishing returns colliding).
- **The dark edge (s123):** the skills wage premium RE-CONCENTRATES wealth
  late-game — top-1% share climbs 341→494bp at t=500 while bottom-20% slide back
  686→679bp. In 2 of 3 seeds this washes out; in s123 it is a real
  inequality interaction (+702bp). WATCH: skills + research together is the one
  combination that lets a wage aristocracy re-emerge.

### Design reading

Research (fixed, floored) is the **anti-famine superweapon** — it alone ended
chronic hunger in every seed. Skills are a nice-to-have whose cost is hidden
until research is already on. If the game wants both, sequence matters less than
EXPECTATIONS: the combo is still the best society (zero hunger, highest real
wages, cheapest bread), it just delivers less than the sum of its parts.

---

## Pair 3 — Wealth tax(800bp) × Land dump: the tax SLEEPS in an equal society

**Verdict: ⚠️ Interaction exactly zero — because the tax never fired.** This is
not a bug: it is a real property of an equal society. Byte-identity proof:
`tax800 ≡ base3` and `tax_dump ≡ land_dump` in ALL THREE seeds (full 650-tick
trajectories identical, pools identical ⇒ zero WEALTH_TAX events ever).

Mechanism (verified): the tax base is **personal balances only** (coop treasuries
excluded unless `include_inventory` is on, per the D14 design decision). In this
equal world, private money is ~13M units across 1000 citizens — the top-1%
hold ~100k each, far below the 500k-unit threshold. The same engine path
**demonstrably bites in unequal worlds**: the earlier unequal study's top-1%
share collapsed 3228→524bp under the same 800bp rate. An equal society has no
taxpayer; the wealth tax is a **sleeping watchdog** — inert until inequality
actually exists.

### Land dump: absorbed, foreclosed, no lasting mark

The dump (23 parcels cashed at t=60) does not break the society either:

- The monopolist's cash-out briefly re-concentrates wealth (top-1% share spikes
  445→663bp at t=100), then the Georgist LVT forecloses 15 parcels the same
  snapshot window and the share decays back to ~350bp — same as base.
- Hunger waves after the dump stay **inside the base world's chaotic band**
  (e.g. s42: dump-world waves of 397/604/914 vs base-world waves of 404/779/671
  — different shapes, same magnitude; the +1-citizen butterfly effect dominates).
- `unmet_streak_max = 649` in every dump run is the **documented monopolist
  artifact** (the scripted pool-funded agent owns no pantry, as in
  `sweeps/land_study/`), NOT a starving underclass — ordinary citizens' hunger
  follows the same wave pattern as base.

### Design reading

1. **The wealth tax cannot be "too high" in a healthy economy — it can only be
   irrelevant.** It activates exactly when its target (personal wealth
   concentration) exists. If game designers want the tax to matter at lower
   wealth levels, the THRESHOLD (not the rate) is the knob.
2. **Coop wealth is invisible to the personal wealth tax.** A coop-leviathan
   (like pair-2's s123 wage aristocracy) is untaxed by design. If that becomes a
   problem in the game, the lever is `include_inventory`/treasury inclusion —
   a deliberate future study.
3. **Land monopoly + dump is a nuisance under the full stack**, confirming the
   land_study verdict at society-timeline resolution.

---

## Sequencing — Research early vs late: the "luxury" advice is obsolete

**Verdict: ✅ Under the FIXED funding rule, research is no longer a late-game
luxury.** The old atlas verdict was measured against the broken (pool-draining)
rule. With the reserve floor protecting dividends:

| Cell (median of 3 seeds) | Gini | Produced | Unmet | Pool end |
|---|---|---|---|---|
| research_early (t=50) | 2,732 | 81,427 | **5** | 696M |
| research_late (t=400) | 2,625 | 79,368 | **5** | 923M |
| research_never | 2,671 | 75,686 | 256–656 | 1.67B |

- **Any research timing ends chronic hunger; never-research keeps it** in every
  seed (unmet 656/256/256 in the never cells vs ≤5 typical in funded cells; one
  early-seed chaotic wave at 358).
- Timing only shifts ~2k production and the size of the protected pool: early
  investment spends the pool sooner (696M end vs 923M late).
- All arms carry the p4 all_on config, so `unmet_streak_max=601` in every cell is
  the documented pantry-less scripted monopolist artifact — constant across arms,
  ignored for comparisons.

**Design reading:** with the floor fix shipped, research is safe to offer from
the start. The player choice is a pool-spend-vs-productivity trade, not a trap.

---

## Sequencing — Crisis response: SLOW response rewires society

**Verdict: ❌ Waiting 100 ticks doesn't just fail to help — it changes WHO owns
the society.** Same shock streams per seed, same emergency powers; only the
declaration timing differs (at disaster onset t=100/300/500 vs 100 ticks late):

| Cell | Gini per seed | Unmet per seed | Produced med |
|---|---|---|---|
| crisis_onset (fast) | 2,580 / 3,965 / 2,558 | 451 / 96 / 354 | 56,418 |
| crisis_late100 (slow) | **7,295 / 5,530 / 3,091** | 0 / 534 / 966 | 61,570 |
| never (P2 baseline) | 2,529 / 2,610 / 2,598 | 886 / 616 / 261 | ~73,000 |

### The society story (worst late case, seed 123)

A pandemic-era shortage hits at t≈300 while the emergency declaration lingers
unresolved. With crisis rationing absent, scarcity pricing runs free, insolvencies
pile up, and the rich buy the dip: **top-1% wealth share explodes 365→3,285bp**
(more than a third of all private money), the bottom-20% collapses to 200bp, and
hunger pins at 886/1000 for two hundred ticks. The Society Pool drains to
**45M units** (from 1.67B) — dividends nearly dead. The world never rebalances
before the next crisis hits at t=600. Fast response keeps Gini at ~2,500–2,600
in 2 of 3 seeds through the same shocks.

The paradox of the medians: late response shows HIGHER production (61.5k vs
56.4k) — because rationing suppresses luxury output. Fast response is the
equality-preserving choice; slow response is the prosperity-now,
oligarchy-later choice. Neither is "free"; the game should surface this
trade-off explicitly.

---

## Hunger root cause (2026-09-14 instrumented diagnostic, base_s42)

Instrumented 650-tick run (`/tmp/hunger_diag.log`, memrun): per-good unmet
composition, market listings, hungry-citizen balances, bread-chain coop
finances. **Verdict: the user is right — something IS structurally wrong.**

1. **Hunger is not bread and not poverty.** Late-game chronic unmet is
   water (455–946 citizens), electricity (271–871), milk (~607–630), meat
   (~350–385), transport (402–522), eggs, fruit, housing. Bread oscillates and
   resolves. Hungry citizens are RICH: median balance 34k→360k over the run,
   p90 up to 590k — affordability is not the binding constraint.
2. **Zero essential listings at hunger peaks while stock exists.** At every
   detailed snapshot: bread_listed_qty=0, bread_listers=0, while bakers hold
   10–936 bread on 57k–160k treasuries. Prices frozen (bread 38; base world has
   scarcity_pricing OFF — verified in params). Nothing re-prices, nothing clears.
3. **Persistent unserved demand with no supply response:** unserved_bids
   grain=865 for ALL 650 ticks; water=916 late-game. Capacity never answers.
4. **Essential capacity is frozen at founding.** 124 coops at t=2, ZERO new
   foundings in 650 ticks (P3's broken founder trigger: requires zero active
   listings, which never happens). Service goods (water/electricity/transport)
   cannot be buffered in pantries, so any capacity gap = immediate unmet, and
   the chronic infrastructure gap (8 water coops vs 1000 citizens) never closes.
5. **The grain layer is financially dead while downstream hoards.** Farmer
   coops: treasury 2–888 credits, wage_debt 400k–1.43M (honest wages accumulate
   debt when sales lag). Millers/bakers: 57k–160k treasuries. The pool
   periodically ASSUMES dead farmers' wage debts (engine wage-debt rule), a
   hidden pool→workers recycling that keeps the broken chain alive.

**Design synthesis:** hunger persists because the economy has NO working growth
mechanism for essential capacity: founder trigger broken (P3) + no price signal
(scarcity pricing off by default) + no expansion behavior + service goods
unbufferable. Fix directions (future spec): relax founder trigger to persistent
unmet OR thin stock; default scarcity pricing ON for essentials; allow coop
expansion on persistent unserved bids. Coop SIZE is a non-issue (ruleset caps
members at 20; the s123 'aristocracy' was 12 workers earning wages, 1/3 seeds,
self-corrected) — the system's ailment is too little entry, not concentration.


- All 51 cells complete, resumable, money conservation exact in every run.
- Shock streams byte-identical per seed across cells (P3 mechanism re-verified:
  base ≡ base3 across pairs).
- Tax-vacuity mechanism instrumented directly: max personal balance over a
  100-tick equal-world run = **260,207 units** vs threshold 500,000 → zero
  WEALTH_TAX events (memrun log /tmp/tax_probe.log).
- Full test suite unaffected by the `start_tick` amendment (research suites
  18/18 during build; full suite green at 466 after the reserve-floor fix).

## 966-Citizen Capacity Audit (2026-09-15)

Probe: `scripts/capacity_966_audit.py` (150 ticks, seed 42, stage-6 scaling).
Data: `sweeps/society/capacity_966_s42.json`.

**Question:** does the scaled world's installed capacity cover honest
post-kcal need at city scale? (The 179-citizen gate verifies code paths;
this verifies the arithmetic.)

### Verdict: capacity-healthy at scale, two tight spots

| Sector | Coverage | Note |
|---|---|---|
| Food (kcal GROUP) | **1,582%** | grain alone 1,206% — famine arithmetically impossible |
| Bread (single food) | 95.7% | tightest single food; group covers via substitution |
| Utilities | electricity 247%, water 292%, heating 160%, transport 202% | all safe |
| Durables/services (cycled) | housing 133%, healthcare 556%, childcare 556%, education 1,618%, clothing 1,113%, books 1,043%, maintenance 135%, furniture 534%, household 205% | all covered |
| **Medicine** | **83.5%** | the ONLY true under-capacity (2 producer coops, 26.4 vs 31.6/tick cycled need) |

### Audit bugs found and fixed en route (both were false alarms)
1. Integer-floor runs: a coop pooling <100 labor-h/tick showed ZERO
   capacity for 100-hour recipes — the engine accumulates pooled labor
   across ticks (`labor_pool_hours`); capacity must be fractional.
2. Durables measured per-tick: housing/clothing/etc. are `needs_cycle`
   goods (housing = 1 per 360 ticks); per-tick need overstated 30–360x.

The earlier "housing 0%, healthcare 55%" alarm in this session was bug #1
+ #2, not a real gap. Housing_guild exists with 22 members across 3 coops.

### D18 wage-debt backstop at scale (free rider on same run)
Book 19.7M units across 73 indebted coops (~270k avg vs 480k–1.4M
insolvency thresholds), **zero WAGE_DEBT_ASSUMED events** in 150 ticks.
No coop near structural insolvency; backstop correctly dormant at scale.
Consistent with the 179-citizen plateau finding — D18 calibration VERIFIED
at 966 citizens, no fix needed.

### Actionable
- Medicine: +1 producer coop or batch bump closes the only real gap.
- Founder trigger reads `demand_ema`; ema_end vs need shows the signal
  will fire for medicine (ema 22 vs need 31.6) — but only 2 producer
  coops exist and founders were absorbed; founder mobility (D19) remains
  the lever that would self-heal this.
