# Design Decisions — Running Log

> Working log during the brainstorming phase. Feeds the final design spec in docs/superpowers/specs/. Each entry: decision, rationale, status.

## D1 — Real blockchain: Cardano (ADA) ✅ DECIDED 2026-08-19
- **Decision:** Build on Cardano as the real blockchain layer.
- **Rationale:** Determinism (eUTXO), predictable flat fees, radical transparency, Hydra L2 throughput (1M TPS testnet 2026), Paima Engine exists for exactly this pattern, on-chain democratic governance (Voltaire) thematically aligned.
- **North star check:** Compatible with real-world graduation (partner chain later if ever needed).

## D2 — Architecture: engine-first, chain-anchored ✅ DECIDED 2026-08-19
- **Decision:** Headless deterministic economic engine off-chain; player actions anchored as Cardano transactions (Paima-style app-L2); bot simulations run free and fast before anything goes on-chain.
- **Rationale:** Prove-it-first requirement; anyone can re-execute the engine over on-chain inputs and verify the Open Board.
- **Note:** Not a sidechain — no own validators. Cardano L1 secures the input history.

## D3 — Scope: full starter economy ✅ DECIDED 2026-08-19
- **Decision:** Design target is the full economy from day one: 30+ goods, labor/energy/materials fully modeled, interventions and innovation fund active.
- **Rationale:** AI-assisted development makes the scope feasible; design everything against full scope so no layer needs redesign later.
- **Implementation note:** Built in verifiable layers (ledger → production → markets → governance), but the full economy is the definition of done for v1.

## D4 — Currency: hybrid credits anchored to labor time ✅ DECIDED 2026-08-19
- **Decision:** Plain abstract credits ("credits") as the trade currency. Underneath, every credit issuance is anchored in accounting to labor time × social multiplier.
- **Mechanism:**
  - Base: 1 hour worked = 1 credit × multiplier for the role.
  - Multipliers: 1.0 baseline, higher for hard/undesirable/scarce labor, adjusted by need and availability.
  - Multiplier governance: automated scarcity signals and/or democratic votes (open sub-question, see Q5).
  - Prices: production cost (labor + energy + materials) is the cost-baseline; open market bidding determines actual prices; difference flows to the surplus pool.
- **Rationale (founder):** Not all jobs are equal; pay must adjust for need and availability — more pay for work nobody wants, via automated or voted systems. Labor time remains the accounting basis so "production at real cost" stays meaningful.
- **Open sub-question:** How are multipliers set — purely automated, purely voted, or hybrid (auto with democratic override)?

## D5 — Multiplier governance: automated with democratic override ✅ DECIDED 2026-08-19
- **Decision:** Wage multipliers adjust automatically from scarcity data (unfilled positions → multiplier rises; oversubscribed → settles down); citizens can veto or override any adjustment by vote within a defined time window.
- **Rationale (founder):** Fast engine reactions with sovereign democratic control; the automatic formula lives transparently on the Open Board, so nothing is a black box.
- **Design implication:** The engine needs a published, deterministic multiplier formula plus a veto/override voting mechanism with a defined window.

## D6 — Co-op governance: engine proposes, members approve ✅ DECIDED 2026-08-19
- **Decision:** Default co-op governance: the engine computes suggested production plans from market signals (price trends, stock levels, demand); members vote to accept, adjust, or override each cycle; routine decisions can be auto-approved via policy. Per-co-op constitutions may select other styles (direct votes, elected managers) — internal decision style is *policy*, not *protocol*. All co-ops stay in the same shared ledger, market, and money system.
- **Rationale (founder):** "I like automations so 3 sticks out." Matches the automation-with-democratic-sovereignty pattern (D5). Not locked dogmatically — see D7.

