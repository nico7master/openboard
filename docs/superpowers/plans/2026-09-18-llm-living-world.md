# LLM Living World — Full Design Evaluation & Plan (DRAFT, awaiting founder approval)

Date: 2026-09-18 · Status: DESIGN EVALUATION — no code, no engine changes in this document
Governing ideas: `docs/ideas/2026-09-08-engine-as-law-referee-predictor.md` (engine = referee,
actors play inside it) · `docs/ideas/vision-and-growth-path.md` (Break the System first)

---

## 0. The one-sentence architecture

**The engine stays a deterministic referee; LLMs become actors inside its rules — seated at
social roles, deciding on human timescales (events and months, not ticks), acting only through
the same validated Transaction API bots and humans use, with every decision recorded in the
ledger so replays stay byte-identical.**

---

## 1. Cadence — "do we need decisions every tick?" → NO

### The power-asymmetry doctrine (founder principle, 2026-09-18)

**We do NOT simulate every citizen with an LLM — ever.** Most people in the real world are
System-1 actors: they consume, work, live. That's the bots. LLM tokens are a *scarce resource
spent on agency, not on simulation breadth*: only the few actors who hold **power to change
things** get a seat — and each seat exists to pursue **its own goal** (win the attack, get a
law passed, build a business empire, expose fraud). The seat's job is not to "react" but to
make smart, multi-step decisions that make its goal come true — which is precisely what
mechanical bots can never do and what makes the world feel alive.

Real humans don't decide everything every second. Psychology's two-system model maps cleanly:

| System | Real-world behavior | In our world | Cost |
|---|---|---|---|
| **System 1 (reflex/habit)** | breathing, routine work, daily shopping | **deterministic bots** (buy baskets, work shifts, produce runs) | ~0 — already runs at 18 t/s |
| **System 2 (deliberation)** | voting, deals, founding, reporting fraud, journalism, policy | **LLM seats** | one call per decision |

**Trigger taxonomy (what wakes an LLM seat):**
1. **Calendar**: monthly token cycle (30 ticks) → politician/citizen-panel sessions; quarterly → audit reviews. Matches the vote-token cadence already in the engine.
2. **Event**: famine wave onset, crisis declared, price shock, attack detected, new proposal filed → the seat's *interest filter* fires (cheap bot-side predicate; the LLM only wakes when the predicate is true).
3. **Milestone**: my balance crossed a threshold, my coop went idle 20+ ticks, my good hit capacity limit → entrepreneur/adversary seats.
4. **Never per-tick**: no seat listens to raw ticks. Hard budget: **≤ ~40 LLM calls per 100 ticks** at full living-world strength; a 2,000-tick session ≈ 200–800 calls total.

Realism bonus: humans in real economies also act on events and calendars, not a metronome.

---

## 2. Interaction — "how can LLMs interact? make deals?" → three channels

| Channel | What it is | Exists today? | Binding? |
|---|---|---|---|
| **A. The market** | anonymous bids/offers, prices do the talking | ✅ fully (BID, LIST_GOOD, fair clearing, scarcity pricing) | ✅ executed instantly by clearing |
| **B. The civic board** | public proposals, votes, delegations, reports, audits | ✅ fully (PROPOSE, VOTE token, DELEGATE, REPORT, AUDIT events) | ✅ via RULE_CHANGE / policy adoption |
| **C. Deals** | negotiated agreements between named parties ("I'll supply you bread weekly at X if you supply me power") | ❌ **NEW — the deals layer** (design below) | ✅ via escrow + reputation |

### The deals layer (the genuinely new thing)

Real economies run on *contracts*: employment, supply agreements, insurance, credit lines.
Our engine has the atomic pieces (escrow already exists for machine purchases; wages exist;
loans exist; the D18 equity injection exists) but no way for two parties to *agree* on a
multi-tick arrangement. Design (v0, deliberately small):

