# Vision & Growth Path

> Saved 2026-08-19. Founder directives and decisions captured during the design phase. These are binding long-term goals — check them before every major design decision.

## North Star

1. **Prove it first, then go live.** Testing before going live is non-negotiable — bot simulations must demonstrate stability before any human or real value is involved.
2. **Grow into the real world.** If the system proves stable and fun, it should graduate from game to real-world protocol and find adoption. Every design decision must stay compatible with this path.

## Decided (2026-08-19)

- **Real blockchain: Cardano (ADA).** Chosen for: determinism (eUTXO), predictable low fees, radical transparency, Hydra L2 throughput, Paima Engine for on-chain games, democratic on-chain governance (Voltaire) — thematically aligned with the model.
- **Architecture: engine-first, chain-anchored.** Headless deterministic economic engine; bots simulate off-chain at full speed with zero fees; player actions anchor to Cardano.
- **Integration depth (assumed, confirm in spec): game actions on-chain, deterministic engine off-chain** — Paima-style: players submit moves as L1 transactions; the engine applies them deterministically; anyone can re-execute and verify the state.

## Position on Cardano — not a classic sidechain

| Layer | What it is | Role here |
|---|---|---|
| Cardano L1 | The settlement layer, fully public | Anchors player inputs, holds the verifiable Open Board history |
| App-specific L2 (Paima-style) | Deterministic state machine driven by on-chain inputs | Runs the economic engine off-chain; re-executable by anyone |
| Hydra head | State channel for instant, near-zero-fee volume | Fast auction bidding among participants |
| Partner chain (later, optional) | Own chain bridged to Cardano | Only if scale ever demands full graduation |

## Funding & investment philosophy (open topic)

- **Project Catalyst** (Cardano's democratic innovation treasury) is the most thematic match — the real-world version of the model's Innovation Fund. Milestone-based grant applications are a natural path.
- **No private equity model.** Funding must not recreate private profit extraction that the model rejects. Socialist-compatible forms to explore: crowdfunding/donations, repayable bonds from future surplus, deposit/withdraw at cost.
- **Real-value phases need legal review.** Early phases stay testnet/play-money; real ADA flows only after stability is proven and the regulatory picture is checked (jurisdiction-dependent).

## Growth Ladder

1. Bot simulations — prove stability, zero fees, deterministic replays
2. Testnet game — starting with adversarial "Break the System" mode
3. Mainnet game — real ADA, deposit/withdraw at cost, real scarcity
4. Open protocol specification — chain-agnostic spec so others can implement and audit
5. Real-world pilot — a worker cooperative or community running internal accounting on the protocol
6. Adoption — platform co-ops, municipalities, complementary-currency networks

## Design Constraints Implied by the North Star

- **Protocol before game:** every game mechanic must map to a real economic mechanic — no un-simulatable shortcuts.
- **Realistic economics:** labor-time accounting, energy and material constraints are first-class, so simulation evidence is meaningful for real-world claims.
- **The transparency/audit story is the adoption argument.** The Open Board must be verifiable by third parties from day one.
