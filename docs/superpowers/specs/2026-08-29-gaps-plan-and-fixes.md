# Gaps Plan & What-Doesn't-Work Investigation (2026-08-29)

Mandate: plan the world-government improvements (all except wage
bargaining), plan the game items, investigate the measured weaknesses.
Research/planning only — no implementation in this pass.

## Part C — investigation of what doesn't work well

### C1. Dividend channel: re-diagnosed as THROTTLED, not dormant

Fresh probe (seed 42, 986 citizens):

| tick | pool | dividends_paid | services_paid | wealth_tax_in |
|---|---|---|---|---|
| 100 | 435 | 0 | 27,750 | 925,399 |
| 200 | 2,438 | 0 | 71,015 | 1,794,519 |
| 300 | 4,196 | 0 | — | — |

The pool crosses the min_pool_buffer (500) around t120 and grows steadily.
But dividends stay 0 while services (5,000 bp share) draw first, because:
1. services_share (50%) >> dividend_share (10–30%) — services are paid
   from the same pool first
2. `max_dividend_per_tick` = 200 cr TOTAL for all 986 citizens (~0.2 cr
   per citizen per tick even when the pool is full) — an absolute-
   denominator param tuned at 14-citizen scale

**Fix plan:** make every total-denominated param per-capita or
population-scaled (see C2); rebalance default dividend_share vs
services_share; consider a per-capita dividend floor before services.

### C2. Absolute-denominator knobs — the general bug class

Found mis-scaled: `labor_pool_cap` (fixed hours, collapse at 1k citizens),
`max_dividend_per_tick` (200 cr shared by everyone). **Plan:**
1. Audit all OPTIONAL_PARAMS for totals (hours, credits, stocks) vs rates
2. Add population scaling at genesis for any retained total-params
3. Regression test: hardcore gate at 100 and 1,000 citizens must both
   pass with the same per-capita params — no silent mis-scaling again

### C3. From-zero bootstrap starvation (~200-tick transient)

Plan: turn the current genesis seeding (founding capital, equipment,
3-day pantry) into a **votable `genesis_package` rule param**. Effects:
- 'Start from nothing' becomes an honest difficulty setting (leaner
  transient, society-visible)
- The community itself chooses its founding package — on-model
- Test: from-zero with a minimal package must clear essentials within a
  stated bound (new gate)

### C4. Service wobble (maintenance/meat streaks ≤30)

Cause: lumpy discrete production runs vs smooth daily quotas, FCFS clearing.
Plan: EMA-based production targets (want_produce uses rolling consumption
average), small buffer-stock targets for essential services, optional
staggered production scheduling. Gate: essential streak bound stays ≤30
with less oscillation in God View.

## Part A — world-government improvements (wage bargaining EXCLUDED)

### A1. Financial depth package (highest priority)

**Credit union**
- New entity type: `credit_union` coop, capitalized by member deposits +
  a votable slice of the surplus pool
- `LOAN` action: citizen/coop borrows against documented future labor or
  proven production capacity; integer repay schedule with 0% base rate
  (a small service fee is votable)
- Engine: new ledger entries (LOAN_ISSUED, LOAN_REPAY), outstanding-loans
  register, money invariant unchanged (loans move money, never mint)
- Default risk: missed repayments flagged; chronic default blocks new
  loans; the fund absorbs losses (socialized risk, democratically governed)

**Mutual insurance pool**
- Votable premium (bp of wage) → insurance pool; shock-indexed payouts
  (drought/pandemic tiers from the existing shock engine) pay members
  automatically by verified shock impact
- Crisis override applies: in declared crisis, payouts switch to need-based

**Rainy-day accounts**
- Citizens may earmark balance into a locked account (no self-loan),
  withdrawable only on verified hardship (unmet essentials N ticks)
- Gives individuals shock-smoothing without credit

Gate: economy with credit+insurance survives the 'harsh' shock tier with
LESS unmet need than without; loans never break the money invariant; no
credit spiral (outstanding debt capped at votable % of money supply).

### A2. Emergent entrepreneurship

- Shortage detector (exists in God View alerts) becomes an agent signal:
  citizens with savings + free hours may FOUND_COOP when a good shows
  chronic unmet streaks (votable threshold)
- Founder stakes capital, recruits members (JOIN_COOP by choice, not
  assignment), leadership = founder initially, replaceable by vote (D8)
- Gate: seed a world missing one essential good → a co-op emerges for it
  within N ticks without any script; failures wind down gracefully

### A3. Delegative democracy for ALL votable params

Generalize the Stage 5 research loop:
1. Algorithmic proposal layer: published formula reads live signals
   (shortages, Gini, pool levels, shock state) → proposes rule changes
   each cycle
