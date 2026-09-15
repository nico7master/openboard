# OpenBoard Economy: Complete Study Plan

## 🎯 Goal
Learn exactly how every rule changes the game world. We want to find real outcomes, not just see if the engine runs.

## ⚠️ Safety Rule
**Always use `memrun`** for any test that runs longer than 1 minute. This protects our computer from freezing.

---

## ✅ What We Already Know

| Rule | Result | Takeaway |
|---|---|---|
| **Research** | ✅ Safe **with the reserve floor** (fixed 2026-09-13, sweeps/p4fix/). Old rule tapped a % of pool STOCK every tick (compounding → pool dead by t≈180). New optional `reserve_floor` param protects the dividend reserve: fixed all_on worlds end Gini 3.0–3.8k, production 76k, unmet 6, conservation exact. | **Ship research with the reserve floor ON.** Without the floor, treat as late-game only. |
| **Interest (Loans)** | ✅ Safe on its own. | Can be used anytime. |
| **Scarcity Pricing** | ✅ Safe on its own. | Prices can rise freely when goods are rare. |
| **Taxes** | ✅ Tested. Wealth tax reduced inequality without starving people. | Taxes are safe if balanced with dividends. |
| **Land & Rent** | ✅ Tested 2026-09-12 (9 combos, 650t, 1000 citizens, sweeps/land_study/). Georgist LVT defeats a full monopolist: balance 1.2M→~17 units by t≈55, 15/23 parcels foreclose from t≈60. No mass starvation (seed-7 '+78 unmet' was a probe artifact — the scripted monopolist has no pantry). Dump sell-back drains ≤0.6% of the Society Pool. Gini impact small and seed-dependent. | Land monopoly is a nuisance, not a famine. Default LVT (1bp/tick) self-defends; sell-backs are pool-safe. 8 'survivor' parcels persist (dividend income covers their LVT) — harmless. |
| **Imports (Trade)** | ✅ Tested 2026-09-12: bot worlds are byte-identical open vs closed (0 trade events, unmet 114=114). Bots have NO trade logic. | Foreign sector is player-only today. 'Block imports' scenarios need bot trade logic or a human player to matter. Engine mechanics (tariffs, shocks, conservation) already verified by tests. |
| **Chaos (measurement rule)** | ✅ Tested 2026-09-12: ONE extra citizen flips a 1000-citizen world's whole 650-tick trajectory (seed 42: pop 966→954, final unmet 616→1; sweeps/seed42_anomaly/). | Policy studies MUST compare within-seed or across many seeds — single-run deltas at this scale are noise, not signal. |
| **Skills (training)** | ✅ Tested 2026-09-12 (sweeps/p2/): machine stock ends HIGHER with skills in 3/3 seeds (+735/+1347/+1516), food security improves 3/3, no training bottleneck. Mild Gini rise from +3%/level wage premium. | Skills are safe to ship. |
| **Governance voting** | ✅ Tested 2026-09-12 (sweeps/p2/): a 72% majority WILL approve a confiscatory 50%/tick wealth tax in all seeds (703/1000 votes). It collects ~305M units, cuts production 3/3, collapses Gini ~2400bp — poorer but stable, zero deaths. Bots also spam ~270 failing proposals/run → real game UI needs a proposal gate (deposit/cooldown). | Democracy is self-harming but not fatal; add a spam gate before shipping elections. |
| **Crisis override** | ✅ Tested 2026-09-12 (sweeps/p2/): identical harsh shocks, crisis arm cut unmet needs by 435–520 people in 2/3 seeds (3rd +93) at the cost of ~22% fewer production events; 300 active crisis ticks, ratified, money conserved, zero deaths. | Emergency lever works and is worth its production cost. |
| **Disasters (shocks)** | ✅ Tested 2026-09-12 (sweeps/p3/, 15 runs, 650t, 1000 citizens): harsh profile (0.8%/tick) does NOT cascade — production within ±0.5% of healthy control, unmet inside the normal chaos band, no death spiral. Determinism bonus: the disaster arm reproduced P2 crisis_off byte-identically on all 3 seeds. | Shortages stop, they don't cascade. Ship shocks. |
| **Spoilage** | ✅ Tested 2026-09-12 (sweeps/p3/): shelf lives 2–10 ticks → PERMANENT famine (unmet ~950–966/966 from t≈55, all 3 seeds, rot alone suffices), ~618k units rotted/run, Gini +310bp. The economy's buffer stock converts to waste and never recovers. | Do NOT ship short shelf lives. If spoilage ships: long shelf lives (weeks) or prepared foods only. |
| **Panic buying (demand memory)** | ✅ Tested 2026-09-12 (sweeps/p3/): byte-identical to no-memory in all seeds. Memory forms on essentials only, and bots deliberately exclude essentials from the hoard bonus (panic-guard); market goods never go chronically short in bot worlds. | Inert for bots by design. May matter with human players or market-good shortages. |
| **Machine wear (durable capital)** | ✅ Tested 2026-09-12 (sweeps/p3/): wear is ON by default in every run (dashboard/server.py) and is LOAD-BEARING: wear-OFF worlds collapse (production −23%, machine stock −23%, unmet +40/+350/+537, Gini +380–490bp) because machines burn 1-per-run instead of amortizing over 20. No breakdown cascade with wear ON. | Keep wear ON. Initial 'no effect' result was wear-ON vs wear-ON — the A/B lesson is recorded in sweeps/p3/FINDINGS.md. |
| **New businesses (entrepreneur)** | ✅ Tested 2026-09-12 (sweeps/p3/): ZERO emergent foundings in 12 shock runs — trigger needs unmet ≥5 ticks AND zero active listings, but supply shocks never zero out listings (farms keep listing at reduced output). Founding mechanics themselves covered by tests/test_entrepreneur.py. | If emergent entry is desired, relax the trigger: persistent unmet need OR thin listings (<N days stock), not zero listings. |
| **Land + Trade (combo)** | ✅ Tested 2026-09-13 (sweeps/p4/, 12 runs, 650t, 1000 citizens, scripted traders): systems compose cleanly — production ≈ dump baseline, LVT forecloses all 23 parcels in every seed, dump payout and trader extraction are independent additive drains. Gini +1,663bp in seed 42 traced to ONE late-founded coop holding 16% of citizen money (not land-related, mechanism undiagnosed). | No hidden cross-system breakage. Coop-level wealth concentration exists in rare seed-specific cases — watch it if coop payouts matter in-game. |
| **Disaster + Trade (combo)** | ✅ Tested 2026-09-13 (sweeps/p4/): neither safety net nor meaningful drain in bot worlds — drought-window unmet differs from the no-trade disaster baseline by −587/+40/−45 (chaos band). Traders exported ~0.4% of bread stock at famine prices: a real but tiny drain. The import-food channel is untestable with bots (they have no trade logic). | Trade's famine role is decided by PLAYERS: scripted ideal arbitrageurs extract ~1% of the pool per 650 ticks per 15M bankroll (upper bound); imports could only help if a human/bot actually sells food domestically. |
| **Everything ON (full realism)** | ✅ **Works with the research reserve floor** (fixed 2026-09-13, sweeps/p4fix/). The original collapse came from ONE lever, not the combination: research share (250bp) tapped 2.5% of the pool STOCK every tick (compounding, ~28-tick half-life) → Society Pool 2.07B → ≤20 units by t≈180, dividends dead, Gini +5,200bp, production −17%. Fix: new optional `reserve_floor` research param — the tap applies only to the pool ABOVE the floor (verified in-vivo: pool drawdown flattens ~8.8× the moment it crosses the 1B floor at t=160 in all seeds). Fixed all_on ×3 seeds: pool 666M at t=650, Gini 3.0–3.8k, production 76k, unmet 6, conservation exact. | **Full-realism preset is shippable with `reserve_floor` ON.** Fund research from surplus above a protected dividend reserve — never a raw % of pool stock. |

