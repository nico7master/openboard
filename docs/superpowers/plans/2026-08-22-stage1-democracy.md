# Stage 1 Plan: Democracy in the Loop

- [x] T1 politics.py: perception helpers (gini trend, own unmet, sector deficit, own wealth)
- [x] T2 politics.py: 4 archetypes — proposal_gen() + vote_decision() pure functions
- [x] T3 sim.py: election window every K ticks; wire proposals/votes into tick batches
- [x] T4 server.py: politics enabled in baseline; governance LIVE for bot votes
- [x] T5 tests: unit (archetype logic), integration (election flow, rule activates)
- [x] T6 experiment: self-correction run (wealth_tax off at genesis) → measure
- [x] T7 experiment: capture attack (51% faction) → expect block
- [x] T8 gate: 3 seeds × 2000 ticks governance-active stability suite
- [x] T9 docs: decisions + results; commit
