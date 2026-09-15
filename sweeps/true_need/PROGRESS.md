# True-Need Balance Program — Progress Log (2026-09-15)

## Goal
Balance the economy to physiologically real needs (user directive:
"calculate it with real calories", "just a hungry quota", "food choices
dont matter"). Spec: docs/superpowers/specs/2026-09-15-true-need-balance.md

## Fix chain (all applied)
1. kcal needs model (rules.py): 2,900 kcal budget, kcal_per_unit map,
   food group closes on TOTAL calories not per-good quotas.
2. Grain as STAPLE (rules.py + server.py basket): 1 unit = 3,400 kcal =
   a full day's subsistence food; closes the budget alone. Without it
   the food group never closed (gate: worst_breadth 2000/2000).
3. Catalog batch rescale (catalog.py): coal 24->400, electricity 300->1200,
   wind 100->500, heating 40->160, grain 100->800, vegetables 80->200,
   fruit 60->200, fish 50->200, livestock 60->150x3, meals 10->20,
   flour 9->20, bread 20->40. Daily-draw demand (kcal) needs bigger
   batches; per-run input amounts preserved ratio.
4. CRITICAL INVARIANT FOUND (server.py SPECIALISTS): a specialist's
   `buys` dict OVERRIDES the recipe-native bid loop, so it must mirror
   the recipe's per-run consumable inputs. 7 stale dicts (written for
   pre-rescale recipes) created PERMANENT BID SUPPRESSION: plant held
   16 coal (4 members x stale 4/run) < 48 needed, need computed to 0,
   never bid again -> dead 301/300 ticks -> no electricity -> no water
   -> dead kitchen -> meals streak 2000-25=1975. Synced all 7.

## Verification state (seed 42, 2000-tick gate)
- Before program: worst_essential=1975, worst_breadth=2000 FAIL
- After staple+rescale (dead plant): 1975/2000 (identical — plant dead in all)
- After buys-dict sync: worst_essential=2, worst_breadth=153 FAIL
- Diagnosing final 2 offenders (gate_diag per-good dump running)

## Round 4 (14:38): final two offenders (gate_diag per-good dump)
- transport streak 153 (60/tick supply vs 358/tick demand)
- heating_fuel 62 (coal competition margin)
- Fixes: transport batch 20->120, heating 160->240, coal 400->600
- fast_diag after: wage debt NEGATIVE growth (-79k, paying down),
  essentials only startup transients (elec 5, water 8),
  transport/heating alarms gone
- Final gate launched 14:43 (gate_final.log)

## Round 6-7 (15:00-15:16): gate splits by seed, then closes
- Round 6: seed 42 PASS (essential 0, breadth 24); seed 7 FAIL narrow
  (essential 4, breadth 36): heating_fuel 36 (refiner target 60 < one
  batch 240 -> runs pinned 1/tick vs 1074/tick demand), water 4
- Round 7 fixes: refiner target 1300 (5-run sizing), water batch 240,
  wind 800 (clean-power margin); fast_diag s7: heating_fuel alarm GONE,
  water 1, only startup transients left
- 3-seed decisive gate launched 15:17 (gate_final3.log)

## Round 8-9 (15:41-15:57): seeds 42+7 PASS; seed 123 clothing tail
- Round 8: seeds 42 AND 7 PASS; seed 123 narrow fail: clothing 36
  (producer dump: tailors HEALTHY — last_produce=1995, treasury 59k,
  no debt; capacity shortfall: 2 members x batch 8 = 8/tick vs ~45/tick
  cycle demand; weavers batch 6 cap fabric supply at 6/tick)
- Round 9 fix: fabric batch 6->36, clothing batch 8->48 (buys dicts
  already match — no sync needed)
- fast_diag s123: clothing GONE from alarms; only startup transients
  (electricity 5, water 1). Wage debt growing +289k noted as watch item.
- DECISIVE 3-seed gate launched 15:57 (gate_final4.log, ~33 min)

## Round 10 (16:28): seed 123 down to a single-tick blip
- Seeds 42, 7 PASS again; seed 123: worst_essential=1 (bound 0),
  worst_breadth=10 (bound 30) — clothing fix worked (36->10)
- gate_diag s123b launched 16:29 to name the 1-tick essential

## Round 11 (16:54): *** GATE PASSED — 3 seeds × 2000 ticks ***
- Final fix: wind_farm 800->1000 (zero-input margin) for the 1-tick
  electricity blip on seed 123
- Verdict: 1 passed in 645s — ALL SEEDS: worst_essential=0,
  worst_breadth <= 30. The true-need economy survives gate severity.
- Full test suite launched for final validation.

## FINAL SUMMARY (2026-09-15 17:05)

**Verdict: GATE PASSED** — 3 seeds × 2,000 ticks, worst_essential=0,
worst_breadth ≤ 30 in every seed (1 passed in 645s, 16:54).

The economy now produces physiologically real needs:
- Food = a 2,900 kcal calorie budget from any mix (grain is the staple:
  1 unit = 3,400 kcal); variety foods are preference demand.
- Every essential chain closes: coal→electricity→water→farms→livestock
  →meals all verified live with zero dead producers.
- Full regression suite running for final validation (this log).

**Key invariant for future work:** a specialist's `buys` dict must mirror
its recipe's per-run consumable inputs — it overrides the recipe-native
bid loop, and stale values create permanent bid suppression (the plant
death that caused the original 1,975-tick meals streak).

Artifacts: /tmp gate logs (gate_final*.log), /tmp/gate_diag*.log,
/tmp/fastdiag*.log, /tmp/tnb_probe*.log; spec in
docs/superpowers/specs/2026-09-15-true-need-balance.md.

## FINAL VALIDATION (17:20-17:28)
- Full regression: 474 passed, 2 failed -> both STALE TEST CONSTANTS
  (fish 50->200, wind 100->1000 from the rescale), not regressions.
- Patched both tests with comments; re-ran: 2/2 PASS (rc=0).
- Final state: gate PASSED + regression green. Program complete.

## Wage-debt watch item — CLOSED (17:56)
Full-length trend probe (scripts/wage_debt_trend.py, seed 7, 2000 ticks):
debt builds during startup (38k @t2 -> peak 6.4M @t400), then PLATEAUS
(oscillates 4.3-5.7M from t400 to t2000, debtors steady ~21). Not a
spiral — a one-time startup float that the economy carries while staying
fed (gate PASSED on this exact trajectory). Re-check if input prices or
wage rules change materially.
