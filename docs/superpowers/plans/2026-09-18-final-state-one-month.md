# One-Month Plan to Final Working State (RC1)

Written 2026-09-18 · Horizon: 2026-09-18 → 2026-10-18 · Owner: founder + agent sessions

## Definition of Done (what "final working state" means)

**Release Candidate 1 = a stranger can play it.** Concretely:

1. A human opens the dashboard, starts a new 966-citizen world, and *plays*: votes with the
   monthly token (split/delegate/revoke), files and backs proposals, reports violations,
   reads public audits, watches need-allocation and crises work — without reading code.
2. The **"Break the System"** adversarial mode is a complete loop: attack tools → run →
   scored leaderboard entry → engine survives or honestly degrades.
3. Long sessions hold: an overnight soak (thousands of ticks) with zero money-conservation
   violations, zero famine streaks, and **live founding working** (coop count grows when
   demand exceeds capacity — the D19 fix).
4. Politics verified under the *shipped* defaults (scarcity ON, vote token, whistleblower,
   audits, need-allocation) — the 2026-08 society conclusions re-checked, not assumed.
5. Everything reproducible: suite green, 3-seed gates green, save/load round-trip exact.

Explicitly OUT for RC1 (de-scoped): persistent multiplayer/MMO (next milestone),
10k-citizen scale (stretch, see Week 4), Cardano anchoring (founder's call — optional slot).

## Standing rules (apply every week)

- Spec before engine change (brainstorming hard-gate). Dashboard/UI work also gets a short spec.
- Heavy batches: local via `memrun.sh` (14 GiB, 2-core pin, ONE world process) or the LAN PC
  (`docs/REMOTE_SIMS.md` — probe first, fall back locally). Never bare.
- Every engine change re-runs: focused tests → full suite → 3-seed survival gate.
- Friday of each week: update HANDOFF.md + STUDY_PLAN verdict block (half-day buffer built in).

## Week 1 (Sep 18–24) — Playability I: make the engine visible

| Item | Detail |
|---|---|
| Spec | `2026-09-19-rc1-ux.md`: player surfaces + Break-the-System loop |
| Vote token UI | widget: see monthly token, split allocations, delegate/revoke; direct vote overrides delegate |
| Civic board | proposals list + file/vote; **decision needed**: proposal sponsoring (anti-spam) or free |
| Oversight surfaces | REPORT button → bounty events; audit reports timeline; need-allocation panel; crisis banner |
| Break-the-System MVP | wire attack tools (breaksystem.py, attack API exist) into a run-and-score session with leaderboard save |
| Chronicle | verify shortage-line dedup fix still holds after all recent changes |
| **Exit gate** | a 30-tick guided session where every named mechanic is operable from the UI; screenshots in docs |

## Week 2 (Sep 25–Oct 1) — Live-growth engine fixes (spec-gated)

| Item | Detail |
|---|---|
| Spec | `2026-09-25-live-growth.md` |
| D19 founder mobility | seated founders may LEAVE an under-capacity coop to found/join where demand_ema says needed (tenure+idle guards kept) |
| Founding proof | 2,000-tick 966 run: coop count > start, capacity audit shows gap closure; remote PC batch OK |
| Proposal economy | small anti-spam rule consistent with token politics (sponsor-stake or visibility threshold) — only if founder approves in spec |
| **Exit gate** | founding proof PASS + suite + 3-seed gate; no capacity regression (medicine ≥139%, bread ≥120% hold) |

## Week 3 (Oct 2–8) — Release-candidate science

| Item | Detail |
|---|---|
| Politics sanity re-run | society battery under new defaults (crisis timing ×2, skills+research, land dump; 3 seeds each — PC parallel ≈ minutes/batch) |
| Wave re-measure | hunger-wave amplitude post-balance; if still >~300/1000 peaks, spec a smoothing/buffer policy — else record verdict and move on |
| Save/load robustness | autosave→reload→continue byte-consistency; clone() invariants test (delegation registry etc.) |
| 10k decision point | try pre-partitioned clearing prototype on the PC; if <2 days work → include as stretch; else de-scope to post-RC1 with a documented number |
| **Exit gate** | sanity battery verdicts in STUDY_PLAN; save/load test green; 10k decided in writing |

## Week 4 (Oct 9–16) — Freeze, soak, ship RC1

| Item | Detail |
|---|---|
| Code freeze Oct 9 | only fix-forward; no new mechanics |
| Overnight soak | 24h-class run at 966 (PC or memrun), watch: conservation, RSS, t/s, founding, audit/ledger health |
| Full verification | suite + 3-seed gate + save/load + UX walkthrough on final build |
| Docs | player guide (plain language), one-page README refresh, STUDY_PLAN final block, HANDOFF |
| Optional slot | Cardano anchoring IF founder approves (ledger hash-chain external anchor; small-medium) |
| **Exit gate** | **RC1 tag** + demo session recording + green board |

## Risks & mitigations

- **Chaos re-rolls:** any engine touch invalidates prior byte-identity → gates re-run each change (budgeted).
- **UX scope creep:** RC1 wires EXISTING mechanics only; new game rules need founder sign-off in spec.
- **PC availability:** probe-first workflow; local memrun fallback; never block.
- **Wave disease deep fix:** if smoothing policy needed in W3, it's a rule change → spec + gate, may push
  soak to end of W4 buffer; de-scope to post-RC1 if it threatens the date.
- **Politics surprises:** new defaults may shift old verdicts (that's the point of re-running); treat
  findings as data, tune minimally, keep the date.

## Founder decisions needed before Week 1 starts

1. Break-the-System as the RC1 game mode (per vision doc) — confirm.
2. Proposal spam: sponsor-stake / visibility-threshold / leave-free for RC1.
3. Cardano: in the optional Week-4 slot, or explicitly post-RC1?
