# OpenBoard Economy — Engine Design Spec

**Status:** APPROVED by founder 2026-08-19
**Date:** 2026-08-19
**Source decisions:** D1–D13 in `docs/superpowers/design-decisions.md`

---

## 1. Purpose

Build a **deterministic, headless economic protocol** implementing Open Board Market Socialism: social ownership, production at cost, open auction markets, surplus redistribution, democratic rule-mutation, and radical transparency. The protocol is proven stable via bot simulations before any human plays, anchored to **Cardano** for permanent public verifiability, and designed to graduate into real-world adoption.

**North star:** prove it first, then grow into the real world. Every design decision stays compatible with that path.

**Signature pattern (applies everywhere):** automation proposes from transparent signals → democracy stays sovereign.

## 2. Non-Goals (v1)

- No real-money flows (testnet/play-money only; legal review required before mainnet value transfer)
- No graphical game client (headless engine + simulation harness + minimal CLI/API first)
- No smart-contract deployment (Cardano integration is designed-for, deferred to Phase 8)
- No perfect system (all rules are intentionally mutable — D7)

## 3. System Architecture

```
┌───────────────────────────┐  ┌───────────────────────────┐  ┌───────────────────────────┐
│  Bot simulations          │  │  Live game (later)        │  │  Experimental branches     │
│  (CPU speed, free)        │  │  day = 30 min default     │  │  (what-if analysis)        │
└─────────────┬─────────────┘  └─────────────┬─────────────┘  └─────────────┬─────────────┘
              │         action inputs (same interface)          │
              └──────────────────┬─────────────────────────────┘
                                 ▼
              ┌──────────────────────────────────────┐
              │  Deterministic Engine                │
              │  (rule-set interpreter — rules are   │
              │   versioned data, not code)          │
              ├──────────────────────────────────────┤
              │  • Ledger (append-only, hash-chained)│
              │  • Economy (production, markets)     │
              │  • Governance (votes, rules)         │
              │  • Oversight (anomaly detection)     │
              └──────────────────┬───────────────────┘
                                 │ state hashes / input log
                                 ▼
              ┌──────────────────────────────────────┐
              │  Cardano anchor (Phase 8, Paima-style│
              │  L2: inputs on L1, engine verifiable)│
              └──────────────────────────────────────┘
```

**Key properties**

| Property | Guarantee |
|---|---|
| Determinism | Same (genesis, inputs, rule-versions) → same state, bit-for-bit |
| Replayability | Anyone re-executes the input log and verifies every state transition |
| Transparency | Every transaction, bid, vote, and rule change is public on the Open Board |
| Mutability | Every rule (except the constitutional core) can be changed by vote |

## 4. Core Data Model

### 4.1 The Ledger (the "Open Board")

- **Append-only, hash-chained**: every transaction `t[n]` includes `hash(t[n-1])`. No edits, no deletions, ever (constitutional invariant — D10).
- **Transaction**: `{ tick, sender, action, payload, ruleset_version, state_hash_after, prev_hash }`
- **State hash**: after each tick, the engine commits `hash(canonical(state))` — external verifiers compare state hashes without trusting the operator.
- **Rejected transactions** are also logged (with reason codes) — failure is transparent, never silent.

### 4.2 Entities

| Entity | Key fields |
|---|---|
| **Citizen** | id, credits, labor hours (lifetime), needs profile, vote weight = 1 (always) |
| **Cooperative** | members, workplace constitution (policy), inventory, active recipes, production plan |
| **Good** | id, category, triage flag (market / essential / emergency), unit |
| **Recipe** | inputs (goods + labor hours + energy) → output good, quantity per cycle |
| **Market** | good, open bids, ask orders, clearing result per tick |
| **SurplusPool** | balance, allocation weights (votable), allocation history |
| **RuleSet** | version, parameter values, change provenance (proposal → vote → activation) |
| **Vote** | subject, options, tally method, window, result, recorded ballots |

### 4.3 Rules as Data (D7)

The engine is a **rule-set interpreter**. Rules live in versioned rule-set documents on the ledger:

- Multiplier formula parameters (D5)
- Triage flags per good (D8)
- Surplus allocation weights (D11)
- Governance styles and defaults (D6)
- Triage/auction mechanics, scarcity thresholds, audit triggers

Every transaction records the rule-set version it executed under; replay applies the historically-correct version. Rule changes are special transactions: `proposal → campaign window → vote → activation at tick N`.

## 5. The Economic Loop

Per **day** cycle (D12):

1. **Work**: citizens allocate labor hours to co-op roles. Wage = hours × multiplier(role). Multipliers auto-adjust from application/vacancy data; citizens can veto/override within a window (D5).
2. **Produce**: co-ops run recipes (labor + energy + materials → goods). Engine proposes production plans from market signals; members approve/adjust/override (D6). Cost-baseline (labor + energy + materials, incl. embodied costs) computed and published for every good — constitutional invariant (D10).
3. **Auction**: open markets per good. Bids and asks clear per tick. Sale price above cost-baseline → difference flows to SurplusPool. Below → covered by pool buffer (see §9).
4. **Consume**: citizens buy goods under triage rules — market goods: highest bid wins; essential goods: need-priority rations first, remainder auctioned; emergency goods: strict rationing while scarcity thresholds trigger (D8).
5. **Surplus allocation**: dynamic split computed from need indicators; parameters votable; override window per adjustment (D11).
6. **Govern**: season-level votes (rule changes, council elections, triage flags), plus in-day veto/override windows.

