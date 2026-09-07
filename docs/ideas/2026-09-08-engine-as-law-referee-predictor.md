# Engine as Law / Referee / Predictor — the real-world architecture

Date: 2026-09-08. Status: idea + roadmap reframing (no implementation yet).
Origin: design discussion after the Week 2 harvest and Week 3 multiplayer gates.

## The reframe

The engine will never run **on** a blockchain — one tick (~3,650+ actions, full
world state) does not fit in any L1 transaction, and Cardano's ExUnits/fee
model makes per-action execution impossible (measured in the 2026-08-29
anchoring investigation). But it never needs to. The engine's real-world role
splits into three:

| Role | Meaning | Status in repo |
|---|---|---|
| **Law** | Rules are exact, versioned, integer-only formulas. Every rule change is itself a ledger tx, so the *evolution* of the law is auditable. `rules_hash` commits the active law into every anchor (v1.5 fields) | RuleSetDoc versioning + anchor v1.5 — done |
| **Referee** | Humans act in reality; actions enter the append-only ledger; the deterministic engine replays them under the anchored law and emits verdicts (taxes due, dividends, invariants held, flags). Anyone can run the same replay and get bit-identical results | replay.py + tick commitments + anchor chain — done |
| **Predictor** | Before a community adopts a rule in reality, the policy lab runs the same sweeps and predicts distribution/employment/price effects (18 proven paths already harvested) | policy lab + harvest_rerun.py — done in-sim |

**The real world plays it out by itself.** People and coops execute; the
ledger remembers; the engine judges; Cardano proves nobody rewrote either.
Decentralization comes from *anyone being able to run the referee*, not from
running the referee on-chain. This is exactly Bitcoin's split: rules live in
off-chain node code; the chain provides ordering, timestamping, tamper-evidence.

## Why the current stack maps cleanly

- **Determinism**: integer-only arithmetic, no floats — identical replay on
  any machine (proven by the replay tests and the v0.4 harvest grid).
- **Hash-chained ledger**: every tx hashed into the chain; `tick_commitment`
  commits state + ledger head per tick; anchors merkle-commit the day.
- **Anchors are cheap**: ~$0.03–0.05/day, ~$11–18/yr for daily mainnet anchors.
- **Governance already ledger-native**: RULE_CHANGE txs with versioning +
  rollback; the constitution is data, not code.

## The four honest gaps before pointing it at reality

1. **Oracle problem.** Replay proves *rule-application* (arithmetic, fairness,
   invariants), not physical facts (was the flour really milled?). Needed:
   participants sign their own actions with their own keys; attestation for
   physical facts — observer quorums, receipts, audit sampling. The in-game
   oversight flag system is the template for sampling-based trust.
2. **Teeth.** "coop_7 owes workers 450cr" only binds if credits are real
   claims (mutual credit against coop surplus, community enforcement) rather
   than game points. Institutional design, not code.
3. **Identity.** One-person-one-vote needs Sybil resistance; real people need
   keypairs. Open problem; pragmatic start = invitation + vouching graphs.
4. **Multi-operator verification.** Decentralization of verification only
   counts when several independent parties actually run replays and
   cross-check the anchors. Needs: reproducible builds, a public verifier
   script (Week 4.1 scope), and at least 2–3 independent runners.

## Long-term verifiability upgrade path

- **Now**: deterministic replay + daily Cardano metadata anchors (deferred until
  credentials exist; local verifier path can be built first).
- **Later**: Aiken validator to enforce a minimal on-chain constraint (e.g.
  only governance multisig can post anchors).
- **Game layer**: Hydra head / Paima for real-time multiplayer actions,
  settled to L1 — matches game-concepts.md.
- **Endgame**: zkVM proof that "tick N+1 follows from tick N + these actions"
  — the running itself becomes trustlessly verifiable without on-chain
  execution. Compute-heavy for our tick workload today; the honest endgame.

## Order of operations (unchanged by this reframe)

1. Prove the law is stable and winnable in simulation — **done (v0.4)**
2. Make it multiplayer-fun — **done (v0.5)**
3. Anchor it publicly (Week 4.1, deferred until preprod credentials exist;
   local verifier + reproducible build can proceed independently)
4. Release the referee (v1.0.0: fresh-clone e2e, README, known-issues)
5. Society layer: signed human actions + attestation + mutual credit teeth

## Decision

Adopted as the post-v1.0 direction. No code changes required now; this doc is
the contract that keeps engine scope honest (executor stays off-chain; Law /
Referee / Predictor are the product).
