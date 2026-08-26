# Stage 5 — Shocks, Growth & Research

Date: 2026-08-26 · Status: APPROVED (design dialogue complete) · Predecessor: Stage 4 breadth

## Purpose

Prove that the OpenBoard economy survives what the real world throws at it — disasters,
pandemics with real death, demographic change — while its research future is steered by an
algorithmic-proposal / delegative-democracy loop in which **everything is votable, including
the algorithm itself**.

Core constitutional principle (user-approved):

> Everything is a vote. Every vote is backed by an algorithm. The algorithm itself is a vote.
> Automation proposes from transparent signals; democracy always disposes.

## Scope

1. **Shock engine** — deterministic, seed-driven, escalating test battery; intensity profiles
   for later game difficulty levels (`peaceful` / `standard` / `harsh` / `apocalyptic`).
2. **Demographics** — continuous births, childhood growth delay, real permanent death.
3. **Research system** — innovation pool funded from surplus; allocation = published algorithmic
   proposal + delegative citizen vote + universal override; research centers led by replaceable people.
4. **Crisis override** — declared emergencies suspend advantages/priorities; need-based distribution;
   auto-expires; declaring/ending a crisis is itself a vote.
5. **Carry-over fix (blocking)** — miners' fallback capital ratchet must be verified closed BEFORE
   any shock test runs (shocks hammer capital chains).
6. **Gate** — `scripts/stage5_gate.py`, reusable, honest breaking-point reporting.

Out of scope: game UI difficulty selection (Stage 7+), chain anchoring of shock events beyond the
existing anchor module, human players.

## 1 · Shock engine

### Mechanism

- A `shocks` rule block holds: `enabled`, `profile` (intensity preset or `battery`), `rng_seed`.
- Each tick, a seeded PRNG (deterministic, replay-safe) may roll an event from the active profile's
  weighted table. Every event is emitted as a ledger event (`SHOCK_START` / `SHOCK_END`) so replays
  stay byte-exact.
- Shock types and effects:

| Type | Effect | Fatal class? |
|---|---|---|
| Drought | farm-sector output × (100−X)% for N ticks | no |
| Outage | electricity production disabled N ticks | no |
| Spoilage | destroys X% of all food stocks instantly | no |
| Machine failure wave | X% chance each machine-consuming run burns an extra machine | no |
| Pandemic | sick citizens contribute reduced labor hours for N ticks; severe tier kills citizens permanently | YES |
| Demand shift | one non-essential good's need weight rises/falls permanently | no |

### Real death (pandemic severe tier)

A killed citizen: balance transfers to the surplus pool, inventories return to the common pool,
co-op memberships end, needs entries removed. Death is a `CITIZEN_DEATH` ledger event. The dignity
floor is untouched: nobody dies *of poverty* — only shock events kill, never market outcomes.

### Intensity profiles

| Profile | Behavior |
|---|---|
| `off` | no shocks (default; old saves replay identically) |
| `peaceful` … `apocalyptic` | fixed frequency/severity ladders — game difficulty presets |
| `battery` | TEST ONLY: starts mild, escalates every 250 ticks until a gate criterion breaks; reports the exact breaking tier |

The battery is a testing instrument, not a world setting.

## 2 · Demographics

- **Births**: every `birth_interval_ticks` (votable; default 400), a new citizen arrives with the standard ₡500
  stake minted (money-supply event, invariant-aware). Birth rate scales mildly with population.
- **Childhood**: children consume essential needs (scaled down) but cannot WORK until age
  `adulthood_ticks` (default 600). Childhood is tracked as citizen metadata.
- **Death**: permanent removal per §1. Population therefore drifts with shocks — the economy must
  absorb both growth and loss.
- All birth/death/aging are ledger events (`CITIZEN_BORN`, `CITIZEN_ADULT`, `CITIZEN_DEATH`).

## 3 · Research system

### Innovation pool

