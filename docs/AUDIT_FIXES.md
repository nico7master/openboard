# Audit Fix Tracker — 2026-09-20 (approved: all packages, one by one)

**Mandate:** founder approved all packages (P-GOV, P-ECON, P-GAME, P-DESIGN, P-PROBE). Work order: P-GOV → P-PROBE (feeds P-ECON) → P-ECON → P-GAME → P-DESIGN. Two additional reviewers (spec-drift, code-quality) were restarted by the founder and will return — their findings get appended here when collected.

**Status legend:** ☐ pending · 🔍 probe-first · 🔧 fixed (+test) · 🚫 won't-fix (reason) · ⏳ awaiting reviewer

Source audit: `docs/AUDIT_2026-09-20.md`. Freeze lifted only for listed fixes; every fix lands with a regression test; full suite before each package commit.

---

## P-GOV — governance hardening (IN PROGRESS)

| # | Finding | Status | Notes |
|---|---|---|---|
| A1 | CRISIS_VOTE counts no voters — unlimited repeat votes, single-actor ratification | ☐ | fix: track voters per crisis declaration; reject repeat senders |
| A2 | structural 60% tier over CAST weight + 10% quorum → minority capture via abstention | ☐ | fix: structural denominator = all citizens × token_bp |
| A3 | delegation mirroring multiplies weight (bloc = (1+F)×token); tally-time reads | ☐ | fix: cap mirrored weight per delegate; snapshot delegations at proposal-open |
| A4 | trust entrenchment: default trust 100, +5 for any pass, no rate limit, precomputable dice | ☐ | fix: default 50; outcome-based trust; per-cycle proposal rate limit; content-hash-seeded die |
| A5 | structural whitelist omits surplus_spending (and loans/oversight/scarcity) | ☐ | fix: add economically decisive keys |
| A6 | auto-ratified crisis = one-death kill-switch, kind always 'pandemic' | 🚫 DECIDE | founder directive stands for RC1; revisit severity threshold + kind mapping post-RC1 |
| A7 | whistleblower bounty rotation by colluders | 🔍 | EV probe first (penalty vs bounty) |
| A8 | vote-token attention race (decoys consume the electorate) | ☐ | fix: no new proposals while another is in its final tick |
| A9 | rollback trial window reverts structural changes cheaply | ☐ | fix: structural rollbacks keep structural tier |

## P-PROBE — verify-before-fix (after P-GOV)

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
| B1 | loan default blocking | ☐ | after B1 probe |
| B2 | rent amortization | ☐ | after B2 probe |
| B3 | capital_wear + recent_sales/unserved_bids outside state hash; clone() incomplete | ☐ | include in snapshot_dict; complete clone() |
| B4 | refresh pricing | ☐ | after B4 probe |
| B5 | shocks/demographics/wage_debt_repay not votable (OPTIONAL_PARAMS gap) | ☐ | add with validators |
| B6 | recent_sales accumulation | ☐ | after B6 probe |
| B7 | base catalog: heating_fuel/medicine quotas without recipes | ☐ | minimal recipes or strip from default quotas |
| B8 | input advance = perpetual grant | 🚫 DECIDE | founder design: generous founding support; revisit with accountability post-RC1 |
| B9 | dashboard invariant omits foreign_balance | ☐ | add to sums |
| B10 | wage-debt insolvency hardcodes wage 800 | ☐ | compute from actual wage bill |
| B11 | post-crisis markup snap-back | ☐ | decay-clamp first ticks post-crisis |

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
| C10 | no auth on endpoints | ⏳ | post-RC1 multiplayer gate; document as known gap for RC1 |
| C11 | LLM detach leaves headless citizen | ☐ | restore bot twin on stop |
| C12 | silent arena errors | ☐ | showToast on failure |
| C13 | unaffordable buy buttons enabled | ☐ | disable when unaffordable |
| C14 | quest narrow/skippable | ☐ | fold into P-DESIGN polish |
| C15 | LLM cost display edge cases | ☐ | warn on missing usage data |
| C16 | duplicate keys/roster entries, O(n) scans | ☐ | cleanup pass |

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
| D10 | no social pressure signal | 🚫 DECIDE | post-RC1 (touches simulation behavior) |

## Late reviewer additions (spec-drift + code-quality — collect when they return)

| # | Finding | Status | Notes |
|---|---|---|---|
| — | awaiting restarted reviewer reports | ⏳ | founder restarted both chats |

---

## Completion log

| Package | Completed | Commit | Suite |
|---|---|---|---|
| (none yet) | | | |