---

## 🧬 Society in Motion (2026-09-13, sweeps/society/) — interactions, sequencing, timelines

51 runs, 650t, 1000 citizens, 3 seeds; first study with within-seed interaction
decomposition (`AB − A − B + base`), lever-sequencing cells, and society
timelines (wealth classes, bread price, real wage, dividends, firm concentration).

| Question | Result | Takeaway |
|---|---|---|
| **The healthy society itself** | Golden age (t=50–150: zero hunger, bread index 100→12, real wage ×5), then CHRONIC chaotic hunger waves (170–780/1000) despite cheap bread, stable wages, stable dividends. Equality improves on its own (top-1% 741→~320bp, bottom-20% 252→~930bp); coops do NOT become leviathans (174→5bp). | Hunger is a production-volatility problem, not a price/wealth problem. The engine's equal start self-de-concentrates; the game's drama must come from shocks and choices, not passive drift. |
| **Spoilage(week-scale) × Disasters** | ✅ NO interaction (all effects inside chaos band; Gini ±90bp, production ±1.7%). | Individually-safe realism rules stay safe together. Ship both. |
| **Skills × Research(fixed)** | ⚠️ SUB-ADDITIVE: production 2.3–8k below the additive prediction in 3/3 seeds; s123 shows a wage-premium aristocracy re-forming (top-1% 341→494bp, interaction +702bp). Still the best society on hunger (0) and real wages. | Research is the anti-famine superweapon; skills' cost hides until research is on. Watch coop/wage concentration when both are maxed. |
| **Wealth tax(800bp) × Land dump** | Interaction EXACTLY zero — the tax never fired: byte-identical trajectories in 3/3 seeds; instrumented max personal balance 260k vs threshold 500k (equal world's private money ~13M total; coop treasuries excluded from tax base). Same engine bites hard in unequal worlds (old study: top-1% 3228→524bp). | The wealth tax is a SLEEPING WATCHDOG: inert in equal societies, armed when inequality exists. Threshold (not rate) is the knob to make it matter early. Land dump still absorbed (LVT forecloses, monopoly decays). |
| **Research timing: early (t=50) vs late (t=400) vs never** | ✅ Old "research = late-game luxury" verdict is OBSOLETE under the fix. Any timing ends chronic hunger (unmet ≤5 typical vs 256–656 never). Early spends pool sooner (696M end) vs late (923M); production 81.4k / 79.4k / 75.7k. | With `reserve_floor` ON, research is safe to offer from game start. Player choice = pool-spend vs productivity, not a trap. |
| **Crisis response: fast (onset) vs slow (+100 ticks)** | ❌ Slow response doesn't just fail — it REWIRES ownership. Same shocks: fast keeps Gini ~2,500–2,600 (2/3 seeds); slow explodes Gini to 3,091/5,530/7,295, top-1% 365→3,285bp in the worst case, bottom-20% →200bp, pool →45M, hunger pins 886/1000 for 200 ticks. Paradox: slow shows HIGHER production (rationing suppresses luxury output). | Emergency-response SPEED is an equality lever, not just a hunger lever. The game should surface the trade-off: fast = fair-but-poorer; slow = richer-now, oligarchy-later. |


---

## 🍞 True-Need Balance (2026-09-15, sweeps/true_need/) — physiological needs + the buys-dict invariant

**User directive:** "calculate it with real calories… food choices don't matter."
Replaced the per-good fantasy basket (every citizen demanded fish AND meat
AND eggs AND milk… every tick) with a **calorie-budget needs model**:
~2,900 kcal/tick from any food mix (kcal_per_unit map), hunger closes on
TOTAL calories. **Grain = the staple** (1 unit = 3,400 kcal = a day's
subsistence food) — without a citizen-accessible staple the food group
NEVER closed (gate breadth 2000/2000).

**The critical engine invariant found while balancing** (server.py): a
specialist's `buys` dict OVERRIDES the recipe-native bid loop, so it must
mirror its recipe's per-run consumable inputs. Seven stale dicts
(pre-rescale values) caused PERMANENT BID SUPPRESSION: power_plant held
16 coal (4 members × stale 4/run) < 48 needed, computed need to 0, never
bid again → dead 301/300 ticks → no electricity → no water → dead kitchen
→ meals streak 1,975/2,000. Synced all 7.

**Fix chain (all verified by fast_diag + per-good gate dumps):** staple
grain → 12 catalog batch rescales (coal 24→600, electricity 300→1200,
grain 100→800, …) → buys-dict sync → transport target 400 + service
batches (childcare/healthcare 96, education 48) → refiner target 1300 +
water 240 + wind 800→1000 → fabric 36 / clothing 48.

| Metric | Before program | After (gate, 3 seeds × 2,000 ticks) |
|---|---|---|
| worst_essential streak | 1,975/2,000 | **0 — GATE PASSED** (1 passed, 645s) |
| worst_breadth streak | 2,000/2,000 (bound 30) | ≤30 in all seeds |
| Dead essential producers | plant, 3× water, kitchen | none |
| Wage debt trend | +1.28M (spiral) | −79k (paying down, seed 42) |

**Design consequence:** the economy now produces what humans actually
need (calories, water, power, warmth, transport) instead of an inflated
shopping list, and founders/investors see true capacity gaps. Variety
goods (fish, meat, clothing…) remain as preference demand — citizens buy
them when the staple is secured, exactly as the user specified.

---

## 🔍 What We Need to Study

### Priority 1: Realism Rules (New)
*These decide how money and goods flow.*

| Rule | Question to Test | What We Want to Find Out |
|---|---|---|
| **Land & Rent** | If one person owns all the land, do others starve? | Does inequality break the economy? |
| **Imports (Trade)** | If we block imports, do food prices crash or run out? | Does the country survive without outside help? |
| **Tax Rate** | If taxes are too high, do factories stop working? | Is there a 'sweet spot' for taxation? |

### Priority 2: Player Behavior (Action)
*These decide how players interact with the system.*

| Rule | Question to Test | What We Want to Find Out |
|---|---|---|
| **Skills** | If everyone gets a skill boost, do we run out of machines? | Does training create a bottleneck? |
| **Voting** | Can players vote for a tax that kills their own factories? | Do people vote short-sightedly? |
| **Crisis Mode** | If we stop luxury goods, does the food supply survive? | Does the emergency rule work as intended? |

### Priority 3: Hidden Systems (Built but Untested)
*These exist in the engine but have no data yet.*

| Rule | Question to Test | What We Want to Find Out |
|---|---|---|
| **Disasters** | If a factory breaks by accident (storm/quake), does the system recover? | Do shortages cascade or stop? |
| **Spoilage** | If food rots after a few days, does it stop people from hoarding? | Or does it just cause waste? |
| **Panic Buying** | After one shortage, do people over-buy and cause the next one? | Does this memory help or hurt? |
| **Machine Wear** | Do old machines breaking down crash production? | How much repair capacity do we need? |
| **New Businesses** | When players start new coops, does everyone get richer? | Can opening too many hurt existing ones? |

### Priority 4: Combinations (The Big Unknown)
*Every rule was tested alone. Real games run them all at once.*

| Test | Question | Why It Matters |
|---|---|---|
| **Land + Trade** | With both on, do local farmers die out? | Realism systems may fight each other. |
| **Everything ON** | The full-realism world: all rules at realistic settings. | Does the whole model hold together, or collapse? |
| **Disaster + Trade** | A harvest failure WITH open imports. | Does trade act as a safety net or a drain? |

---

## 🚀 Next Steps

1.  **Study Land & Trade:** See if these two rules break the wealth balance.
2.  **Study Hidden Systems:** Check Disasters and Panic Buying.
3.  **Study Combinations:** Test if rules clash (e.g., Land + Trade together).
4.  **Write the Rules:** Use the data to set the limits.

---

## 📝 Notes

*   **Focus:** We want to know *what happens in the game*, not if the code works.
*   **Data:** All results are saved in the `sweeps/` folder.
*   **Goal:** Build a guide for the game based on real test data, not guesses.
