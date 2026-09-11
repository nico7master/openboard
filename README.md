# Open Board Economy

A headless, deterministic economic engine proving **Open Board Market Socialism** — a transparent append-only ledger economy of worker cooperatives, production recipes, auction markets, surplus redistribution and democracy — with multiplayer games as frontends on top.

**Protocol, not a game:** the economy is a verifiable integer engine (spec-driven, hash-chained ledger, exact money conservation) that bot-driven simulations must prove stable *before* humans play.

## Status (2026-09-11)

| Milestone | State |
| --- | --- |
| Core engine (ledger, coops, recipes, markets, democracy) | ✅ proven |
| Hardcore survival gate (unequal 50/50 start, 21M fixed supply) | ✅ passed, 3 seeds |
| Policy harvest — 54/54 winnable wealth-tax × dividend paths (top-1% 50% → 5.2%) | ✅ proven |
| Scale: 966-citizen stability gate (worst essential streak 48 ≤ 50, invariant exact) | ✅ passed |
| Multiplayer: 12 seats × 1,000 ticks, 100% action throughput | ✅ passed |
| Game layer: Break-the-System v2 + onboarding quest (playable WebUI) | ✅ shipped |
| Realism contracts L1–L6 (interest, scarcity pricing, R&D→productivity, land + Georgist LVT, foreign sector, regional markets) | ✅ landed, 29 contract tests |
| Performance (≥5 ticks/s @ 1,000 citizens) | 🔧 1.77 t/s, ladder in progress |
| Cardano preprod anchoring | ⏸ deferred by design (pre-anchor window used for hash-format upgrades) |

**465 tests green.** Every feature lands with a gate: survival, conservation, determinism (byte-identical replay proofs), and effect-fidelity contracts (each policy must reproduce its documented real-world direction/mechanism/magnitude/flips).

## Layout

| Path | Content |
| --- | --- |
| `src/openboard/` | The engine: ledger, state, rules, markets, bots, land, foreign, regions, research, crisis, anchor |
| `dashboard/` | Flask WebUI + game server (playable) |
| `tests/` | 465 gates: conservation, determinism, realism contracts, API |
| `scripts/` | Gates, benches, profilers, sweeps (`memrun.sh` = resource-capped launcher) |
| `sweeps/` | Banked evidence: gate logs, policy heat-cards, fidelity runs |
| `docs/` | Source model (verbatim), specs, plans, incident briefs, handoff |

## Run

```bash
python -m venv venv && . venv/bin/activate
pip install -e .
pytest -q                       # 465 gates
python dashboard/server.py      # WebUI on :8421
```

Heavy runs: `bash scripts/memrun.sh <GiB> <log> <cmd>` (memory-capped, CPU-pinned — the framework shares this container).

## Docs

- `docs/source/open-board-market-socialism.md` — the authoritative model
- `docs/ideas/engine-as-law-referee-predictor.md` — the deployment thesis
- `docs/ideas/scaling-doctrine-hierarchy-of-computation.md` — how this scales to millions
- `docs/HANDOFF.md` — living state snapshot
