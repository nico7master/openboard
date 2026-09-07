# OpenBoard Economy — Handoff (2026-09-07)

## Current state: HEALTHY & HISTORIC MILESTONE
- **FIRST FULL HARDCORE-GATE PASS in the unequal world** (commit `e56ec2c`):
  essentials 0 (bound 0), breadth 15 (bound 30), ALL 3 seeds (42/123/7) identical PASS.
- The unequal scenario (top 1% owns 50% of the 21M fixed supply, pool empty, tax off)
  is now PROVEN winnable at the engine level.
- 49/49 targeted tests green; worktree clean; all work committed.

## What the unequal world is
- 21,000,000 credits fixed supply, splittable to 0.01, never minted. Invariant: balances + pool + coop treasuries == 21M, exact.
- Genesis: richest 1% (1 citizen) owns 50% (10.5M). Society Pool = 0. Wealth tax OFF until the player enacts it.
- Server: dashboard/server.py, Run(seed, scenario='unequal'). Port 8421.

## The winning fix (D21g, offer smoothing)
- Bread listings arrived in bursts (0/84/8/438/day) vs constant 181 demand; unmet == 181 - sold exactly.
- Fix: offer_smoothing votable param — essential producers release inventory toward the observed demand rate (state.demand_ema), capped by held-buffer, instead of dumping held-buffer in lumps. Total production & input use UNCHANGED, only release schedule smooths.
- Two rejected experiments kept as votable default-OFF Lab rules with evidence in code:
  - supply_buffer_runs (input-order buffer): 3/14 — stripped neighbor stages
  - demand_smoothing (EMA planning): 2/12 — didn't touch the burst

## Fast diagnostic (scripts/fast_diag.py)
- 300-tick run in ~37s with live alarms: rejection storms per reason, wage-debt trajectory, DEAD essential producers (last-PRODUCE gap), unmet streaks. Use BEFORE any 2000-tick gate.
- Caught an EMA dict-indexing KeyError in 0.4s that was silently killing gate runs.

## Week 2 next step (from the shipping-month plan, docs/superpowers/plans/2026-09-03-shipping-month.md)
- Harvest the 100+ banked simulations (sweeps/ has wealth_tax sweeps): prove winnable policy paths from the 50/50 start to a fair distribution while everyone stays fed. Then deflation study (fixed money + growth), multiplayer (10+ seats), Break-the-System v2, onboarding quest, crash-proof persistence, Cardano preprod anchor + verifier, performance floor, release gate -> v1.0.0.

## Known pitfalls (do NOT rediscover)
- Gate runs use sim.py specialist closures, NOT bots.py strategic_producer — patch sim.py for gate-relevant behavior.
- Container memory: 10 GB cgroup (not 31 GB); run one seed per process.
- LedgerRecord payload lives in r.tx (fields: seq/tick/accepted/tx/reason) — probe via r.tx, else you get all-zero artifacts.
- Never early-return around collected personal buys in bot functions (pin-streak-at-1 bug class).
- Panic-buying must never apply to essentials (positive feedback loop).
- Fresh container recreations wipe pip installs (pytest/flask) but keep project files; reinstall ad hoc.
- smooth-the-plan and buffer-the-inputs both FAILED; only smooth-the-OFFER worked (neighbor-safe).

## Key files
- Engine: src/openboard/engine.py (clearing ~line 1220+, wage phases, backstop)
- Bots: src/openboard/sim.py (gate specialists — patch HERE for gate behavior), src/openboard/bots.py (dashboard honest_worker)
- Rules: src/openboard/rules.py (param registry + validators; OPTIONAL_PARAMS tuple)
- Dashboard: dashboard/server.py (world assembly; new-world params near 'live_cost_baselines')
- Docs: docs/what-we-built-plain-language.md (plain explainer), docs/superpowers/plans/2026-09-03-shipping-month.md (the plan)