## 6. Governance & Constitution (D10)

### 6.1 Constitutional core (invariants)

1. Ledger integrity: append-only, hash-chained, no deletion
2. Radical transparency: all transactions, bids, votes public
3. The rule-change process itself (no shortcuts, no emergency powers bypassing votes)
4. One person, one vote — votes cannot be bought, weighted, or transferred
5. Production-at-cost accounting always computed and published

### 6.2 Two-phase lock

- **Bootstrap phase**: core changeable by simple majority (tuning period; nothing sacred yet)
- **Hardened phase** (after declared stability milestone): core changes need ≥2/3 supermajority + multi-day window + trial period

### 6.3 Asymmetric recovery

Reverting a change **within its trial period** requires only simple majority. Undoing damage is always easier than causing it. Rollback is a first-class ledger transaction referencing the target rule-set version, backed by the engine's per-version performance metrics (§10.3).

### 6.4 Oversight (D9)

- **Automated anomaly detection** (deterministic, auditable modules): hoarding patterns, wash-bid/price manipulation, free-riding indicators, collusion signatures → public dashboard flags
- **Elected Oversight Council** (player body, rotating terms): investigates flags, proposes interventions (hoard dissolution, fraud fines, emergency triage triggers); interventions are votable and logged

## 7. Time Model (D12)

| Unit | Contents | Simulation | Live game |
|---|---|---|---|
| **Tick** | one action batch settles | as fast as CPU allows | seconds |
| **Day** | production, consumption, wages | minutes for years | 30 min default (room-configurable) |
| **Season** | harvests, scheduled votes, council elections, rule-change windows | automated | weeks |

**Experimental branching**: replay/branch from any tick in simulation mode — rewind, change rule or inputs, diverge, compare. Live mode: one canonical timeline, no rewind (D10).

## 8. Agents & Bots (D13)

All agents (bots and humans) share **one action interface** — bots are first-class citizens.

| Archetype | Behavior | Tests |
|---|---|---|
| Honest Worker | work, buy essentials, modest saving | baseline |
| Strategic Producer | efficiency-optimizing production | price signals, co-op dynamics |
| Hoarder | buys far beyond need | scarcity triggers, audits |
| Price Manipulator | cornering, wash-bids | auction integrity, anomaly detection |
| Free Rider | minimal work, max consumption | free-rider detection, multipliers |
| Champion Voter | self-serving rule campaigns | rule-change integrity |
| Crisis Turtle | panic dumps/hoards | emergency triage, resilience |
| Collusive Faction | coordinated multi-bot bloc | anti-monopoly, vote-manipulation limits |
| Gray-Market Smuggler | bypasses official economy | exit-threat: does the system keep people inside? |
| Innovator | proposes genuinely useful changes | are good actors rewarded? |

Default population mix: 60% honest / 25% strategic / 15% adversarial (configurable per experiment).

## 9. Money & Prices (D4)

- **Currency**: abstract "credits". Accounting anchor: every issuance tied to labor time × multiplier in the ledger internals.
- **Money supply**: credits are created by wage payments (and the genesis allocation) and circulate: sales revenue funds co-op wages; the price-minus-cost delta flows into the SurplusPool, which recirculates it via public services, dividends, infrastructure, and innovation funding. Long-run stability requires pool inflow ≈ pool outflow with the reserve buffer bounded — monitored invariant (§10.3). Definitive money-retirement mechanism (credits leaving circulation) is an explicit votable rule; the conservative v1 default: **surplus beyond the reserve buffer's cap is retired** (removed from circulation), keeping the buffer the system's only standing sink.
- **Prices**: cost-baseline always published; auction clearing sets actual price; deltas flow to/from SurplusPool.
- **Shortfall handling**: if sales fall below cost-baseline persistently, co-ops draw from pool buffer; chronic deficits trigger oversight review (production sunset or recipe redesign proposals).

## 10. Testing & Proof Strategy

### 10.1 Unit & property tests
- Ledger: hash-chain integrity, replay determinism (fuzzed input sequences)
- Engine: same inputs → identical state hash (CI-enforced)
- Rules interpreter: version pinning correctness

### 10.2 Simulation campaigns
- **Stability campaign**: mixed population, 10 in-game years, standard events
- **Adversarial campaign**: each adversarial archetype at 30%+ population
- **Crisis campaign**: storms, crop failures, energy shocks
- **Constitutional attack campaign**: Collusive Factions + Champion Voters attempting rule capture
- **A/B campaigns**: parallel branches with one rule differing — the empirical engine for D7

### 10.3 Stability metrics (per season, per rule-set version)

