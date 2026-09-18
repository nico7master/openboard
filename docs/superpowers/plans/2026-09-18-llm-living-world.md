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
- **Cost:** ≤ ~40 calls / 100 ticks full-strength; 2,000-tick session ≈ 200–800 calls. **Model decision (founder, 2026-09-18): 11 GB VRAM rules out local big models — seats run on CHEAP ONLINE models.** Battery shortlist: Mercury 2.5 (fast diffusion, very cheap), Gemini Flash-class, DeepSeek chat, Groq-hosted Qwen/Llama (keys already in env), Together-hosted Qwen. Judge on a playtest rubric: legal-move rate vs the engine validator, goal persistence across a session, cost + latency per session. Cheapest adequate model wins; ~0.5–1.5M tokens/session ≈ **$0.10–0.50 per session** at cheap-tier prices, potentially $0 on free tiers. One SMALL local model (7–8B, Ollama) stays useful only as the **zero-cost plumbing dummy** for shaking out harness bugs (digest size, malformed actions, recording) before spending online tokens.
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

---

## P0 COMPLETE (2026-09-18) — Adversary Seat Is Live

**Founder lock-in:** Mercury via A0 Venice API. Built and verified the same day.

### What ships

| Component | Path | Notes |
|---|---|---|
| Seat harness | `src/openboard/llm_seat.py` | digest builder, Venice client, robust JSON parse, transaction mapper (exact validator schemas), session recorder |
| Session driver | `scripts/llm_attack_session.py` | `--record` (Mercury decides) / `--replay` (recorded decisions re-fed, zero model calls) |
| Offline tests | `tests/test_llm_seat.py` | 8 tests, fake client, no network |
| Live evidence | `sweeps/llm_seat/session_20260918_144704.json` | Mercury played a real round; A/B replay matched byte-for-byte |

### Model wiring facts (cost us two probes to learn)

- Endpoint accepts **`mercury-2`** (not `mercury`, not `mercury-2.5`).
- Mercury is a diffusion model with hidden chain-of-thought: at `max_tokens=600` the reasoning budget consumed ALL tokens and content came back **empty**. Fix: `venice_parameters.disable_thinking: true` + `max_tokens=1200`.
- Cost so far: the entire live session cost **$0.00** (measured `cost.usd: 0.0`).

### Real bug found and fixed (pre-existing, game-level)

`attack_score`/`round_verdict` counted **all** state flags as attacker damage. Background bots' baseline FREE_RIDER flags hit 49 by tick 1 → every B2 round "stopped_by_system" instantly. The API tests passed only because they ran 1–2 ticks. Fix: flags are attributed by `target` — only flags against the attacker count as YOUR damage; `all_flags` kept for the scoreboard. The game's own contract now holds: *flags are the system catching you.*

### A/B determinism proof (the core rule, verified with a live LLM)

| Run | Model calls | Verdict |
|---|---|---|
| Record | 2 | ticks 9, flags 1 (FREE_RIDER), gini 817, damage 110, invariant OK |
| Replay | **0** | **identical** — same ticks, flags, gini, damage, invariant |

LLM decisions are recorded as inputs; replays are byte-identical. Survival gates stay bot-only.

### Verification

Full regression: **520/520 passed** (7:52 memrun). Offline seat tests: 8/8. Live session: invariant intact, attacker-attributed flags only.

### Next (P1)

Full 200-tick record session (~10–20 LLM calls, still $0-class cost) → leaderboard entry for `llm_adversary` vs playbook bots; then P2 (politician + citizen panel seats) per the plan above.

### P1: FULL SESSION COMPLETE (2026-09-18, mercury-2-5)

**Founder asks answered:** correct id is `mercury-2-5` (dash form); token/cost accounting now built into every session; full 200-tick session played.

**Session economics (session_20260918_155952.json):**

| Metric | Value |
|---|---|
| LLM calls | 199 (one per tick) |
| Input tokens | 320,419 (~1,610/tick) |
| Output tokens | 25,544 (~128/tick) |
| Cost as reported by endpoint | **$0.00** |
| Wall time | 238.4s (~4 min for a full round) |
| Malformed replies survived | 3 (hardened: pass-turn, counted) |

At typical cheap-tier paid pricing (~$0.10/M in, ~$0.30/M out) a full session would be ≈ **$0.04** — the living world is economically trivial to run.

**Game result:** Mercury-2.5 survived the full round as a real adversary: damage 520 (5 flags: FREE_RIDER + HOARD, Gini 2637bp), invariant intact. First LLM leaderboard entry vs playbook bots.

**Engineering fixes landed:** decision cadence bug (`tick % 1 == 1` never fired — one decision was replayed 200 ticks; now `(tick-1) % every == 0`), malformed-reply resilience (pass-turn + count, like a human losing a turn), per-call usage capture, session-level accounting block.

**Determinism at scale:** full-session replay = byte-identical verdict (199 ticks, 5 flags, damage 520, gini 2637) with **0 model calls** in 0.4s-class wall time.
