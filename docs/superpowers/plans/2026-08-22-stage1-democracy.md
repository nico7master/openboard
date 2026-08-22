# Stage 1 Plan: Democracy in the Loop

- [ ] T1 politics.py: perception helpers (gini trend, own unmet, sector deficit, own wealth)
- [ ] T2 politics.py: 4 archetypes — proposal_gen() + vote_decision() pure functions
- [ ] T3 sim.py: election window every K ticks; wire proposals/votes into tick batches
- [ ] T4 server.py: politics enabled in baseline; governance LIVE for bot votes
- [ ] T5 tests: unit (archetype logic), integration (election flow, rule activates)
- [ ] T6 experiment: self-correction run (wealth_tax off at genesis) → measure
- [ ] T7 experiment: capture attack (51% faction) → expect block
- [ ] T8 gate: 3 seeds × 2000 ticks governance-active stability suite
- [ ] T9 docs: decisions + results; commit
