# Stage 3 Plan
- [x] spec doc
- [x] new specialists + coops + endowments in server/sim
- [x] capital_refresh off in baseline
- [x] competition coops (farmers_north, city_bakers, wind_farm)
- [x] tests: chain trades, self-sustained capital, resilience (tests/test_stage3.py — 6 tests)
- [x] 3x2000 gate + full check.sh
- [x] docs + commit

## Gate results (scripts/stage3_gate.py)

PASS on all 3 seeds x 2000 ticks:
- zero unmet needs at every checkpoint (state.unmet_needs empty)
- money invariant exact at every checkpoint
- capital consumed AND market-replenished: 46 burns vs 83 fills per seed
- gini ~0.28 stable from t750 onward (was 0.35 pre-fix)
- surplus pool stable ~5,270; retirement flowing (~389k by t2000)

## Bugs found & fixed during the stage
1. **Capital cost-floor leak** — legacy machine book value (1,500) leaked into
   VWAP fallback, pricing coal at 71 and killing the downstream chain.
   Fix: extended-catalog baseline overrides (machines 160, tools 25).
2. **Capital listing deadlock** — consumable stock buffer (10) prevented
   machine_works from ever listing its only output. Fix: capital goods list
   at any stock.
3. **Under-seeded heavy-batch coops** — steel/machine batches cost more than
   one run's revenue; seeds sized to full batch cycles.
4. **Probe artifact documented** — timeline "unmet" metric is stale when
   apply_tick is driven directly; true welfare signal is state.unmet_needs.

## Post-gate hardening (full-suite verification round)
5. **Capital maintenance gap** — bots bid for tools/machines only while
   `want_produce`; once output stock was full, a burned machine was never
   replaced and the coop froze forever (miners at 0 machines, t100-2000).
   Fix: bots maintain recipe-required capital stock ALWAYS (independent of
   production desire). Verified: miners sustain machines in the long run.
6. **Analytics money_total bug** — money_pie included capital_fund but
   money_total omitted it; the pie-sum test caught it. Fixed server-side.
7. **Stale test expectations** — dashboard/circular tests hardcoded the old
   cast (6 coops, 4 treasuries). Now derive from BASELINE_TREASURIES / count
   dynamically so future cast changes don't break invariants.

## Capital backstop (deadlock class fix)
8. **Structural capital deadlock** — a coop that burned its last machine
   with treasury < machine price can NEVER recover (no output -> no income).
   Fix: rule-gated `capital_backstop` phase — society's capital fund provides
   recipe-required replacement, booked as retirement (invariant exact).
   Restricted to coops with PROVEN production history (applied-history scan,
   cached outside state for replay safety). Default off; enabled at 10-tick
   intervals in the baseline. Regression tests: rescue + inert-without-param.
