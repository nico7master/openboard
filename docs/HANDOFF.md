# OpenBoard Economy — Handoff (2026-09-07, evening)

## Current state: WEEK 2 HARVEST COMPLETE — WP2.2 GATE EXCEEDED 6x

### The unequal world is not just winnable — it is ROBUSTLY winnable
- **54/54 WIN**: 18 policy paths (wealth_tax.rate_bp {100,200,400,600,800,1200}
  × dividend_share_bp {2000,3000,5000}) × 3 seeds (42/123/7), 1500 ticks each.
- Final private top-1 share ~524–525bp on ALL of them (gate: <1500bp), from
  ≈5000bp at genesis. Worst essential streak 11 (bound 30), identical everywhere.
- Money invariant exact every tick, every run (inv_bad=0).
- Data + heat-card: `sweeps/unequal_rerun/` (54 JSONs, HEATCARD.md, grid.log).
- Findings: `docs/superpowers/specs/2026-09-07-week2-harvest-findings.md`
  - Rate sets PATH SPEED not endpoint (300-tick: 100bp→948bp, 200→577, ≥400→~557;
    1500-tick: all → ~524bp). Residual 524bp = untaxed below-threshold balance
    (subsistence protection) + coop working capital — a stable, explainable equilibrium.
  - Dividend share shapes the ride, not the endpoint (≤1bp spread at 1500 ticks).
- WP2.4 deflation study DONE: `docs/superpowers/specs/2026-09-07-deflation-policy-study.md`
  (essentials clear at cost floors via BUY_ESSENTIAL — no auction deflation;
  credit velocity = primary votable knob; demurrage = default-OFF Lab rule, NOT yet implemented).

## New tooling
- `scripts/harvest_rerun.py` — unequal-world policy-grid harness (resumable,
  one combo-seed per process, per-tick money invariant, essentials streaks,
  top-1 trajectory). `list|diag TAX,DIV [seed]|run TAX,DIV|report`.
- `scripts/harvest_triage.py` — banked-sweeps triage (25 combos, PROVISIONAL
  pre-cap heat-card at `sweeps/harvest_triage.md`).
- `openboard.metrics.top1_share_bp` + `SimMetrics.summary()['final_top1_share_bp']`
  — PRIVATE wealth share (balances + treasuries, pool EXCLUDED — the pool is
  the tax's destination; counting it masks the redistribution, proven by probe).
  8 unit tests in `tests/test_metrics.py`.

## What the unequal world is
- 21,000,000 credits fixed supply, splittable to 0.01, never minted. Invariant: balances + pool + coop treasuries == 21M, exact.
- Genesis: richest 1% (1 citizen) owns 50% (10.5M). Society Pool = 0. Wealth tax OFF until the player enacts it.
- Server: dashboard/server.py, Run(seed, scenario='unequal'). Port 8421.
- Proven winnable: enact ANY tax 100–1200bp (threshold stays default/upc-scaled)
  + any dividend share → top-1 < 1500bp with everyone fed.

## The winning fix (D21g, offer smoothing)
- Bread listings arrived in bursts (0/84/8/438/day) vs constant 181 demand; unmet == 181 - sold exactly.
- Fix: offer_smoothing votable param — essential producers release inventory toward the observed demand rate (state.demand_ema), capped by held-buffer, instead of dumping held-buffer in lumps. Total production & input use UNCHANGED, only release schedule smooths.
- Two rejected experiments kept as votable default-OFF Lab rules with evidence in code:
  - supply_buffer_runs (input-order buffer): 3/14 — stripped neighbor stages
  - demand_smoothing (EMA planning): 2/12 — didn't touch the burst

## Fast diagnostic (scripts/fast_diag.py)
- 300-tick run in ~37s with live alarms: rejection storms per reason, wage-debt trajectory, DEAD essential producers (last-PRODUCE gap), unmet streaks. Use BEFORE any 2000-tick gate.

## Week 3 next step (from the shipping-month plan)
- 3.1 Multi-human seats at scale (10+ seats, 1000-tick soak, zero invariant breaks)
- 3.2 Break-the-System v2 (scoring, timed rounds, leaderboard; playable 20-min round)
- 3.3 Onboarding quest (watch → enact → observe → adopt; tutorial can use the
  proven 400bp×3000bp path as the guided storyline)
- 3.4 Persistence & campaign (named saves, crash-recovery drill: kill -9 → ≤30s loss)
- Weekly tag v0.4 due (Week 2 complete: triage + re-run grid + deflation study landed)

## Known pitfalls (do NOT rediscover)
- Gate runs use sim.py specialist closures, NOT bots.py strategic_producer — patch sim.py for gate-relevant behavior.
- Container memory: 10 GB cgroup (not 31 GB); run one seed per process. Long grids: `setsid nohup` + `disown`, NOT plain `nohup &` (session resets kill the process group otherwise — cost us a re-launch).
- LedgerRecord payload lives in r.tx (fields: seq/tick/accepted/tx/reason) — probe via r.tx, else you get all-zero artifacts.
- Market events do NOT survive ledger pruning — read clearing prices from `state.applied` BEFORE `applied.clear()` each tick.
- wealth_tax.threshold in ruleset params is upc-scaled (×100) at the END of `Run._params()` — override rate_bp only, NEVER rewrite the threshold (2026-09-04 unit-scale fix).
- Never early-return around collected personal buys in bot functions (pin-streak-at-1 bug class).
- Panic-buying must never apply to essentials (positive feedback loop).
- Fresh container recreations wipe pip installs (pytest/flask) but keep project files; reinstall ad hoc.
- smooth-the-plan and buffer-the-inputs both FAILED; only smooth-the-OFFER worked (neighbor-safe).
- Full-suite pytest can wedge on IO in this container (observed: sleeping 12min at 10% CPU); prefer targeted files.

## Key files
- Engine: src/openboard/engine.py (clearing ~line 1220+, wage phases, backstop, _wealth_tax_phase ~line 2024)
- Bots: src/openboard/sim.py (gate specialists — patch HERE for gate behavior), src/openboard/bots.py (dashboard honest_worker)
- Rules: src/openboard/rules.py (param registry + validators; OPTIONAL_PARAMS tuple; wealth_tax/surplus_spending validator shapes)
- Metrics: src/openboard/metrics.py (gini + top1_share_bp; private-wealth semantics for top-1)
- Dashboard: dashboard/server.py (world assembly; new-world params near 'live_cost_baselines'; unequal genesis near line 798)
- Docs: docs/superpowers/specs/2026-09-07-week2-harvest-findings.md (this week's proof), docs/superpowers/plans/2026-09-03-shipping-month.md (the plan)
