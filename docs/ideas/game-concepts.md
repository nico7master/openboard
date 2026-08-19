# Game Concepts — Saved Ideas

> Saved 2026-08-19 from the first brainstorming session. All five concepts are kept for later; the recommended path is recorded below. Nothing here is discarded.

## The Spectrum

| # | Concept | What it is | Best for |
|---|---|---|---|
| **A** | **Society Simulator** | Democracy 3 meets Dwarf Fortress — you steer an economy of agents, watch the Open Board react | First playable proof of the core |
| **B** | **Round-based Market Game** | 4–8 players, 45-min rounds: form co-ops, produce, bid in open auctions, vote surplus allocation. Digital board game | Rapid playtesting of economic balance |
| **C** | **Cooperative Colony Builder** | Multiplayer Factorio/Anno-style — shared ownership of factories IS the mechanic, market layer is democratic | Most natural "game" fit, medium scope |
| **D** | **Persistent Economy MMO** | EVE Online's player-driven economy, but socialist — labor time tracked as play, public dashboards, real scarcity | The long-term vision / ultimate proof |
| **E** | **"Break the System" adversarial mode** | Red team (hoarders, fraudsters, exploiters) vs. blue team (auditors, oversight) — a CTF for economics | Gamified stress-testing of the core — genius test tool disguised as a game |

## Recommended Path

**Core engine → E (stress-test as a game) → B (fast human playtesting) → C (first "real" game) → D (the dream).**

Concept **C** is the strongest standalone game: production chains generate real gameplay *and* real economic data simultaneously — the game and the testbed become the same thing.

## Underlying Architectural Principle (applies to all games)

Build the economy as a **protocol, not a game**: a headless, deterministic economic engine (ledger, cooperatives, production recipes, auction markets, surplus redistribution, voting, audits). Every action = a transaction on a transparent append-only ledger. Bot-driven simulations prove stability before any human plays. Games and dashboards are just frontends on top.

## Open Question (blocks engine design)

What does "crypto base system" mean?
1. Real blockchain (smart contracts, e.g. Solidity)
2. Cryptographic transparent ledger — hash-chained, append-only, publicly verifiable, server-side *(recommended: keeps speed/control for testing, portable to a real chain later)*
3. Plain in-game economy (no cryptographic layer)