2. Citizens: vote direct, delegate (revocable, per-topic), or abstain
   (default weight follows the algorithm)
3. Everything remains votable/editable — including the algorithm itself
   (constitutional guard applies)

Implementation: extend politics.py archetypes to delegate-aware voters;
new DELEGATE action; per-topic delegation registry; replay stays exact
(delegation is just vote computation). Gate: delegated outcomes track
expert positions on test scenarios; recall works mid-window.

### A4. Geography & finite resources

- Tile/region layer: resource nodes (ore, water, arable land) with
  depletion and regeneration rates
- Transport cost: distance-weighted auction clearing (adds 'location'
  dimension to markets); coops have locations; citizens commute
- Territorial model for 'one country first': a region adopts OpenBoard
  rules; neighbors trade at boundary markets
- Gate: resource depletion drives migration/adaptation without collapse;
  determinism preserved (static map per seed)

### A5. Outside world

- Trade partners with exogenous prices (votable tariffs); migration in/out
  (new citizens bring stakes; emigrants withdraw) — demographics extension
- Rival-system comparison metrics: a shadow 'market economy' run beside
  the OpenBoard region for the takeover narrative

### A6. Votable monetary policy

- Move mint/retire rates (wage mint cap, backstop retirement, demurrage?)
  into ruleset params under PROPOSE/VOTE with constitutional bounds
- Inflation/deflation guardrails as auto-flags (Oversight Council signals)

### A7. Justice system

- `GRIEVE` action: any citizen files a grievance citing an event/flag
- Council docket: trials (evidence = ledger events), outcomes: fine,
  restitution, restorative labor, dismissal
- Appeal path: second vote by a random citizen jury (deterministic seed)
- All justice actions are ledger events — auditability is the point

## Part B — game items

### B1. Accounts + concurrency (multiplayer foundation)

- Session-based auth in the Flask server (login → citizen binding);
  multiple humans seated simultaneously; WebSocket push instead of 1s poll
- World list + join links; spectator mode

### B2. 'Break the System' playable mode

- Human picks an adversary role with the PROVEN attack toolkit: hoarder,
  wash-bidder, faction organizer, wage-mint exploiter, governance capturer
- Objective: break an invariant/trigger a flag within N ticks; the world
  democracies (other players or bots) defend
- Uses the exact attack classes from the Stage 2 adversary lab as levels
  (tutorial = the lab itself)
- Scoring: damage dealt vs ticks used; leaderboard per scenario seed

### B3. Pacing & UX

- Speed presets: pause / 1x / 5x / max (autoplay interval presets)
- Notification toasts for seat-relevant events (wage, unmet, vote closing,
  shock declared) + a notification center
- Mobile-friendly layout pass

### B4. Onboarding quest

- First-session guided path: work 8h → buy bread → eat → vote on a live
  proposal → found/join a coop, each step gated with explanation
- Written from the Citizen Seat affordances (already computed per state)

### B5. Persistence & campaign

- Named worlds + save/load list; shareable world summary (seed + params
  hash, verified by anchor protocol later)
- Long-run campaign mode: continuous world with seasons

## Recommended build order

1. C2 (param-scaling audit) — unblocks honest sweeps and A1's design
2. A1 financial depth (credit union first)
3. A2 entrepreneurship (short, high visibility)
4. A3 delegative democracy (extends existing politics)
5. B2 Break-the-System mode (uses adversary lab directly)
6. B1 accounts/concurrency (multiplayer gateway)
7. A4–A7 geography/outside-world/justice, B3–B5

Each item gets its own brainstorm → spec → plan → implementation cycle
with a gate, per the project workflow.

---

## Build log (2026-08-29, autonomous execution)

| Item | Commit | Tests |
|---|---|---|
| C2 per-capita dividend cap (fixes 200-cr TOTAL throttle at scale) | `2944e97` | 4 |
| Schema fix: optional `max_dividend_per_citizen_tick` accepted (also repairs 3 politics tests) | `2251529` | — |
| A1 credit union (LOAN/REPAY, pool-funded, fee->pool, defaults flagged) + seat affordances | `d339897` | 10 |
| A2 emergent entrepreneurship (shortage-detecting FOUND_COOP) | `0152f92` | 5 |
| A3 delegative democracy (DELEGATE, tally expansion, cycle-safe) | `63f57f2` | 7 |
| B2 Break the System (playbooks + scoreboard + API) | `0aecaae`, `2431655` | 9 |
| B1 accounts + concurrency (PBKDF2, tokens, one-citizen-one-seat, 2-humans-same-tick proof) + API | `1032942`, `4df276e` | 9 |

Replay safety: every engine change is behind an optional rule param
(absent = off = old worlds replay byte-identically).
