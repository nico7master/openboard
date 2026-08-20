# Phase 7 Plan: Bot Simulations (D13) & Stability Metrics (spec §10)

Goal: the "prove it" phase — a bot cast of 10 archetypes runs the economy,
adversarial behaviors fail *visibly* (flags, failed proposals), and
stability metrics are measured per run.

## Design

- `metrics.py`
  - `gini(values)` — exact integer Gini coefficient
  - `SimMetrics` collector from state/events: clearing-price variance per
    good, unmet essential demand, flags by kind, archetype outcomes
- `bots.py` — one decision function per archetype; each bot sees only
  public state (radical transparency = perfect information is fine);
  deterministic given (state, params, tick, seeded rng):
  1. HonestWorker — work, buy essentials, modest market bids
  2. StrategicProducer — work, produce when inputs ready, list surplus
  3. Hoarder — minimal work, max-quota essential buys every tick
  4. PriceManipulator — wash-bids on own co-op's listings (inflate price)
  5. FreeRider — no work, maximal essential consumption
  6. ChampionVoter — proposes self-serving rules, votes for them
  7. CrisisTurtle — panics on price spikes (>2x baseline), hoards broadly
  8. CollusiveFaction — N bots bloc-voting + coordinated market cornering
  9. GrayMarketSmuggler — abstains unless prices stay near cost (system
     attractiveness probe); metrics track abstention
  10. Innovator — proposes efficiency rules, votes against capture
- `sim.py` — `run_simulation(citizens, archetypes, ticks, seed, params)`:
  deterministic world setup (co-ops founded from the cast), tick loop,
  returns final state + ledger + metrics timeline
- Engine addition: WASH_BID detection in the auction pass (spec §6.4) —
  a winner whose paying co-op is also the seller flags publicly

## Gates

- Baseline (honest+strategic mix): 100+ ticks, money invariant, no crash,
  gini stays moderate, essentials actually consumed
- Hoarder → flagged + dissolvable; FreeRider → flagged
- PriceManipulator → WASH_BID flagged
- Faction bloc below quorum → self-serving proposal fails
- Same seed → identical state hash (determinism)
- Gini verified against hand-computed values
