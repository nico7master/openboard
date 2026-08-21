# Dashboard Spec: OpenBoard Engine Server + Web Client

Date: 2026-08-21 · Status: approved (seed architecture, option B)

## Purpose

A visual testing interface for the engine — and the seed of the future
game frontend. The server/client split is permanent architecture;
everything else is additive.

## Architecture

```
Browser (Alpine.js + Chart.js, vendored — no build step, works offline)
   |  JSON polling (~1s) + action POSTs
   v
Engine Server (Flask, owns ONE run in memory)
   |  imports unchanged
   v
openboard engine (pure library — 180 tests stay valid)
```

No WebSocket in v1: polling gives the same feel at this scale; live push
arrives with multiplayer v2. No auth, no multi-run, no DB — those are
game-era features.

## Server (dashboard/server.py)

A `Run` object owns: WorldState, Ledger, bot roster, pending human
actions, per-tick recorded batches, injections (treasury seeds), a
metrics timeline, and a rolling event feed. One global lock; an autoplay
daemon thread ticks at a configurable interval.

Human actions join the NEXT tick's batch (honest to the tick model):
UI submits -> pending -> merged with bot actions -> one apply_tick.
The server fills ruleset_version automatically.

### API v1

| Route | Method | Purpose |
|---|---|---|
| /api/state | GET | Full snapshot + timeline + events + bots + pending |
| /api/reset | POST | New run (citizens, params, seed) |
| /api/tick | POST | Advance exactly one tick |
| /api/autoplay | POST | {running, interval} start/stop |
| /api/action | POST | Submit a transaction as a citizen |
| /api/bots | POST | Add/remove bot (name, archetype, coop) |
| /api/save | GET | Download the run as a replayable JSON |
| /api/load | POST | Restore a saved run (deterministic replay) |
| / | GET | The page |

## Save format (openboard-run-v1)

{format, genesis, params, injections, batches: {tick: [tx...]}}
— replaying batches rebuilds the identical world (bot decisions were
recorded, so no re-deciding). This doubles as the multiplayer replay
and audit format later.

## Client (dashboard/static/index.html)

Dark single-page layout, panels:
- Header: controls (tick, autoplay, reset), tick, money supply, Gini, surplus
- Charts: Gini + money supply over time (Chart.js)
- Citizens / Co-ops tables
- Market: last clearing prices, active listings/bids
- Governance: proposals + vote buttons
- Oversight: flag feed
- Events: rolling feed
- Play-as-citizen: action picker with payload templates
- Bots: add/remove archetype bots

## Explicit non-goals (v1)

Auth, identity, multiple runs, WebSocket push, real chain posting,
game graphics, mobile polish.