A votable share of the surplus pool flows into `state.innovation_pool` each tick
(`research_share_bp`, default proposed by algorithm, ratified by vote).

### The allocation cycle (every `research_cycle_ticks`)

1. **Algorithm proposes.** A published, pure function computes field weights from transparent
   signals: disease prevalence, unmet-need indices, demand/supply gaps, capacity vs population.
   Output: e.g. health 38%, energy 27%, food 21%, computing 14% — reasoning visible to anyone.
2. **Citizens respond**, per citizen per cycle, exactly one of:
   - **direct vote**: split their 100 points across fields (linear, exact);
   - **delegate**: assign their vote-weight to another citizen (revocable anytime, votes public);
   - **abstain**: weight follows the algorithmic default.
3. **Aggregation**: delegated weight stacks on delegates' own choices. Final split = weighted result.
4. **Within-field allocation**: same mechanism splits each field's budget between competing research
   centers/proposals (the covid-center-vs-hearing-loss case). Any citizen or co-op may propose a
   center; founders lead it initially.
5. **Funding**: centers draw their share; spending produces research progress toward concrete
   recipe unlocks (improved variants: less labor/energy per unit).

### Leadership is a role

Entities don't fail — people do. A center whose progress stalls chronically puts its leadership up
for re-vote; any member can stand. Assets never leave social ownership. Founders start as heads
(idea + knowledge); execution keeps them there.

### Universal override

- Reject/amend any proposal: ordinary majority vote.
- Edit the algorithm itself: PROPOSE/VOTE item (formula constants, signal set).
- Temporary override: "ignore formula, concentrate on X for N ticks" — passes as an ordinary vote,
  auto-expires.

No sacred code. Constitutional guard (2/3 supermajority) applies only where Stage 1 already applies it.

## 4 · Crisis override

- Declaring/ending a crisis: citizen vote (simple majority), or auto-declared by severe shock class
  subject to post-hoc ratification vote within ≤ 100 ticks.
- During crisis: all priority advantages suspended; essentials distributed by need (fair clearing
  rotation already exists); research spending may be redirected by emergency vote.
- Crisis state is a ledger event; replay-safe.

## 5 · Carry-over blocking fix

Miners pinned at 0 machines for 250+ ticks despite correct exit-ramp bids: bids fired but never
filled. Root cause must be found (bid/listing matching or early-tick supply) and verified with a
dedicated regression test (miner recovers machines after fallback) BEFORE the shock battery runs.

## Gate criteria (`scripts/stage5_gate.py`)

All measured, not vibes:

1. **Ratchet closed**: miner re-acquires machines after fallback within ≤ 50 ticks, all seeds.
2. **Escalating battery** × ≥2 seeds: report the breaking tier honestly; below it, essentials unmet
   recover within ≤ 100 ticks after each shock ends; money invariant exact every tick; replay byte-exact.
3. **Demographics**: population grows organically in peaceful runs; pandemic deaths reduce labor
   force and the economy re-stabilizes without them; children mature into workers.
4. **Research loop**: field allocations track injected signal changes (disease outbreak shifts
   budget toward health through votes, not designer decree); delegation changes outcomes when the
   delegate is informed; algorithm edit passes as ordinary vote and takes effect.
5. **Crisis override**: declared crisis suspends priorities visibly; distribution equalizes; crisis
   ends cleanly.
6. Full existing suite stays green; old saves replay byte-identically (all new behavior rule-gated).

## Testing strategy

Unit tests per mechanism (shock PRNG determinism, death accounting, birth minting, childhood
maturation, delegation aggregation, algorithm edit flow, crisis lifecycle). Integration: scripted
mini-worlds exercising each subsystem. Gate: long-run multi-seed battery.

## Risks

- Shock × capital-chain interaction may expose new deadlocks (expected — that is the point).
- Delegation graph cycles (A→B→A): resolve by cycle detection, treat as abstain.
- Research unlock power creep: improved recipes bounded (≤20% efficiency gain per tier).
