# Stage 1 Spec: Democracy in the Loop

Goal: prove the society can tune its own rules without a designer's hand.

## Political bot archetypes (perceive → propose → vote)
- **egalitarian**: monitors Gini; proposes higher wealth_tax / dividend share when inequality climbs
- **libertarian**: prefers lower taxes; votes against interventions, proposes tax cuts when stable
- **pragmatist**: monitors own unmet needs + sector deficits; proposes stock-target/dividend tweaks that fix shortages
- **faction**: coordinated minority/majority voting bloc — proposes self-serving rules (capture attack)

## Mechanics
- Election window every K ticks (default 50): each political bot may PROPOSE
  one rule-param change; all bots VOTE per archetype interest.
- Proposals limited to whitelisted votable params with bounded deltas
  (guardrails: params stay in validated ranges per rules.py).
- Existing governance rules apply unchanged (quorum, 2/3 constitutional,
  rollback ratchet, version pinning).

## Experiments
1. **Self-correction**: start world with a bad rule (wealth_tax disabled).
   Society must detect harm (Gini climb) and vote taxes in. Measure ticks
   to detection, to correction, Gini peak.
2. **Stability under politics**: governance-active long runs (multi-seed,
   2000 ticks) stay within gate metrics.
3. **Capture attack**: faction of 51% attempts to vote itself the surplus
   (dividend targeted at faction / tax exemption). Expect constitutional
   guards to block; if not, that is a finding to fix.

## Gate (all must pass)
- multi-seed governance-active runs: unmet 0 (post-transient), money
  invariant exact, no crash
- ≥1 measured self-correction event
- faction capture blocked visibly (rejection or guardrail) in all seeds
- tests green incl. new: politics unit tests + self-correction + capture

## Non-goals (later stages)
- 2nd producer per sector (stage 3), adversarial search (stage 2),
  shocks (stage 5).
