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