## D7 — Rule mutability: every rule can be changed or voted out ✅ DECIDED 2026-08-19
- **Decision (meta-principle):** The system will NOT attempt to be perfect. Instead, all rules are mutable: rule-sets are versioned data committed to the ledger; rule changes are special transactions requiring passed votes; every transaction records the rule-set version under which it was processed. Multiple rule variants can run side by side (parameter sweeps in bot simulations; parallel game worlds on-chain) and be compared empirically. In-game democracy becomes the experimental laboratory — "make these decisions in game and see how it actually plays out."
- **Rationale (founder):** "We won't build the perfect system — build it such that all rules can be changed and voted out... maybe build multiple systems or plugins at the same time and then just test multiple versions."
- **Design implications:** Engine is a rule-set interpreter, not hardcoded logic (rules are pluggable modules with defined interfaces); rule-change proposals and votes are first-class ledger transactions; parallel-world comparison mode is a core feature; determinism is preserved by replaying each transaction under its active rule-set version.
- **Cardano parallel:** Voltaire governance does exactly this at chain level — economy-level rule voting mirrors the host chain's own philosophy.
- **North star check:** Empirical A/B evidence of rule variants is the strongest possible argument for real-world adoption.

## D8 — Scarcity allocation: per-good triage ✅ DECIDED 2026-08-19
- **Decision:** Every good carries a policy flag set by vote: **market good** (pure auction), **essential good** (need-priority rations to all first, surplus to auction), or **emergency good** (strict rationing when automatic scarcity thresholds trigger). Flags are votable rules under D7 — the triage itself is an experiment, not dogma.
- **Rationale (founder):** Price discovery is a good mechanic — capitalism's auto-balancing is real and worth keeping; the hybrid keeps it while fixing rationing-by-wealth in crises. "Not perfect either, but let's go for it" — imperfection is acceptable because all rules can be changed and A/B tested (D7).

## D9 — Oversight: automated audits + elected Oversight Council ✅ DECIDED 2026-08-19
- **Decision:** Engine runs automated anomaly detection (hoarding patterns, price manipulation, suspicious transactions) with public dashboards. An elected Oversight Council (player body, rotating terms) investigates flags and proposes interventions — breaking up hoards, fining fraud, triggering emergency triage. All interventions are votable and logged on the Open Board. Auditor becomes a player role in the game.
- **Rationale (founder):** "2 yes!" Checks and balances; engine speed plus human judgment plus democratic legitimacy; fully transparent actions.
- **Design implication:** Anomaly detectors are deterministic rule modules (auditable); council elections, terms, and intervention votes are first-class ledger transactions.

## D10 — Constitution: two-phase lock, asymmetric recovery, immutable history ✅ DECIDED 2026-08-19
- **Decision:**
  1. **Minimal core invariants** (ledger integrity — append-only, hash-chained; radical transparency of transactions/bids/votes; the rule-change process itself; one person one vote; production-at-cost accounting always computed and published).
  2. **Bootstrap phase:** core is changeable by simple majority — the system is being tuned and nothing is sacred yet.
  3. **Hardened phase:** after stability milestone is reached, core changes require ≥2/3 supermajority plus a mandatory multi-day voting window and trial period.
  4. **Asymmetric recovery:** reverting a change within its trial period needs only a simple majority — undoing damage is always easier than causing it. Evil actors need sustained 2/3; defenders need 50% + evidence.
  5. **Immutable history:** the append-only ledger means even a unanimous vote can never rewrite past records — worst case is fully visible on the Open Board; the system can always see what was done and when.
  6. **Evidence-based rollback:** the engine tracks performance metrics per rule-set version (price stability, inequality, shortage events), so every rule change is an experiment with data and rollback is one vote away.
- **Rationale (founder):** "A core makes sense, but I want to change the core in the beginning also... immutable first or only if 2/3 or higher, so evil players can't get rid of it... changeable but not so we can never recover. Maybe a roll back function that checks how it worked and with less effort we can roll back."
- **Design implication:** rule-set versions behave like git commits for governance — version, measure, compare, revert. Rollback is a first-class ledger transaction.