| Metric | Target |
|---|---|
| Price stability (essentials basket) | bounded oscillation, no runaway trend |
| Availability of essentials | 100% of citizens above need floor, incl. crisis seasons |
| Unemployment / unfilled roles | transient only; multipliers close gaps within seasons |
| Inequality (credit Gini) | bounded; no dynasty formation |
| Money supply drift | issuance ≈ retirement within tolerance |
| Attack visibility | 100% of scripted attacks detected on dashboard |
| Recovery time | ≤ 1 season from crisis events |

### 10.4 Definition of "proven" (gate to live game)
All targets held across stability + adversarial + crisis campaigns, with replays published. Then: testnet game ("Break the System" first), then human playtesting.

## 11. Cardano Integration (Phase 8, designed-for now)

- **Pattern**: Paima-style app-L2 — player actions as L1 transactions; engine applies them deterministically; anyone re-executes from on-chain inputs and verifies state hashes. Not a sidechain; no own validators (D2).
- **Decision deferred until Phase 8**: adopt Paima Engine vs. custom Aiken contracts. The engine's input log and state-hash format must map cleanly to both — this constraint is enforced from Phase 1.
- **Hydra head** (optional later): fast in-head auction volume, settle summaries on L1.

## 12. Implementation Phases (layers within full scope, D3)

| Phase | Deliverable | Gate |
|---|---|---|
| 1 | Ledger core: append-only chain, replay, state hashes | replay fuzz tests green |
| 2 | Entities + rules-as-data interpreter (versioned rule-sets) | version pinning tests green |
| 3 | Production: co-ops, recipes, labor, wages, multipliers | 1 season simulates cleanly |
| 4 | Markets: auctions, triage, cost-baselines, SurplusPool | stability campaign baseline |
| 5 | Governance: votes, rule changes, two-phase constitution, asymmetric recovery | constitutional attack campaign |
| 6 | Oversight: anomaly detection + council interventions | attack visibility 100% |
| 7 | Simulation harness: 10 archetypes, campaigns, metrics, branching/A/B | "proven" gate (§10.4) |
| 8 | Cardano anchoring (testnet) + first game frontend ("Break the System") | external verification demo |

## 13. Proposed Defaults (review these!)

### 13.1 Starter goods (39)

| Category | Goods |
|---|---|
| Food (raw) | grain, vegetables, fruit, fish, meat, eggs, milk |
| Food (processed) | flour, bread, canned food, cheese, meals (service) |
| Materials | timber, stone, iron ore, coal, sand |
| Processed materials | lumber, bricks, steel, glass, fabric |
| Tools & machines | hand tools, machines, electronics, medicine |
| Consumer | clothing, furniture, household goods, books |
| Housing & energy | housing (service), electricity, heating fuel, water, transport (service) |
| Services | healthcare, education, childcare, maintenance (service) |

Triage defaults: food/housing/water/healthcare/electricity/heating = **essential**; medicine, transport = **market** with emergency escalation (auto-escalate to **emergency** when scarcity ≥ 30% below seasonal need, or by vote — D8 triage is votable); all other goods = **market**.

### 13.2 Multiplier formula (D5)

`multiplier(role) = clamp(1.0 × difficulty(role) × scarcity(role), 0.5, 3.0)`

- `difficulty`: votable per-role base factor (default 1.0; hard roles proposed higher)
- `scarcity = 1 + 0.5 × ln(max(1, applicants_ratio))` where applicants_ratio = open positions / applicants over trailing 2 seasons (unfilled roles → multiplier rises)
- Emergency boost: +1.0, auto-decays over 5 days

### 13.3 Surplus allocation defaults (D11)

| Category | Default weight |
|---|---|
| Public services (health, education, housing, childcare) | 35% |
| Infrastructure & maintenance | 20% |
| Innovation fund | 20% |
| Citizen dividend | 15% |
| Reserve buffer (crisis smoothing) | 10% |

Dynamic engine adjustments bounded to ±10 percentage points per category per season, from need indicators; every adjustment overridable by vote within its window.

## 14. Error Handling

- **Invalid actions** → rejected-transaction records with reason codes (never crashes, never silent drops)
- **Rule violations** → same: rejection + oversight flags where relevant
- **Sim bugs** → quarantined branch; comparison dashboards isolate divergences
- **Replay mismatch** → hard failure of the "proven" claim; blocks live phase
- **Chronic co-op deficits** → oversight review path (§9), not silent bailouts

## 15. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Scope creep (full economy from day one) | Phase gates; each layer independently verifiable |
| Rule-set interpreter complexity | small rule DSL, property-tested; rules versioned like data |
| Bot behavior too simplistic → false confidence | adversarial campaigns mandatory for the gate; archetype specs per phase |
| Cardano ecosystem shifts before Phase 8 | engine is chain-agnostic; anchoring is an adapter |
| Economic model embedded assumptions | every parameter votable + A/B tested (D7) — the system critiques itself |

---

**Next step:** user review of this spec → implementation plan (Phase 1: ledger core).
