# P4-fix Findings — Research Funding Reserve Floor (spec 2026-09-13)

**Verification rerun of the P4 `all_on` arm with the research reserve-floor fix.**
Everything else is byte-identical to the P4 probe (same trader book, shocks, 650t,
1000 citizens, seeds 7/42/123). Harness: `scripts/p4fix_rerun.py` (`P4FixRun`:
`research.reserve_floor = 1B units = 10M cr`), all runs via memrun, one at a time.

## Verdict: the collapse is fixed

| Metric | broken (P4 all_on) | **fixed (floor 1B)** | no-research ref (P2 skills_on) |
|---|---|---|---|
| Society Pool end | 20 / 10 / 3 units | **666M ± 1M (all seeds)** | 1.67B (all seeds) |
| Gini end | 7,852–8,140 | **3,023–3,825** | 2,713–3,572 |
| Production end | 60,887–61,631 | **75,936–76,505** | 70,936–72,855 |
| Unmet needs end | 497–639 | **6 (all seeds)** | 47–471 |
| Deaths | 0 | 0 | 0 |
| Conservation (money+foreign+research) | ✅ 0 | ✅ **0 exact, all seeds** | — |

**All spec success criteria met:** pool never nears 0 (never collapses), Gini back in
the healthy band, production ≥73k, extended conservation exact.

## In-vivo proof the tap pauses at the floor

The pool crosses the 1B floor at **t=160 in all 3 seeds** (dividends draw it down
organically). Slope of the pool BEFORE vs AFTER the crossing:

| seed | pre-slope | post-slope |
|---|---|---|
| 7 | −5,944,433/tick | −678,311/tick |
| 42 | −5,945,304/tick | −675,558/tick |
| 123 | −5,946,762/tick | −676,127/tick |

The ~8.8× flattening is exactly the research tap switching off (pre = tap + organic
draw; post = organic dividend draw alone). **The floor mechanism demonstrably works
under the full rule stack**, and the residual draw is sustainable (~980 ticks of
headroom at the final rate).

**Honest nuance:** the pool ends at ~666M, below the literal 1B floor — by design.
The floor only blocks the research tap; dividends still draw the pool down, and the
tap correctly resumes only if the pool climbs back above 1B. The protected zone was
never breached by research (no RESEARCH_FUND below floor — in-unit tested; in-world
the tap is off below 1B by construction).

## What the fix buys vs doing nothing

- **Broken behavior:** pool dead by t≈180, dividends stop, Gini +5,200bp, production
  −17%, unmet needs 497–639.
- **Fixed behavior:** dividends flow all game (pool 666M at t=650), inequality back in
  the healthy band, production **above** the no-research world (research productivity
  bonuses actually materialize instead of collapsing the pool) — 76k vs 71–73k, and
  unmet needs 6 vs 47–471.
- Research still accumulates 914M know-how (vs 1.83B broken — roughly half the
  "knowledge" for a working economy; the old rule effectively taxed dividends to
  over-accumulate know-how).

## Replay identity (old worlds byte-identical)

`reserve_floor` absent/0 ⇒ arithmetic unchanged (taxable = max(0, pool − 0) = pool).
Verified by the pre-existing unit test `test_funding_phase_invariant_neutral_and_gated`
(still passing, untouched) plus the new floor test
`test_funding_reserve_floor_protects_pool` (4 assertions: pause at/below floor,
excess-only share, absent-floor identity, negative clamp).

## Files

| Item | Path |
|---|---|
| Spec | `docs/superpowers/specs/2026-09-13-research-funding-fix.md` |
| Engine change | `src/openboard/research.py::fund_pool_phase` (new optional `reserve_floor` key, default 0) |
| Harness | `scripts/p4fix_rerun.py` (+ `scripts/p4_probe.py::run` gained optional `run_cls/out_dir/name` overrides, default byte-identical) |
| Raw data | `sweeps/p4fix/all_on_floor1B_s{7,42,123}.json` |

## Caveats

- Fixed runs still have traders (P4 design) — identical book to the P4 baseline, so
  the comparison isolates the research rule.
- The 1B floor value is a design choice (10M cr ≈ 5 months of organic pool draw at
  these settings); the knob is exposed for Policy Lab tuning.
- Research effectively pauses while the pool is below floor — intended (dividends
  outrank know-how); raise the share or lower the floor to push harder.
- Suite status: targeted research suites **16/16**; full regression suite **466/466 passed** (both via memrun).

## Verification stamp (2026-09-13 13:19 CEST)

- Targeted research suites: **16/16 passed**.
- Full regression suite (memrun, 14 GiB / 2-core pin): **466 passed** in 628.7s —
  zero failures, pre-fix behavior intact everywhere else.
