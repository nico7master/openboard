# Spec: Source-Model Completion (2026-09-15)

**Founder directive:** "implement all of it the way it is planned" — close the three gaps between
`docs/source/open-board-market-socialism.md` and the engine.

## Gap table (from the 2026-09-15 audit)

| # | Source promise | Engine today | This spec |
|---|---|---|---|
| A | "Prices ... provide real-time signals of scarcity or abundance" | `scarcity_pricing` built + realism-tested, but OFF in defaults | ON by default with anti-gouging guard |
| B | "Game-theoretic incentives (whistleblower rewards, automatic audits) keep the system honest" | oversight flags exist; no reward, no audit cycle | `REPORT` action + bounty; periodic `AUDIT_REPORT` events |
| C | "genuine scarcity → allocate based on need (priority lists, lotteries, or democratic decision)" | essential clearing = FCFS/rotation only | need-first ordering (priority mode), votable |

---

## Package A — Scarcity pricing ON by default

**Default:** add to `DEFAULT_RULESET_PARAMS`:
```python
"scarcity_pricing": {"enabled": True, "max_markup_bp": 2_500, "step_bp": 500, "decay_bp": 250},
```
(proven values from `tests/test_realism_scarcity.py::sp_params`.)

**Safety (verified in code today):** the essential pass clamps settlement price to the floor
(`if price > entry["floor"]: price = entry["floor"]  # L2: essential needs never pay premium`),
so citizens' `BUY_ESSENTIAL` never pays the markup; the premium steers the auction layer only.
Crisis override zeroes signals (anti-gouging, already implemented).

**Replay safety:** `genesis_state(..., ruleset_params=...)` callers that pass explicit params are
unaffected; worlds constructed from defaults (Run._params, gates) adopt the new default going forward.
Historical saves store their own params snapshot → old saves replay byte-identically.

**Verification:** full suite (scarcity realism tests already assert signal/premium mechanics);
new test: default ruleset has scarcity enabled; gate proof: hardcore 2,000-tick gate × 3 seeds via memrun
with defaults (no famine regression allowed).

---

## Package B — Whistleblower rewards + automatic audits

### B1. REPORT action (whistleblower bounty)

- New citizen action `REPORT`: payload `{"kind": ..., "target": ...}` — cites an *existing* oversight flag
  `(kind, target)` from `state.flags` (kinds: HOARD / MARKET_POWER / FREE_RIDER).
- Deterministic bounty: **first** valid report per (kind, target) earns `wb_reward_credits` (default 100)
  from the Society Pool (pool -= reward; reporter += reward) — pool must cover it; second-and-later reports
  of the same (kind, target) are rejected (`ALREADY_REPORTED`) and earn nothing.
- Payment recorded as `WHISTLEBLOWER_PAID` event (public on the board — transparency).
- Rewards are identity-bound; no self-report of own flags (`SELF_REPORT`) — no gaming via self-citation.
- New optional param `whistleblower`: `{"enabled": bool, "reward_credits": int(1..100_000), "max_per_tick": int(1..100)}`; default **OFF** (replay-safe); validated in rules.py like other optional params.
- Validator: `REPORT` rejected unless whistleblower enabled, flag exists, not self, not already paid.
- Dispatch: `REPORT` added to SUPPORTED_ACTIONS, validators, appliers (signature `lambda t: _apply_report(state, t, params)`).
- New Reason members: `REPORT_DISABLED`, `FLAG_NOT_FOUND`, `ALREADY_REPORTED`, `SELF_REPORT`.

### B2. Automatic audit (periodic, deterministic)

- Every `audit_every_ticks` (default 50; part of new optional param `audits`: `{"enabled": bool, "every_ticks": int(10..10_000)}`; default OFF) the engine appends a public `AUDIT_REPORT` event containing:
  - ledger integrity: recompute chain (recount txs; every record's prev_hash linkage and tx_hash integrity re-derivable deterministically — the audit recomputes the **count** and the **flag summary**),
  - flag summary: counts per kind + open/total,
  - pool + treasury totals (public board numbers).
- Hook: in `apply_tick` right after the oversight detection block (line ~3677 site), `if audits enabled and tick % every == 0`.
- Pure integer arithmetic; event only — no state mutation (replay-safe).

**Verification B:** new `tests/test_whistleblower_audit.py`:
1. default OFF → `REPORT` → `REPORT_DISABLED`; no AUDIT_REPORT events.
2. enabled + planted HOARD flag → first REPORT pays exactly `reward_credits` from pool, emits WHISTLEBLOWER_PAID; second reporter rejected ALREADY_REPORTED.
3. self-report rejected SELF_REPORT.
4. AUDIT_REPORT appears exactly on every_ticks boundary with pool/treasury/flag counts matching state.
5. replay identity: disabled-default world byte-identical to pre-change baseline.

---

## Package C — Need-first allocation (priority lists / lotteries)

- New optional param `need_allocation`: `{"enabled": bool, "mode": "priority"|"lottery"}`; default OFF (replay-safe).
- Hook: `_served()` in `_clear_markets` (citizen essential pass). Today: rotation only (`fair_clearing`).
- priority mode: order by `(unmet streak desc, bidder asc)` — the longest-suffering citizen is served first
  (`state.unmet_needs[citizen][good]` = ticks-unmet, already maintained by consume phase).
- lottery mode: deterministic lottery seeded by `(tick, good)` → pseudo-random permutation (integers only, hashless —
  use a small LCG on (tick*31+len(good)) basis) — equal need, equal chance, replayable.
- Precedence when both fair_clearing and need_allocation enabled: need_allocation wins (it *is* the fair rule);
  crisis override (crisis_active) forces priority regardless (need-first is the crisis doctrine).
- **Verification C:** new tests in `tests/test_need_allocation.py`:
  1. priority: longest-unmet citizen served first when supply short;
  2. lottery: deterministic replay (same seed → same order across two runs), serves with equal likelihood over ticks;
  3. default OFF → byte-identical legacy behavior;
  4. crisis + lottery → priority order.

---

## Engine touch-point summary

| File | Change |
|---|---|
| `src/openboard/rules.py` | DEFAULT_RULESET_PARAMS += scarcity_pricing ON; OPTIONAL_PARAMS += whistleblower, audits, need_allocation; validation blocks |
| `src/openboard/engine.py` | `_apply_report` + validator + dispatch; WHISTLEBLOWER_PAID event; `_audit_report` helper + apply_tick hook; `_served` ordering modes |
| `src/openboard/state.py` | nothing (flags already persisted; no new state needed — rewards are balance moves + events) |
| `src/openboard/errors.py` | 4 new Reason members |
| `tests/test_whistleblower_audit.py`, `tests/test_need_allocation.py` | new |
| `tests/test_realism_scarcity.py` | extend: default-on assertion |
| `dashboard/server.py` | none (Run._params deep-copies defaults) |

## Success criteria

1. New unit tests pass; full suite green via memrun.
2. Hardcore gate (2,000 ticks × 3 seeds, defaults incl. scarcity ON): zero essential famine streaks.
3. Legacy replay identity proven (byte-identical outcomes when all three packages OFF).
4. STUDY_PLAN.md governance verdicts updated; HANDOFF.md noted.

## Out of scope
- Land, foreign sector, regional markets (already implemented and verified).
- Dashboard UI for reports/audits (separate task).
- Changing triage/crisis doctrine.
