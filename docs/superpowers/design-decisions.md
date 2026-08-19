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

## Open questions queue
- Q5: Multiplier governance mechanism (automated / voted / hybrid).
- Q6: Production decision-making inside co-ops (member votes vs manager roles vs algorithmic).
- Q7: Consumption allocation when goods are scarce (price rationing vs need-based priority lists).
- Q8: What "state" institutions exist in v1 (oversight body powers, intervention triggers).
