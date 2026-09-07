# Scaling Doctrine — the Hierarchy of Computation

Date: 2026-09-08. Status: design doctrine (guides WP4.2 and the post-v1.0
roadmap; no protocol changes yet beyond what the 1,000-citizen gate forces).
Origin: scaling discussion after v0.5 — "how do we guarantee millions or
gigga-populations?" + "once people join a company we only calculate the
company, and companies calculate together."

## 1. The guarantee model: architecture, not one big benchmark

No one proves billions by simulating billions once. The guarantee is:

1. **Linear-scaling architecture** (§3) — verified at each rung
2. **A cohort fidelity ladder** (§4) — statistical equivalence measured rung
   by rung, so prediction at 10⁹ is a calibrated surrogate, not a hope
3. **Sharded verification** (§5) — referee capacity scales with hardware

Measured baseline (2026-09-08, this container): 181 citizens / 43 coops /
~5.7 ticks/s (~176 ms/tick, ~3,650 actions/tick). The WP4.2 gate
(1,000 citizens / 300 coops / ≥5 ticks/s) forces ~5× speedup — a real
constraint, which is why performance work comes before release.

## 2. The hierarchy of computation (the coop insight)

"Once people join a company we only have to calculate the company — and we
can even calculate companies together." This is already true in the engine,
partially:

| Thing | Unit of computation today |
|---|---|
| Production (WORK+PRODUCE, recipes, inventory, treasury) | **the coop** — one recipe run per company, never per worker |
| Capital rent, input demand, trade bids | **the coop** — one aggregated bid per company |
| Wages, needs consumption, votes | the **person** — deliberately individual (rights) |

**The rule that keeps it market socialism:** the company is the unit of
*production* computation; the person remains the unit of *claim*. Aggregation
happens at market interfaces, never inside rights (wages/needs/votes stay
individual ledger rows — that is the fairness guarantee the project proves).

The missing rung is **FEDERATE** (post-v1.0): coops uniting into federations
with shared treasury/purchasing/joint output claims while member coops stay
autonomous. Then the compute tree is:

```
billions of people → millions of coops → thousands of federations → one global law
```

Each level calculates only itself and its interfaces; the global engine
carries only the law (money supply, wealth tax, dividends, constitution —
kilobytes) plus top-level market roots. Adding a level adds log-cost, not
linear cost. This is the actual answer to "billions."

## 3. Locality: shard the markets, keep the law global

The unrealistic part of the engine is not speed but that essential markets
clear **globally** every tick. Real economies are local markets under global
law. Partition citizens into ~50–200-household **regional markets** (coops
are already local!): one O(N) global clearing becomes M shards of O(N/M)
→ linear scaling. Global variables stay global and trivially cheap.
This mirrors MMO architecture and real economies.

## 4. The cohort fidelity ladder (prediction at billions)

Doctrine: prove **statistical equivalence** between N real agents and N/k
representative cohorts for the macro targets (top-1 share, essentials
streaks, gini). Each rung measures the previous rung's error:

| Rung | What it proves |
|---|---|
| 181 → 1,000 (WP4.2 gate) | linear scaling; fidelity curve begins |
| 1,000 → 10,000 | same laws, same verdicts; dashboard 10k view |
| 10⁵–10⁶ | sharded regions + parallel replay verification |
| 10⁹ | the real world IS the execution layer (engine-as-referee, see 2026-09-08 engine-as-law doc); prediction via calibrated cohorts; verification sharded by tick-range/region across independent runners |

First concrete experiment: run the proven policy grid at full 181 vs a
40-agent cohort surrogate, publish error bars in `sweeps/`.

## 5. Verification parallelizes even though execution doesn't

Replay of tick N needs only the action batch + previous state hash, so
independent verifiers shard by tick range or region and cross-check anchor
roots. Referee capacity scales with hardware forever — that is the billions
guarantee: not one big simulation, but **anyone can verify any slice**.

## 6. Making prediction fast (Policy Lab as conversation)

| Lever | Expected win | Mechanism |
|---|---|---|
| Warm-start forks | ~4–5× fewer ticks | save tick-300 steady state once; every variant forks from it (the 54-run harvest re-ran identical warmups) |
| Parallel seeds | ~8× wall on 8 cores | harvest runs are embarrassingly parallel; multiprocessing across seeds |
| Early-exit verdicts | ~3–5× fewer ticks | t=300 already discriminates tax rates; stop when confidence decides, not fixed 1500 |
| Cohort surrogate | ~5–25× smaller worlds | 20–40 agent worlds calibrated against full runs, error bars published |
| Engine speedups | 5–50× | cache per-tick params (currently rebuilt per bot), shard per-good auction sort, __slots__/numpy balances; Rust hot loop (pyo3) as the far option |

Combined target: today's ~4–5 min experiment → ~2–5 s.

## 7. Order of work (folded into Week 4)

1. Profile the 181 world — find where the 176 ms/tick goes
2. Pass the 1,000-citizen gate at ≥5 ticks/s (WP4.2)
3. Cohort fidelity experiment (first ladder rung evidence)
4. Local anchor verifier (Cardano-optional half of WP4.1)
5. Release gate v1.0.0
6. Post-v1.0: FEDERATE action, regional markets, zkVM endgame
