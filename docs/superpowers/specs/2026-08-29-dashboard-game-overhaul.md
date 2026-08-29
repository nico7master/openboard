# Game-style dashboard overhaul — design spec

Date: 2026-08-29 · Status: approved (user, 21:27 CEST) · Decisions D9.1–D9.4

## Problem

The dashboard is an engineer's instrument panel: walls of raw numbers, tables,
no story. A non-technical player cannot tell at a glance whether the world is
healthy or what deserves attention.

## Principle (D9.1)

> The dashboard tells a story in plain language first; numbers exist only
> inside pictures. Color carries meaning; raw values live in drill-downs.

## Components

### 1. World at a Glance (landing view)
Story cards, each = icon + plain sentence + a chart (sparkline / gauge / trend
arrow) + severity color. Server-computed from live state:
- Economy health (needs met %, trend arrow)
- Shortages (who couldn't buy what, how long, spiking since when)
- Inequality trend (Gini line, direction)
- Idle production (which coops starved of what, for how long)
- Open votes (plain-language summaries + ticks-to-close)
- Active shocks as weather (icon, affected industries, intensity)
- Population story (births, deaths, children)

Click a card → detail panel with the full chart. No bare tables on landing.

### 2. Living Flow Map (canvas, real data only)
- Industry nodes sized by production, colored by health
- Goods as animated particles along actual supply-chain edges (from recipes)
- Money pulses returning; shocks rendered as weather overlays
- Population ring showing needs satisfaction
- Click node → plain-language story (starvation streak, last sale, blocked input)
- Playback bar: pause / slow / normal / fast (reuses autoplay + tick speed)

### 3. Circular Flow Stage
Animated machine diagram: Citizens → Labor → Co-ops → Goods → Markets →
Surplus → Pools → Citizens. Arrow thickness/pulse = real per-tick flow volume
from /api/flows. Stuck money glows red in its pipe (e.g. dividends throttled).
Click a stage → the story card behind it.

### 4. Story-first reskin of existing views
Charts replace tables in God View, Seat, votes, stability map. Numbers only in
drill-downs. All existing functionality preserved (seat actions, votes,
autoplay, attack mode).

## Server API

- `GET /api/story` → `{cards: [{id, icon, severity, sentence, series?, detail}], tick}`
- `GET /api/flows` → per-tick aggregated flows: industry nodes (production,
  health, pending inputs), edges (good, volume/tick), pool flows (wages,
  dividends, services, taxes), population ring data

## Decisions

- **D9.1** Story-first: plain sentences + charts; never bare numbers on primary surfaces.
- **D9.2** Living flow map: nodes + supply-chain particles + shock weather, all driven by ledger data (no cosmetic geography).
- **D9.3** Circular Flow Stage: the economy as an animated machine diagram — the map is where you watch, the stage is where you understand.
- **D9.4** Both visuals read the same server-computed flow data; they can never disagree with each other or the ledger.

## Non-goals

No 3D, no new frameworks (canvas + existing Chart.js/Alpine), no engine changes
(presentation layer only), no geography (future package).

## Verification

- `test_story.py`: story cards severity-classified with sentences; shortage /
  inequality / vote / shock cards computed from injected states
- `test_flows.py`: flow volumes reconcile with ledger events; endpoint shapes stable
- Full suite green; dashboard boots; visual verification via screenshot
