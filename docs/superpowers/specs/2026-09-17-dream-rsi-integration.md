# Dream-RSI Integration — Analysis & Wiring Proposal (DESIGN ONLY, not yet wired)

Date: 2026-09-17 · Status: PROPOSAL awaiting founder approval · No engine/gate/memrun changes required.

## 1. Verdict: WORTH-IT, scoped to expensive searches

**Reasoning:** This project has a real, recurring, automatically-scoreable search shape — the
lever sweep (`sweeps/atlas/`: 81 runs; `sweeps/unequal_rerun/`: 37+; `wealth_tax__*`: 88+).
Every attempt already produces a scored JSON with zero new science. BUT the *past* grids are
complete and cheap (~22.6 s per 300-tick diag); exhaustive enumeration already answered them.
Search-order intelligence only pays when **attempts are expensive**: city-scale gate runs
(966 citizens × 2,000 ticks ≈ 8–13 min serialized) and the upcoming scaling work (10k citizens,
demographics params, region counts) where full grids are unaffordable.

**Scope rule:** use Dream-RSI for city-scale/gate-class searches. Do NOT use it to re-search
cheap exhausted grids.

## 2. Inventory of recurring scored searches

| Search | Varies per attempt | Score source (existing) | Attempts/campaign | Status |
|---|---|---|---|---|
| Lever atlas (L1 interest, L2 markup cap, L3 research share) | `I,S,R` combo, seed | `sweeps/atlas/*.json`: `inv_bad`, `worst_ess_streak`, `ess_ok`, `final_top1_bp`, `verdict` | 27–81 + seeds | DONE (exhaustive) — validation data only |
| Tax/dividend grid | `tax_bp, div_bp` | `sweeps/unequal_rerun/*.json` same fields | 30–60 | DONE — validation data only |
| **City-scale stability search (TOP CANDIDATE)** | one realism-lever/param pack at 966-citizens × 2,000 ticks | gate log `final:` line (`inv_bad`, `worst_streak`) + GATE verdict | 10–30 per new feature | RECURRING — every future feature must re-prove the gate |
| 10k-citizen scaling params (batch table, founder counts, region count) | batch/coeff set | capacity audit JSON + gate | 15–40 | PLANNED |
| Entrepreneur-trigger loosening, election spam filter tuning | rule params | p2/p3-shaped study JSONs | 10–20 | PLANNED |

## 3. TOP CANDIDATE — exact contract

**Candidate A (pilot): atlas diag search.**
- attempt = `bash scripts/memrun.sh 14 /tmp/atlas_<I>_<S>_<R>.log /opt/venv/bin/python scripts/atlas_grid.py diag I,S,R 42` (one combo per process, already resumable, writes one JSON)
- score = evaluator over `sweeps/atlas/diag_i<I>_m<S>_r<R>_s42.json`
- score formula (identity-independent, from existing fields):
  `score = 0` if `inv_bad != 0` or `ess_ok is false`; else
  `1000 - 10*max(worst_ess_streak.values()) - abs(final_top1_bp - 500)/10`
  (higher = stable + equal; inv_bad is a hard zero because money conservation is non-negotiable)
- evaluator = `scripts/rsi_evaluator.py <path.json>` → prints `{"score": <int>, "verdict": ...}` — reads ONE JSON, no imports from engine, ~30 lines.

**Candidate B (graduate target): gate-class search.**
- attempt = param-pack gate run (2,000 ticks, 966 citizens) via memrun with checkpointing per the standing probe rule
- score = parse existing gate log tail (`final: pop=… inv_bad=N worst_streak=M` + `GATE: PASS`)
  → `score = 0` if inv_bad≠0 or no PASS; else `1000 - 25*worst_streak`
- evaluator = second mode of the same `rsi_evaluator.py` (`--gate-log`), still zero gate-script changes.

## 4. Wiring plan (exact, when approved)

1. `.a0proj/plugins/dream_rsi/config.json` → `{"campaign_project": "openboard-economy"}`
   (keeps world pool + policy lineage inside this project; plugin default today is `dream_rsi`,
   whose dir exists but is empty of our traces).
2. `scripts/rsi_evaluator.py` — new standalone script (sketch above). NO changes to any gate script.
3. `policies/` — auto-seeded by `rsi_lap start`; candidate policies later via `rsi_dream` flow.
4. Lap attempts launch ONLY via memrun (standing probe rule). Remote PC (docs/REMOTE_SIMS.md)
   may execute the same memrun-wrapped commands host-side as an accelerator; recording stays identical.

## 5. Pilot campaign

- **Objective:** re-derive the atlas L3 answer (max research share that stays WIN) in ≤ 12
  attempts/lap × 3 laps, fixed seed 42 — a known-answer validation of the whole loop.
- **Budget:** ≤ 12 attempts/lap; stop lap when a combo scores ≥ 900 or attempts exhausted.
- **Success metric:** sims-to-first-stable-config vs historical 27-combo sweep; also lap-over-lap
  mean best score. Paper's ~50%-fewer-attempts after a few laps = hypothesis to check, not fact.
- **Graduation:** if pilot shows ≥ 30% attempt savings or equal-cost finding, wire Candidate B
  for the next real city-scale feature (10k scaling).

## 6. Lap protocol (verbatim for a future chat)

1. `rsi_status` → confirm campaign is `openboard-economy`, note current policy NAME.
2. `rsi_lap action=start` → read returned policy + budget.
3. For each chosen attempt (ONE world process at a time — `pgrep -f atlas_grid` first):
   a. `bash scripts/memrun.sh 14 /tmp/atlas_<combo>.log /opt/venv/bin/python scripts/atlas_grid.py diag <I>,<S>,<R> 42`
   b. `/opt/venv/bin/python scripts/rsi_evaluator.py sweeps/atlas/diag_<...>_s42.json` → score
   c. `rsi_lap action=record action_type=attempt desc="atlas I,S,R seed42" cmd="<command a>" artifact="<json path>" score=<score>`
   d. If memrun hit the cap: read log first; do NOT blind-retry; record exit_code honestly.
4. `rsi_lap action=finalize`.
5. After ≥ 2 laps: write 1–2 candidate policies to `policies/candidates/`, then `rsi_dream`.
6. Record campaign verdict in `docs/STUDY_PLAN.md`.

## 7. Open risks

- **Seed chaos noise:** single-seed scores are noisy (one-citizen divergence band); pilot pins
  seed 42 for comparability — policies may overfit s42; mitigate later with 2-seed min for finalists.
- **Goodhart:** composite score could be gamed by degenerate worlds (e.g. zero production → no
  hunger streaks). Guard: `ess_ok`/production fields stay in the evaluator; human reads verdicts.
- **Checkpoint/restart:** gate-class attempts that die mid-run must be checkpoint-resumed per the
  standing memrun rule; a resumed run's score is still valid (pre-death data rule).
- **Quest mixing:** one campaign pool holds multiple question families; keep `desc` tags strict
  (`atlas`, `gate966`, `scale10k`) so replay can filter.
- **PC interplay:** remote results must be synced back before `record` so the artifact path exists locally.