## D11 — Surplus allocation: smart dynamic engine, votable parameters ✅ DECIDED 2026-08-19
- **Decision:** Surplus split is computed dynamically by the engine from scarcity/need indicators (underfunded services → share rises), but the formula, its parameters, and category weights are votable rules (D7). Citizens can override any adjustment within a time window; the engine publishes live dashboards showing what each category received and delivered.
- **Rationale (founder):** "I want 2 and 3 mixed. I want a smart system that can be voted on."
- **Pattern:** Same signature as D5 and D6 — automation proposes from transparent signals, democracy stays sovereign.
- **Design implication:** Surplus allocator is a deterministic rule module with votable parameters; every allocation event is a ledger transaction referencing the active parameter version.

## D12 — Time: layered discrete clock + experimental timeline branching ✅ DECIDED 2026-08-19
- **Decision:** Layered discrete time — atomic **tick** (action batch settles) → **day** (production runs, consumption, wages) → **season** (harvests, governance votes, rule-change windows, council elections). Simulations run ticks at CPU speed; the live game runs a day per fixed real-time period (default proposal: 30 minutes, room-configurable — tunable parameter, confirm in spec). Every transaction is tick-stamped; replaying the ledger reproduces the world exactly.
- **Experimental mode:** timelines can be **branched** — rewind to tick N, change a rule or inputs, run a divergent branch, compare outcomes (counterfactual what-if analysis). Normal mode keeps **one canonical timeline** — no rewind — consistent with D10 immutable history. Branching lives in simulation/experimental contexts only.
- **Rationale (founder):** "2 seems to make sense. And if possible rewind time to try something else at some point in an experimental mode. But maybe not for normal mode."
- **Design implication:** engine state is a deterministic function of (genesis, input sequence, rule-set versions); branching = new input stream sharing a common prefix. Comparison dashboards are first-class.

