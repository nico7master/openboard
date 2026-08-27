# Stage 6 implementation plan — Robustness at Scale

Spec: docs/superpowers/specs/2026-08-27-stage6-robustness-at-scale.md (commits 86234fd, 5885ce0, d94fe3b)
Mandate: user approved full autonomous execution of WPs 1-7 (2026-08-27 21:31 CEST).

- [ ] WP1: profile 1k-citizen run; optimize proven hotspots only; byte-identical replay tripwire + suite green
- [ ] WP2: stage6_scale_gate.py - 1k citizens x 2000 ticks x 3 seeds, invariant exact, streak <=50, <=2h, <=8GB, solo; PASS log committed
- [ ] WP3: coarse sweep harness (sweeps/ dir, 5 knobs x 3 values x 3 seeds x 500 ticks, resumable, sequential)
- [ ] WP4: cliff zoom on 2 sharpest edges (7-10 values x 5 seeds x 1500 ticks) + failure-mode classification
- [ ] WP5: dashboard stability heat-card (God View tab, sweeps/*.json source, click -> run summary)
- [ ] WP6: shock battery at 1k citizens x 2 seeds (peaceful->apocalyptic), honest breaking report
- [ ] WP7: cohort scaling - cohort_k weights, weighted invariant, 1k agents x K=100 (=100k people) x 500 ticks x 2 seeds + K-divergence check
- [ ] Closure: full suite green, roadmap doc updated with charted-region summary, final report

Execution order: WP1 -> WP7 (cohort infra, since it changes state schema BEFORE the big gate) -> WP2 -> WP6 -> WP3 -> WP4 -> WP5 (UI last, consumes sweep data).
Determinism tripwire: fixed 500-tick reference run hash must never change.
