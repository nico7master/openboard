# Stage 2 Spec: Adversary Lab — RESULTS (GATE PASSED)

## Harness (scripts/adversary.py, wired into check.sh)
- Attack matrix: 30 targeted attacks (WORK/TRANSFER/LIST/BID/PRODUCE/
  FOUND/JOIN/RULE_CHANGE/PROPOSE/VOTE/ROLLBACK/INTERVENE/version pinning),
  each vs fresh world, per-tick invariant assertions.
- Seeded fuzzer: 6 random malformed txs/tick mixed into a live economy.
- Greedy adversaries (valid actions, adversarial intent, overlaid on
  honest behavior): wash trader, cornerer, vampire wage farmer.

## Findings & fixes
- Harness bug (not engine): strategies first used wrong BID payload key
  ('price' vs 'max_price') and read nonexistent ledger attrs — the lab
  debugged ITSELF, exactly its job.

## Results (all seeds)
- Matrix 30/30 blocked, fuzz 400 ticks invariants exact.
- wash_trader: ends at 2 cr (loses everything) — wash trading is
  UNPROFITABLE BY CONSTRUCTION: 3x-floor revenue flows to coop treasury
  -> patronage spreads to all members -> surplus above cost to the pool.
  The attack pays society for the privilege.
- cornerer: 166 cr + hoarded bread nobody buys — cornering essentials
  burns credits; essential buyers' FCFS flow continues.
- vampire: 1.26x median — bounded by wealth tax (proven earlier).

## Gate
No strategy extracts >2x median honest wealth; invariants hold. PASSED.