- **DEAL_PROPOSE {parties, terms, duration, penalty}** → **DEAL_ACCEPT** → engine enforces.
- Terms are typed, not free text: `{supply: {good, qty, price, every_k_ticks}}`,
  `{loan: {amount, interest_bp}}`, `{insurance: {premium, covers}}` — the engine validates
  and executes them tick by tick, exactly like recipes. No LLM prose in the ledger.
- **Escrow:** goods/credits locked at accept; released per tick as both sides perform.
  Default on failure → penalty to the pool or counterparty + public DEAL_DEFAULT event.
- **Reputation:** `deals_fulfilled_bp / deals_total` per party, public on the board —
  the human-world signal "can I trust this counterparty?" It gives LLM seats (and players)
  something real to reason about, and gives journalism something to report on.
- This is also the missing piece for *human* multiplayer later — deals are how players
  would interact anyway. Building it for LLMs = building it for the game.

---

## 3. Role taxonomy — "are these roles enough?" → a society's worth, staged

Mapped to real-world social functions (a society needs all of these to be *alive*):

| Seat | Real-world analog | Decides | Exists in engine? |
|---|---|---|---|
| **Adversary** 🎯 | hostile trader / hedge fund / speculator | playbook attacks, market corners, panic attempts | ✅ breaksystem.py (playbooks + attack API + leaderboard already built) |
| **Politician** | lawmaker / party leader | proposals, endorsements, crisis declarations | ✅ PROPOSE/VOTE, token politics, default-approve bots |
| **Trader** | importer/exporter | foreign trade, arbitrage, stocking | ✅ foreign.py machinery (verified, never exercised by bots) |
| **Entrepreneur** | founder | found coops where demand_ema signals gaps; negotiate supply deals | ✅ founding trigger + capacity signal; deals layer = new |
| **Journalist** 📰 | press / commentator | publishes "stories" on digest anomalies (price spikes, wealth concentration, deal defaults) → shapes what other seats and players see | ⚠️ needs only a digest+publish surface — no new economics |
| **Auditor** | watchdog / external audit | requests audits, chases REPORT trails, flags odd flows | ✅ audit machinery + REPORT bounties exist |
| **Crisis council** | emergency committee | rationing choices, crisis timing | ✅ crisis.py, currently auto-ratified |
| **Citizen panel** (3–5 seats) | the public / civil society | spends tokens, delegates, voices needs — the "public opinion" that journalists cover and politicians court | ✅ vote token, DELEGATE |

