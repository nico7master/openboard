# Open Board Economy

A side project to design, simulate, and prove the **Open Board Market Socialism** economic system — and then turn it into multiplayer games.

## Status

**Phase 0 — Workspace & Design.** The economic model is captured (see `docs/source/`), game concepts are saved (see `docs/ideas/`), and the foundational architecture decision is pending:

> **Open decision:** What does "crypto base system" mean here?
> 1. Real blockchain (smart contracts)
> 2. Cryptographic transparent ledger — hash-chained, append-only, publicly verifiable, server-side *(recommended)*
> 3. Plain in-game economy

## Core Architectural Principle

Build the economy as a **protocol, not a game**: a headless, deterministic economic engine (ledger, cooperatives, production recipes, auction markets, surplus redistribution, voting, audits) with games and dashboards as frontends on top. Bot-driven simulations prove stability before humans ever play.

## Repository Layout

| Path | Content |
| --- | --- |
| `docs/source/` | The original Open Board Market Socialism model, verbatim |
| `docs/ideas/` | Saved game concepts and creative directions |
| `docs/superpowers/specs/` | Approved design specs (created after brainstorming approval) |

## Roadmap

1. **Design phase** — answer the crypto question, brainstorm the engine design, write the spec
2. **Core engine** — headless economic protocol with transparent ledger
3. **Simulation** — bot-driven stress tests proving stability
4. **Games** — starting with "Break the System" adversarial mode and the round-based market game

## Working Rules

- All work happens inside this project directory
- The brainstorming hard-gate applies: no engine implementation before an approved design spec exists
- Design decisions are recorded in `docs/superpowers/specs/` before implementation