## D13 — Simulation cast: 10 bot archetypes ✅ DECIDED 2026-08-19
- **Decision:** v1 cast: Honest Worker, Strategic Producer, Hoarder, Price Manipulator, Free Rider, Champion Voter (self-serving rule campaigns), Crisis Turtle (panic dumps/hoards), Collusive Faction (multi-bot bloc), **Gray-Market Smuggler** (bypasses official economy — tests whether the system keeps people inside it), **Innovator** (proposes genuinely useful rule changes — tests whether good actors are rewarded). Population mixes configurable (e.g. 60% honest / 25% strategic / 15% adversarial).
- **Rationale (founder):** "Sure for now this is fine. If you don't have any other types, I depend on your intelligence." Agent additions: Smuggler (exit threat is real for any alternative-economy system) and Innovator (adversarial-only casts can't prove the system *works*, only that it resists attacks).
- **Design implication:** Bots are pluggable agents with the same action interface as human players — they double as the adversarial content of the "Break the System" game mode.

## Open questions queue
- (empty — all brainstorm questions resolved; ready for spec assembly)


### 2026-08-22 — Circular flow closure (patronage + capital rent)

- **Co-op patronage dividends**: co-op treasury surplus above a 1,600 cr
  operating buffer returns 50%/tick to worker-members. Rationale: treasuries
  are socially-owned conduits, not hoards; dead money in treasuries broke
  the circular flow (Gini 0.541 with frozen 21k miner treasury).
- **Use-based capital rent**: consuming a machine as recipe input pays
  society 1,500 cr (replacement cost) into the surplus pool. Rationale: free
  endowment capital became private rent capture — coal's cost baseline embeds
  machine depreciation the miners billed but never paid. Rent is charged on
  USE, not holdings (holding-based billing drained idle co-ops and caused
  42 unmet needs; use-based kept zero unmet while compressing Gini 0.541 ->
  0.347). Both params votable (D7 rules-as-data).
- **Gate criteria amended**: recycling (dividends + services > 0, pool
  bounded) replaces 'retirement fires >= 1' — spending-priority keeps the
  pool below the retirement cap by design; retirement stays unit-tested.

### 2026-08-22 — Hard Core: long-run survival (true cost + depreciation fund)

- **VWAP true-cost accounting** (`cost_accounting: vwap`): baselines stamp
  from co-ops' realized purchase costs (integer 1/10,000 cr moving average),
  not book values. Millers' book-cost bleed to treasury 0 was the t~800
  freeze's first cause. Off in genesis; old saves replay byte-identically.
- **Earmarked depreciation fund**: machine/tool rent flows into a dedicated
  `capital_fund`; ONLY capital refresh draws from it. Prior design let
  dividends spend the machine-replacement money — society starved its own
  capital (miners hit 0 machines). Self-balancing: 1,500 in per machine
  burn, 1,500 out per replacement (fund steady ~980 at t2000).
- **Capital refresh retirement**: public capital maintenance retires money
  from supply (77k over 2,000 ticks) — the first working money sink; also
  fixed 'retirement never fires'.
- **Solvency guard**: specialists skip PRODUCE when treasury can't cover the
  next run's inputs (prevents producing into insolvency).
- **Long-run gate**: 3 seeds x 2,000 ticks, zero unmet in final 500, Gini
  <= 0.5, utilities above floors, invariant exact (~100s).
- Result: loop 1.00, Gini 0.475 (savings-creep remains, B5-B6), machines
  sustained indefinitely, zero unmet from t1 to t2000.

### 2026-08-22 — Hardening rounds 1-2 (autonomous stress loop)

- **Progressive wealth tax** (`wealth_tax` {threshold 5,000, rate_bp 200}):
  balances above threshold pay into the pool, recycled via dividends.
  Fixed savings concentration: Gini 0.489 -> 0.232 flat, balances banded
  6.0k-6.3k. Votable rule param like everything else.
- **MARKET_POWER competition gate**: dominance flags only fire when >= 2
  coops list the good. Single-producer-per-good is structural (baseline),
  not abuse — killed 6 permanent noise flags.
- **Bootstrap pantry**: 3 days of bread/water/electricity at founding so
  the supply-chain spin-up never registers as unmet need.
- **Cumulative WORK-hours cap** (`max_work_hours_cumulative`, ephemeral
  per-tick counter, hash-safe): per-tx cap alone allowed N distinct WORK
  txs to mint N x cap in one tick. Closed with exploit test.
- **Zombie wage-farming proven bounded**: idle-pool wages are the income
  pump (D4 right-to-work), NOT an exploit — wealth tax converges a pure
  farmer to ~5,400 cr (= honest-worker equilibrium). Lesson learned the
  hard way: capping idle labor collapsed all demand (balances hit 0,
  minted 215k -> 5.7k); labor_pool_cap stays available but OFF in
  baseline, documented in code comments + regression tests.
- **scripts/stress.py**: reusable 3-seed deep diagnostic (gini path, unmet,
  velocity proxies, price-floor spreads, stockouts, flag census) — the
  harness that caught every issue above and both of my own regressions.

### 2026-08-22 — Stage 1: democracy in the loop (GATE PASSED)

- **Constitutional guard (new engine rule)**: changing governance params,
  the oversight council, or constitution phase now requires 2/3 of ALL
  citizens, not just cast votes. Motivated by the faction experiment: a
  60% bloc otherwise rigs quorum->0 then repeals anything. Ordinary
  economic rules stay simple-majority — democracy lives, capture dies.
- **Perception = visible rich-poor spread (x100), not Gini**: empirically
  the balance-Gini never crossed the trigger while the spread sat at 10x
  for 1,400+ ticks (untaxed heal run). Citizens see spread, not statistics.
- **Heal experiment PROVEN**: wealth tax removed at genesis -> society
  detects divergence by tick ~200, votes the tax back stepwise, converges
  at its OWN equilibrium: 900bp (society chose 4.5x the designer's 200bp
  and stayed stable: gini 2,207, zero unmet, invariant exact).
- **Politics does not destabilize**: governance-active normal runs match
  the hardened baseline (gini ~2,193 vs 2,320; zero unmet final 500).
- Determinism note: seeds 42/7/123 produce near-identical political
  trajectories (same proposal counts) — political behavior is a function
  of public state, as designed.

## Stage 3 — Competition & Real Capital (2026-08-22)
- **D-S3-1: Market-priced capital baselines.** Under extended_catalog, machine/tool
  cost baselines reflect batch market reality (160/25), not legacy one-off book
  values (1,500/60). Book values leaking into VWAP fallback priced coal at 71
  and froze the downstream chain. Lesson: a cost floor must reflect what the
  good actually costs to make NOW, not what it once cost.
- **D-S3-2: Capital goods list freely.** The consumable stock buffer (10) is
  wrong for tools/machines: their purpose is sale. Buffering them deadlocked
  the toolsmith chain (8 machines held, never listed). Capital lists at any stock.
- **D-S3-3: Batch-cycle seed treasuries.** Heavy coops (steel ~800/run,
  machines ~2,200/batch) need seeds covering multiple cycles until internal
  trade reaches steady state; otherwise the chain freezes mid-flight.
- **D-S3-4: Wind power as structural competition.** wind_farm recipe is
  labor-only (zero material inputs): renewable electricity competes with coal
  power on price forever, no input dependency.
- **D-S3-5: Probe hygiene.** Timeline metrics (unmet etc.) are event-driven via
  _last_events; driving apply_tick directly makes them stale. Gates must read
  state.unmet_needs directly.
- **D-S3-6: Capital backstop as social ownership made real.** When a producer
  coop burns its last tool/machine and cannot afford a replacement, the market
  cannot save it: no capital -> no output -> no income -> permanent deadlock.
  Society's capital fund (earmarked depreciation rent) steps in as last-resort
  maintainer of the means of production — exactly the source model's principle.
  Guardrails: only proven production recipes count (no free capital for
  never-producers), booked as retirement so the money invariant stays exact,
  deterministic order, replay-safe via out-of-state cache.

## Stage 4 — breadth & genesis seeding (2026-08-24)

**Decision: society seeds founding values at genesis** (user-approved).
The live world starts with founding capital, equipment, and a 3-day pantry;
the stage-4 gate measures this REAL configuration (skip first 250t founding
window). `ZERO_START=1` keeps the from-nothing variant for adversarial study.
Rationale: the model's bootstrap-endowment rule already says society equips
its members; measuring a stripped world measured the wrong claim.

**Engine fixes landed during breadth:**
- Multi-run PRODUCE: bots scale runs to labor/inputs/stock-gap (millers idled
  19k labor-hours at 1 run/tick while the city starved)
- Producer input pass rotates service order by tick (alphabetical FCFS
  starved late names)
- Input advance priced at bot-bid parity (baseline+2); printshop deadlock
  broken — books now produce
- Buffer must stay below stock_target (teachers/builders produced-to-target
  and never listed)
- Third water utility: 2 coops left ~9 water/tick for ALL producers after
  citizen drinking — the master constraint behind bread/livestock/fabric
  starvation
- Cast rebalanced: 4 builders (housing oscillated 86 unmet), bricks target
  400, maintenance treasury 1800 (tool-burning recipe), weavers 120

**Known issue (documented, not blocking):** maintenance & meat oscillate
(maintenance 147->68->133->35 across 2,000 ticks) because the recipe burns a
hand_tool per unit and livestock shares grain with millers. Bounded, no
runaway; revisit under shocks/growth tuning.


## Stage 5 design decisions (2026-08-26)

- D5.1 Real-world demographics: births always flow (children consume, mature at ~600 ticks); pandemics kill permanently. Death only from shocks, never market outcomes (dignity floor).
- D5.2 Shock engine has intensity profiles (`peaceful`..`apocalyptic`) for future game difficulty; escalating battery is test-only instrumentation that reports the honest breaking tier.
- D5.3 Research allocation = algorithmic proposal from transparent signals + delegative citizen vote (direct/delegate/abstain-default) + universal override. Everything votable, including the algorithm itself. Linear point-splitting chosen over quadratic for simplicity/exactness (user preference).
- D5.4 Entities never fail; leadership is a replaceable role. Founders lead first; execution keeps them there. Means of production stay social.
- D5.5 Backer-priority layer REJECTED by user as too complicated/rarely useful. Crisis overrides all advantages: distribution by need during declared emergencies.
