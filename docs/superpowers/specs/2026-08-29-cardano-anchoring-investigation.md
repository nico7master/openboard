# Cardano Anchoring — Deep Investigation (research only, no implementation)

Date: 2026-08-29. Mandate: investigate deeply, implement nothing.
Question: how do we anchor OpenBoard's daily anchor chain (anchor.py:
{day, merkle_root, prev_anchor}) to Cardano, at what cost, with which
mechanism, and how does this map to the game vision (Hydra/Paima)?

## 1. What we already have (protocol layer, Phase 8 — done)

- `tick_commitment(tick, state_hash, ledger_head)` — one sha256 commits
  the full world state AND the full ledger prefix per tick.
- `merkle_root(commitments)` — deterministic binary merkle root.
- `build_anchor(day, commitments, prev_anchor_root)` — CBOR-safe message,
  strings/ints only, each anchor chaining to the previous root.
- `verify_anchor(...)` — anyone with the ledger + the on-chain anchor
  can verify. Tampering with ANY historical tx breaks the root.

> **2026-09-01 update (Midnight City lessons):** for anchor v1.5, also
> embed `rules_hash`, `engine_version`, and `tick_height` in the anchor
> message — making each anchor a *reproducibility* commitment (the state
> is the output of a specific deterministic engine version), not just a
> data commitment. See docs/ideas/2026-09-01-midnight-city-comparison.md.

The design is exactly the production pattern used by audit-trail systems:
merkle-tree the data, post only the root on-chain (Cardano's own docs
recommend this for larger datasets).

## 2. Costs (measured against live 2026 data)

| Item | Figure | Notes |
|---|---|---|
| Fee formula | 0.155381 ADA + 0.000043946 ADA/byte | docs.cardano.org fee structure |
| Typical anchor tx | ~0.164 ADA | small metadata tx |
| ADA price (Aug 2026) | ~$0.17–0.26 | varies |
| Cost per anchor | ~$0.03–0.05 | one tx/day |
| Annual cost (daily anchors) | **~$11–18/yr** | utterly negligible |
| Batched (per-tick anchor, 500t/day) | ~$1.80–2.50/day | unnecessary; daily is enough |
| Aiken validator tx | base fee + ExUnits | only needed if on-chain enforcement wanted |

Conclusion: metadata anchoring costs effectively nothing. Even hourly
anchors (<$500/yr) would be affordable. Cost is NOT a constraint.

## 3. Mechanisms compared

| Mechanism | What it gives | Cost/complexity | Verdict |
|---|---|---|---|
| **Metadata-only tx** (label via CIP-10 registry, e.g. custom label like Orynq's 2222) | Immutable timestamped commitment, publicly verifiable by anyone with the ledger | ~0.164 ADA/tx + free API tier | **RECOMMENDED for v1** — zero smart-contract risk, our anchor.py messages already fit |
| **CIP-20 (label 674) message** | Standard message format; human-readable in wallets/explorers | Same as above | Could wrap our anchor JSON inside 674 msg for readability |
| **Aiken validator** | On-chain enforcement (e.g., only our wallet can post anchors; escalation-of-constraint games) | Script dev + ExUnits fees + audit burden | LATER — adds nothing to verifiability of a passive commitment |
| **Paima Engine** | Game state on L2, stateful NFTs fully on-chain, cross-chain wallets (Whirlpool) | Engine integration; open-source (1.4M Catalyst grant) | For the GAME layer, not the proof layer |
| **Hydra head** | Near-instant tx inside a head, L1 settlement of outcomes; 1M TPS demoed; node v1.0 shipped | Node ops, head lifecycle complexity | For multiplayer game actions, not for daily proofs |

## 4. Infrastructure (all free at our scale)

- **Blockfrost**: free tier, transitioning to not-for-profit (governance
  proposal to make it community/free). Koios: fully free query API.
- **Demeter.run**: free Cardano node/API platform (preview/preprod/mainnet).
- **Testnets**: Preview + Preprod with official tADA faucet
  (docs.cardano.org); faucet has had downtime windows — request early.
- Wallet: Lace/Eternl/Broadside (browser), or cardano-cli for a cold
  anchor-key setup. Server-side posting needs a hot key + tiny ADA float.

## 5. Precedents (we are not inventing anything)

- **Orynq SDK** (production): AI audit-trail merkle roots anchored to
  Cardano metadata label 2222; high-throughput receipts get hourly L1
  anchors on a partner chain. Same shape as our design.
- **Cardano-client-lib docs** explicitly recommend merkle-root anchoring
  for large datasets.
- Governance itself anchors off-chain docs on-chain (hash + URL) — the
  Voltaire pattern proves the metadata-anchor model at state level.

## 6. Funding reality (Project Catalyst, 2026)

- Pilot round (Aug 2026): 50k–200k ADA grants, 10–15 teams, free
  submission, ~2-week windows; full rounds via on-chain governance are
  a 12+ month proposal-to-approval process for multi-million ADA.
- Honest read: Catalyst is a months-long community campaign, not quick
  money. Do not anchor the roadmap to it. Bootstrapping costs (~a few
  hundred ADA) are trivially self-fundable; Catalyst is for the later
  public-facing milestone, if ever.

## 7. Recommended decision (for when we implement)

1. **v1 (proof of existence):** daily metadata transaction on Preprod
   testnet, custom label registered CIP-10 style (our own namespace),
   anchor.py message as metadata payload, posted via cardano-cli or
   Blockfrost/Mesh from a dedicated wallet. ~$0.05/day, zero contract
   risk, fully verifiable with a ~50-line verifier script.
2. **v1.5:** wrap in CIP-20 msg for explorer readability; hourly anchors
   during crisis/demo windows only (cost still trivial).
3. **Game layer (later):** Paima (stateful NFT co-op identity) and/or
   Hydra head (fast multiplayer actions) — evaluated when the game
   frontend stage begins. Anchor chain stays L1.
4. **Never (without a new spec):** putting game state or economy logic
   in Plutus contracts — our engine is the source of truth; the chain
   is the notary. This preserves determinism and replay.

## 8. Risks / open items

- ADA price volatility: costs quoted at $0.17–0.26; even 10x price keeps
  annual anchoring <$200.
- Faucet downtime (observed Aug 2026 reports) — request tADA early.
- Metadata size limit (16 KB/tx): our anchor is <200 bytes; fine.
- Key management: anchor wallet key must live somewhere; for testnet a
  plain key file suffices; mainnet later needs a funding policy decision
  (who holds the key that speaks for 'OpenBoard'?).
- Orynq-style hourly L1 anchoring exists as an upgrade path if we ever
  need sub-daily finality for public proofs.

## Sources (Aug 2026)
Cardano Docs (fee structure, transaction costs, testnet faucet),
developers.cardano.org (metadata overview, networks, funding),
cips.cardano.org CIP-20 & CIP-10, forum.cardano.org fee threads,
blockfrost.io + cgov.io (not-for-profit transition), demeter.run free
tier, hydra.family + iog.io (Hydra v1.0, 1M TPS demo), paimastudios.com,
projectcatalyst.io + cryptonomich Aug 2026 pilot round,
fluxpointstudios.com (Orynq label-2222 audit anchoring),
cardanoscan/cexplorer (live ADA price $0.17).
