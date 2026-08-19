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

## Open questions queue
- Q8: What "state" institutions exist in v1 (oversight body powers, intervention triggers).
- Q9: Which rules are constitutional (hard to change) vs ordinary (simple majority)? What is the immutable protocol core?