**Staging:** Pilot = Adversary + Politician (RC1's game mode + governance). Living world =
add Entrepreneur, Trader, Journalist. Full society = Auditor, Crisis council, Citizen panel.

---

## 4. The API — "do we have an api for the llms?" → yes, the whole game already is one

Every actor (bot, human, LLM seat) acts through the same **Transaction API** the engine validates:

- **Economic:** LIST_GOOD, BID, WORK, PRODUCE, JOIN_COOP, LEAVE_COOP, BID_FOR_COOP (coop takeover!), BUY_LAND, SELL_LAND
- **Civic:** PROPOSE, VOTE (token-weighted, splittable), DELEGATE, REPORT (whistleblower)
- **Institutional:** RULE_CHANGE (validated full-params, deep-merge, activation tick — per the Policy Lab rules), crisis levers, foreign-trade actions
- **Attack API:** breaksystem playbooks + attack_tick + round_verdict scoring, already used by test_attack_api.py

What the engine **guarantees**: illegal actions are rejected with a public reason; money
conservation is enforced; every accepted action lands in the hash-chained ledger. **An LLM
physically cannot cheat — it can only make moves the referee allows.** What's missing is not
an API, it's the **persona harness**: digest-builder (compact world view per seat), decision
recorder (LLM output → Transaction batch, recorded for replay), and seat scheduler (trigger
predicates from §1). That harness lives *outside* the engine — zero engine changes for the pilot.

---

## 5. Realism mapping — real world vs our game

| Real-world thing | Our counterpart | Status |
|---|---|---|
| Habits, routine work | deterministic bots (System 1) | ✅ |
| Deliberation (System 2) | LLM seats on event/calendar triggers | this design |
| Prices as information | scarcity pricing + open board | ✅ |
| Contracts & trust | deals layer + escrow + reputation | new (§2C) |
| Lawmaking | proposal → token vote → RULE_CHANGE | ✅ |
| Fraud exposure | REPORT bounties + public audits | ✅ (needs LLMs to exercise it) |
| Media / narrative | journalist seat + public stories | new surface, no economics |
| Financial crises | adversarial attacks + crisis mode | ✅ engine; needs smart attackers |
| International trade | foreign-trade machinery | ✅ engine; needs traders |
| Class dynamics / politics | wealth tax, dividends, votes | ✅; LLM seats finally make it *contested* |
| "The market" as aggregate | clearing + heat-cards + chronicle | ✅ |

Honest gap list (things real societies have that we deliberately DON'T for RC1): crime beyond
rule-attacks, families/dynasties, culture/ideology drift, war. Park these — each is a future
milestone, not a hole in this design.

---

## 6. Determinism, cost, and where it runs

- **Replay:** LLM decisions are recorded as ledger inputs (like a chess move list). Replay
  re-feeds recorded decisions → byte-identical. Survival gates stay bot-only; LLM sessions
  are labeled behavioral scenarios in STUDY_PLAN.
- **Cost:** ≤ ~40 calls / 100 ticks full-strength; 2,000-tick session ≈ 200–800 calls. On the
  GPU PC via Ollama = **free**; model choice via the existing model-candidate-testing battery
  (cheapest adequate model wins). API models as fallback.
- **Where:** harness runs beside the engine (same process, off-tick), GPU PC hosts models;
  heavy sim batches unchanged (memrun / REMOTE_SIMS.md rules still apply).

---

## 7. Phased plan (folds into the RC1 month without breaking it)

| Phase | When | Content | Exit gate |
|---|---|---|---|
| **P0 — Persona harness** | Week 1–2 (parallel to UX work, spec `2026-09-19-llm-seats.md`) | digest-builder, seat scheduler, decision recorder, ONE adversary seat wired to breaksystem | 100-tick session: adversary attacks recorded, replay byte-identical, zero engine changes |
| **P1 — Adversary pilot** | Week 3 | LLM adversary vs 966-citizen world, 3 attack rounds, leaderboard entry | verdict in STUDY_PLAN; any exploit found → fix + gate |
| **P2 — Politician + panel** | Week 3–4 | token-voting LLMs, crisis deliberation; compare vs default-approve baseline | politics comparison note |
| **P3 — Deals layer** | post-RC1 (spec first) | DEAL_PROPOSE/ACCEPT + escrow + reputation, entrepreneur + trader seats | deals test suite + conservation proof |
| **P4 — Full living world** | post-RC1 | journalist, auditor, citizen panel; persistent MMO roles | the "world feels alive" demo |

---

## 8. Risks

- **Model idiocy:** small local models may act randomly → battery-test first, keep scripted
  bots as the floor for comparisons; LLM sessions never gate engine changes.
- **Goodhart on drama:** LLMs optimizing visible metrics could act weirdly human-unrealistic;
  mitigations: persona prompts + historian-style post-run review by us.
- **Determinism drift:** ANY temptation to call the LLM during apply_tick must be refused —
  decisions only pre-tick, recorded, then applied. Tripwire: byte-identity test per session.
- **Scope creep:** the deals layer is the only new economics; everything else wires existing
  mechanics. If the month slips, deals layer moves out, nothing else does.

## 9. Founder decisions
1. Approve this design as the living-world direction (P0–P4 staging).
2. Deals layer in- or post-RC1? (Recommendation: post-RC1 — it's new economics; RC1 ships with seats on existing mechanics.)
3. First model to battery-test on the PC via Ollama (candidate: qwen3 14–30B class)?
