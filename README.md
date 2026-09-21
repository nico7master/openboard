# Open Board Economy

**A deterministic economic engine that proves an entire political economy runs — then lets you play it, break it, and watch it survive.**

OpenBoard implements **Open Board Market Socialism**: a transparent, append-only ledger economy of worker cooperatives, calorie-true needs, auction markets, surplus dividends, and a real voting republic. Every claim about stability is proven by bot-driven simulation *before* humans or AI actors ever touch it.

> The thesis: economics as a **protocol, not an argument**. Rules are code, transfers are integer-exact, the ledger hash-chains every event, and any world can be replayed byte-identically from its transaction log.

## The republic, in one table

| You play as | You can do |
|---|---|
| 🧑‍🌾 **A citizen** | Work a coop, earn wages, buy your basket, receive dividends, found coops, hold land under society's collective ownership (Georgist leasehold), pay/receive the land-value tax |
| 🗳️ **A voter** | One splitable, delegable, revocable vote token per month; vote on any proposal; run for trust; report violations for whistleblower rewards |
| 🎯 **An adversary** | Break the System mode: hoard, corner markets, free-ride, wage-mint, dump land — the engine scores your damage and the oversight system hunts you |
| 🤖 **An AI seat** | Mercury-2.5 plays politician and adversary live through the same public action API humans use — reasoning streamed, decisions recorded as ledger inputs |

## Status — RC1 tag-ready: freeze gate + full audit + final-engine soak 3/3 PASS (2026-09-21)

| Milestone | Evidence |
|---|---|
| **Core engine** — hash-chained ledger, coops, kcal-true needs, recipes, auction markets | ✅ 540/540 tests, exact money conservation |
| **Hardcore survival gate** (unequal 50/50 start, 21M fixed supply, 2,000 ticks) | ✅ 3/3 seeds pass, worst essential streak 4/50 |
| **City scale** — 975 citizens with every founder default ON | ✅ RC1 soak 3/3: 6,000 seed-ticks, zero invariant breaks, 56,550 votes, 970 audits per seed, Gini ~180 |
| **Performance** | ✅ ~18 ticks/s @ 966 citizens (floor was 5) |
| **Multiplayer seats** | ✅ 12 seats × 1,000 ticks, 100% action throughput |
| **LLM living world** | ✅ Politician seat: 4/4 proposals passed live; adversary survived 200 ticks without breaking the economy; $0.00/session; byte-identical replay at zero model cost |
| **Policy science** | ✅ ~200+ banked study runs: tax/dividend atlas, society studies, disaster/spoilage/machine-wear/crisis batteries, P2 battery re-run under current engine |
| **Cardano anchoring** | ⏸ deferred by design until post-RC1 |

**The one-sentence proof:** a transparent cooperative economy with capacity-true production absorbed a 50%/tick confiscatory wealth tax, harsh disasters, adversarial hoarders, and proposal spam — zero deaths, exact money conservation, and every genuine failure traced to a bug, never a design flaw.

## Quick start

```bash
python -m venv venv && . venv/bin/activate
pip install -e .
pytest -q                       # 540 gates
python dashboard/server.py      # WebUI on :8421
```

Open the WebUI → start a world → claim a citizen seat → spend your monthly vote token on the Civic Board → watch crises auto-balance and audits publish. Or start a **Break the System** round and see how much damage one determined actor can do before oversight catches them.

Heavy runs are resource-capped by design (the engine shares its container with other services):

```bash
bash scripts/memrun.sh <GiB> <log> <cmd>   # memory-capped, CPU-pinned launcher
```

## What's inside

| Path | Content |
|---|---|
| `src/openboard/` | The engine: ledger, state, rules, markets, bots, land + LVT, foreign sector, regions, research, crisis, oversight, LLM seats |
| `dashboard/` | Flask WebUI + game server — citizen seat, Civic Board, attack arena, LLM attach |
| `tests/` | 540 gates: conservation, determinism, realism contracts, API click-paths |
| `scripts/` | Gates, sweeps, analyzers, the memrun launcher, remote-sim tooling |
| `sweeps/` | Banked evidence: every study's raw data + FINDINGS |
| `docs/` | Source model (verbatim), specs, study plan, retrospective, handoff |

## How it's proven

Every feature lands with a gate before it ships:

- **Survival gates** — 2,000-tick worlds at city scale; famine-class failure fails the build
- **Conservation proofs** — money in = money out, every tick, integer-exact; the ledger hash-chains and verifies
- **Determinism** — same seed + same transactions → byte-identical world; LLM/human decisions are recorded inputs, so even AI sessions replay exactly at zero cost
- **Fidelity contracts** — each realism lever must reproduce its documented real-world direction and mechanism, or the test fails
- **Full-session doctrine** — the unit suite proves the parts; long runs, LLM playtests, and multi-seed soaks prove the game (13 ship-stopper bugs were caught by sessions, not the unit suite)

Key results, banked with data in `sweeps/*/FINDINGS.md`:

- **Majority confiscation is survivable** — 72% voting a 50%/tick wealth tax: production intact, Gini 2,100→103, zero deaths
- **Harsh disasters don't cascade** — 0.8%/tick shock profile: production within ±0.5% of control
- **Spoilage is the one lethal realism lever** — permanent famine once it bites; gated by default
- **Democracy self-balances** — proposal spam is structurally harmless under attention scarcity (253 filed, 0 pass); crises auto-balance
- **Research is the anti-famine superweapon; the wealth-tax threshold, not the rate, is the knob**

## Documentation

- [docs/PLAYER_GUIDE.md](docs/PLAYER_GUIDE.md) — how to play: citizen seat, the vote token, Mercury, Break-the-System
- `docs/source/open-board-market-socialism.md` — the authoritative source model
- `docs/TESTING_RETROSPECTIVE.md` — what the testing program found, the bug ledger, and the binding test standards
- `docs/STUDY_PLAN.md` — the study ledger: every question asked and its verdict
- `docs/ideas/engine-as-law-referee-predictor.md` — the deployment thesis (law as a verified referee)
- `docs/ideas/scaling-doctrine-hierarchy-of-computation.md` — how this scales to millions
- `docs/HANDOFF.md` — living state snapshot

## License

All rights reserved (private repository, pre-release).