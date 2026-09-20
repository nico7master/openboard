# Audit Fix Tracker — 2026-09-20 (approved: all packages, one by one)

**Mandate:** founder approved all packages (P-GOV, P-ECON, P-GAME, P-DESIGN, P-PROBE). Work order: P-GOV → P-PROBE (feeds P-ECON) → P-ECON → P-GAME → P-DESIGN. Both restarted reviewers have returned; their findings are recorded below (S-series, E-series) and slotted into packages.

**Status legend:** ☐ pending · 🔍 probe-first · 🔧 fixed (+test) · 🚫 won't-fix (reason) · ⏳ awaiting/post-RC1

Source audit: `docs/AUDIT_2026-09-20.md`. Freeze lifted only for listed fixes; every fix lands with a regression test (`tests/test_audit_gov.py`); full suite before each package commit.

---

## P-GOV — governance hardening (✅ CODE COMPLETE 2026-09-20 — 11/11 audit tests pass)

| # | Finding | Status | Notes |
|---|---|---|---|
| A1 | CRISIS_VOTE counts no voters — unlimited repeat votes, single-actor ratification | 🔧 fixed +test | `crisis.voters` dict (JSON-safe) + `CRISIS_VOTED` reason; tally counts first votes only |
| A2 | structural 60% tier over CAST weight + 10% quorum → minority capture via abstention | 🔧 fixed +test | denominator = all citizens × token (unit-guarded for legacy 10k); 2/5 voters now fail, 3/5 still pass |
| A3 | delegation mirroring multiplies weight; tally-time reads → last-second sweeps | 🔧 fixed +test | `delegations_snapshot` frozen at proposal-open; tally mirrors through the snapshot, not live state |
| A4 | trust entrenchment: default 100, +5 any pass, no rate limit, precomputable dice | 🔧 fixed +test | unknown politicians start at 50; `PROPOSAL_LIMIT` (one open proposal per proposer); die seeded on proposal content hash |
| A5 | structural whitelist omits surplus_spending (and credit, scarcity_pricing) | 🔧 fixed +test | `_STRUCTURAL_TOP_KEYS` extended — surplus diversion/credit/pricing now need the 60% tier |
| A6 | auto-ratified crisis = one-death kill-switch, kind always 'pandemic' | 🚫 DECIDE | founder directive stands for RC1; revisit severity threshold + kind mapping post-RC1 |
| A7 | whistleblower bounty rotation by colluders | 🔍 | EV probe first (penalty vs bounty) — P-PROBE |
| A8 | vote-token attention race (decoys consume the electorate) | 🔧 fixed +test | bots split the monthly token across open proposals instead of dumping on the first |
| A9 | rollback trial window reverts structural changes cheaply | 🔧 fixed +test | rollback structuralness judged on the REVERTED version's delta vs its parent (not its own params — that check is vacuous mid-trial) |

Replay-safety note: A2/A9 change settle behavior only for persuasion worlds (server default since 09-19); saved settled proposals are stored resolved, so resume replay is unaffected. A1/A3 additions are JSON-serializable state.

## P-PROBE — verify-before-fix (next)

| # | Finding | Status | Notes |
|---|---|---|---|
| B1 | serial loan default drains pool (overwrite destroys the record) | 🔍 | 20-tick probe → then fix (default blocks new loans) |
| B2 | capital_rent 20× overcharge under durable_capital | 🔍 | probe rent amounts vs wear → then amortize or skip |
| B4 | capital_refresh retires at stale book values → fund hoards | 🔍 | probe fund trend in soak data → price from live baseline |
| B6 | legacy recent_sales overwrite kills B2B demand signal | 🔍 | probe produce rates regional on/off → then accumulate |
| A7 | (above) bounty EV check | 🔍 | same probe batch |

## P-ECON — engine drain + coherence (after probes)

| # | Finding | Status | Notes |
|---|---|---|---|
| E1 | OPTIONAL_PARAMS missing stage-5 keys (research/shocks/demographics/wage_debt_repay/birth_stake_from_pool/wage_mint_mode) → PROPOSE of a full ruleset died INVALID_RULESET — governance dead in exactly those worlds | 🔧 fixed +test | pulled forward into P-GOV 2026-09-20; parity guard test prevents recurrence |
| B1 | loan default blocking | ☐ | after B1 probe |
| B2 | rent amortization | ☐ | after B2 probe |
| B3 | state-copy divergence: clone() omits loans, capital_wear, recent_sales, unserved_bids, demand_ema; _clone_coop omits wage_debt, recipe_intent, last_produce_tick; snapshot drops wear/sales/bids (E2, expanded scope) | ☐ | build copy paths from the dataclass field list + full round-trip equality test |
| B4 | refresh pricing | ☐ | after B4 probe |
| B5 | governance sub-schema never type-checked — vote_token_bp="5000" passes validation then TypeErrors the tick (E3) | ☐ | validate governance sub-key types in rules.py; one shared schema owner |
| B6 | recent_sales accumulation | ☐ | after B6 probe |
| B7 | base catalog: heating_fuel/medicine quotas without recipes | ☐ | minimal recipes or strip from default quotas |
| B8 | input advance = perpetual grant | 🚫 DECIDE | founder design: generous founding support; revisit with accountability post-RC1 |
| B9 | dashboard invariant omits foreign_balance | ☐ | add to sums |
| B10 | hardcoded constants: wage 800 in insolvency backstop; _CAP_TARGETS 60/1500 vs live ~10,095; _ess_seed 4 goods (E6) | ☐ | derive from params/state |
| B11 | post-crisis markup snap-back | ☐ | decay-clamp first ticks post-crisis |
| E7 | swallowed exceptions hide invariant violations (_research_effect_bp except:return 0; bots.py:398; sim.py:471) | ☐ | narrow excepts, flag unexpected errors ledger-visibly |
| E9 | quota trap: goods missing from essential_need_quota default to unboughtable | ☐ | genesis cross-check needs ⊆ quota |
| S3 | need_allocation lacks the source's third mode: "democratic decision" | ☐ | add votable mode or document omission |

