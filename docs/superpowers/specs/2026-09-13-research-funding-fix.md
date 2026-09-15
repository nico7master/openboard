# Spec: Research Funding Reserve Floor (fix stock-proportional pool drain)

**Date:** 2026-09-13 · **Status:** approved (user, 2026-09-13) · **Author:** Agent Zero
**Evidence:** sweeps/p4/FINDINGS.md · sweeps/atlas/ATLAS.md · docs/STUDY_PLAN.md

## Problem

`research.fund_pool_phase` moves `surplus_pool × research_share_bp // 10_000` into the
innovation pool **every tick** — a percentage of the pool's remaining STOCK. A
stock-proportional drain compounds: at 250bp the pool halves every ~28 ticks regardless
of economic health.

Observed (P4 combination study, `all_on` arm, 650t, 1000 citizens, seeds 7/42/123):

- Society Pool 2.07B → <1M by **t=180** in all 3 seeds (ended at ≤20 units).
- 1.83B locked in `research_funding` as permanent "know-how" (conservation held —
  money out of reach, not destroyed).
- Dividend channel dead → Gini +5,200bp (≈7,850–8,140), production −17%, unmet worse
  in 2/3 seeds.
- Confirms atlas isolation sweeps (accounting-corrected): research WINs 0bp = 27/27,
  250bp = 21/27, 500bp = 0/27 — dose-dependent harm with no safe long-horizon setting.

For the game this is a **trap knob**: a rule that reads like a mild tax silently kills
the economy, and blocks any "full realism" preset.

## Fix: reserve floor (Option A)

**Principle:** research may tax what society *earns above* a protected dividend
reserve — never the reserve itself.

New optional research param `reserve_floor` (int, default **0**):

```
taxable = max(0, surplus_pool - reserve_floor)
take    = taxable * research_share_bp // 10_000
```

- `reserve_floor` absent or 0 → **exact pre-fix arithmetic** → old worlds replay
  byte-identically (project convention: absent key = feature off).
- Negative values clamp to 0 (same defensive style as `research_share_bp`).
- While the pool is at/below the floor, research funding **pauses** (emits nothing) —
  dividends keep flowing from the protected reserve.

**Not in scope (future options):** Option B flow-share (tax the tick's surplus inflow,
not the balance) as a semantic upgrade; re-spending or refunding existing
`research_funding`; changing the allocation or crisis-redirect phases (untouched —
redirect happens after funding).

## Touch points

| File | Change |
|---|---|
| `src/openboard/research.py` | `fund_pool_phase`: floor math + docstring. No event-shape change. |
| `tests/test_research.py` | New test: floor protects reserve, excess-only share, absent/negative = pre-fix identity. |
| `scripts/p4fix_rerun.py` | Verification harness: all_on ×3 seeds with floor 1B via memrun → sweeps/p4fix/. |

No `rules.py` change: `validate_params` does not validate the research dict today
(research keys ride on direct ruleset construction); adding validation would change
rejection behavior for existing saves — deliberately avoided.

## Verification (success criteria)

1. **Unit:** floor respected (no funding at/below floor), excess-only share exact,
   invariant `surplus + innovation + Σfunding` unchanged, absent/negative floor =
   pre-fix numbers.
2. **Integration rerun (all_on × 3 seeds, floor 1B, memrun):**
   - pool ≥ 1B at end in every seed (never collapses),
   - Gini back near the no-research band (< ~3,000; skills add a mild rise),
   - production ≥ 73k (research bonuses may push it higher — intended semantics),
   - extended conservation `money_delta + Δforeign + Δresearch == 0` exact.
3. Full targeted research suites pass (`tests/test_research.py`,
   `tests/test_realism_research.py`).

## Risks

- Research effectively stops while the pool sits at the floor — intended (dividends
  outrank know-how), and the Policy Lab knob keeps working: raise share or lower floor
  to push harder.
- Old demos/replays of broken-research worlds stay broken by design (replay fidelity).

---

## Verification result (2026-09-13)

**All criteria met.** Fixed all_on ×3 seeds (sweeps/p4fix/): pool 666M at t=650
(never collapses; crosses floor at t=160 with tap-pause proven in-vivo, slope
−5.94M→−0.68M/tick), Gini 3,023–3,825, production 75.9k–76.5k, unmet 6, extended
conservation exact in all seeds. Targeted research suites 16/16; full regression
suite 466/466 passed. See sweeps/p4fix/FINDINGS.md.