## P-GAME — trust fixes

| # | Finding | Status | Notes |
|---|---|---|---|
| C1 | leaderboard farmable post-round | ☐ | refuse acts when over; record once |
| C2 | one global attack game | ☐ | owner token + mutex (per-session games post-RC1) |
| C3 | playbook attribution lies | ☐ | pin playbook per round |
| C4 | unmet streak not attacker-attributed | ☐ | attacker-attributed or delta-vs-baseline |
| C5 | score weights degenerate (flag burst optimal) | ☐ | cap flags/tick, count kinds, weight real harm |
| C6 | advertised invariant check never runs | ☐ | capture baseline at round start |
| C7 | queued actions vanish on autosave | ☐ | persist pending in to_save/from_save |
| C8 | autosave failures swallowed | ☐ | log + surface warning |
| C9 | leaderboard file race/wipe | ☐ | temp-file replace under lock |
| C10 | no auth on endpoints; /api/action accepts ANY sender string — unauthenticated impersonation (E4) | ☐ | require token on /api/action (+authz test); post-RC1 full multiplayer auth |
| C11 | LLM detach leaves headless citizen | ☐ | restore bot twin on stop |
| C12 | silent arena errors | ☐ | showToast on failure |
| C13 | unaffordable buy buttons enabled | ☐ | disable when unaffordable |
| C14 | quest narrow/skippable | ☐ | fold into P-DESIGN polish |
| C15 | LLM cost display edge cases | ☐ | warn on missing usage data |
| C16 | duplicate keys/roster entries, O(n) scans; E8 duplicate 'gini_bp' key in breaksystem.py:128 (AST-verified) | ☐ | cleanup pass + add ruff/pyflakes to CI |
| E5 | policy-adopt pre-law snapshot wrapped in except:pass — rollback promise fails invisibly | ☐ | report snapshot failure in response |
| E10 | dead order: params-None guard after first dereference | ☐ | move guard above first use |
| E11 | _apply_list_good/_apply_bid re-resolve active ruleset against tick contract | ☐ | use the resolved params |

## P-DESIGN — say the story

| # | Finding | Status | Notes |
|---|---|---|---|
| D1 | game never states its premise (50/1 start, fairness goal, win screen) | ☐ | mission banner + win screen |
| D2 | Break-the-System is a spectator sport | ☐ | per-cycle attack choices + oversight meter |
| D3 | governance OFF by default | ☐ | flip default for new worlds (founder-approved) |
| D4 | Citizen Seat undiscoverable | ☐ | header tab + tour step |
| D5 | proposals displayed as raw JSON | ☐ | plain-language rendering |
| D6 | no reign score | ☐ | reign scoreboard at round end |
| D7 | advisor can auto-play | ☐ | advisor depth dial |
| D8 | Mercury buried | ☐ | Civic Board story hook |
| D9 | quest trivially skippable | ☐ | completion rewards |
| S1 | Innovation Fund fully implemented but NEVER enabled in dashboard defaults — shipped worlds never run it | ☐ | enable research in server defaults |
| D10 | no social pressure signal | 🚫 DECIDE | post-RC1 (touches simulation behavior) |

## P-GOV2 — governance follow-ups (from late reviewers)

| # | Finding | Status | Notes |
|---|---|---|---|
| S2 | "Votes cannot be bought" documented with ZERO enforcement — unlimited TRANSFER + free DELEGATE make purchasable delegations mechanically possible and undetected | ☐ | flag transfer→delegation pairing or votable transfer-limit default |
| E12 | mixed-mode ballots: one dict ballot activates token_mode for the whole proposal incl. legacy strings counted at 10,000 | ☐ | normalize or reject mixed ballots |

## Docs-only follow-ups

| # | Finding | Status | Notes |
|---|---|---|---|
| S4 | Land: private landholding drifts from verbatim "owned collectively" — keep Georgist mechanics, state leasehold framing in constitution-facing docs | ☐ | README/constitution doc |
| S6 | stale comment conflict: rules.py "instant path" vs engine "flows through proposals" | ☐ | reconcile |
| S7 | inequality_seed: only production param with no paper trail | ☐ | document or remove |
| S5 | externality corrections (pollution/addiction/bubbles) missing | ⏳ | future milestone |
| S8 | universal services = refund model, not true provision | ⏳ | roadmap (documented) |

## Faithful core (reviewer-confirmed, no action)

Transparency/ledger, cost pricing, auction markets, surplus recycling, coops, whistleblower + audits, price-signal need allocation, foreign sector, regional markets — all verified present and faithful to the source text.

---

## Completion log

| Package | Completed | Commit | Suite |
|---|---|---|---|
| P-GOV (+E1 pulled forward) | 2026-09-20 | (this commit) | 11/11 audit tests; scoped 43/43; final full suite at commit |
