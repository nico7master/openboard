# Testing Retrospective — What We Learned (2026-09-20)

**Why this exists:** between 2026-08-27 and 2026-09-20 the testing program ran ~200+ simulation runs, 540 automated tests, live LLM playtest sessions, and multi-day soaks. This document captures the durable lessons so they outlive the sessions that produced them. Raw data lives in `sweeps/`; this is the index of what matters and why.

---

## 1. The Bug Ledger — proof the testing worked

Every row was invisible to code review and would have shipped to players:

| Bug | Found by | Consequence if shipped |
|---|---|---|
| wealth_tax threshold scaled ×100 twice (server + genesis) | founder's "default votes" idea | every whole-document proposal silently fails validation — live governance permanently broken |
| research funding = % of *remaining* pool | Everything-ON study (p4) | exponential pool drain → dividend death |
| attack_score counted ALL flags as attacker damage | LLM full session (P1) | every Break-the-System round ends at tick 1 |
| human votes rejected `INVALID_PAYLOAD` (missing bp) | RC1 UX work | flagship governance feature silently dead in the UI |
| Citizen Seat view was a blank page | split-vote build | "Play as a citizen" rendered nothing |
| `persuasion` key dead in `_gov_params` whitelist | Mercury live sessions | entire 60%-tier + trust design never fires |
| no-op proposals farm trust forever | **Mercury found it** | politicians exploit their own scoring |
| founder defaults missing in live games (unreachable 50% quorum) | UX verification | token worlds launch without the token |
| electricity collapse t=955; machine boom-bust at scale | stage-6 scale gates | city-scale worlds die mid-run |
| "eat every food every tick" need quota | founder's physiology challenge | chronic fake famine; capacity numbers meaningless |
| broken founder trigger + scarcity pricing off + broken grain chain | founder rejected "looks fine" | the hunger nobody could see |
| founder stay-rule pinned founders under capacity | capacity audit | founding lever dormant at 966 citizens |
| `gini(dict)` summed citizen NAMES not balances | soak smoke test | wrong equality metric in soak reports |

**The pattern:** almost none came from the unit suite alone. They came from **full sessions** — long runs, live LLM playtests, scale gates, soaks, and a founder who challenged "looks fine." The unit suite proves the parts; the sessions prove the game.

---

## 2. Science Verdict Ledger

| Question | Verdict | Data |
|---|---|---|
| Land monopoly | nuisance, not famine; LVT recaptures wealth; pool-dump attack is safe | `sweeps/land_study/` |
| Majority confiscation | upgraded twice: self-harming → not fatal → **harmless equalizer** (Gini 2,100→103, production intact after capacity fixes) | `sweeps/p2/`, `sweeps/p2_rerun/` |
| Crisis override | works as designed; now insurance with no current claim (unmet 0 in both arms); ~13% production redirect cost | `sweeps/p2_rerun/` |
| Spoilage | **the one genuinely lethal lever** — permanent famine once it bites | `sweeps/p3/` |
| Machine wear | load-bearing for scale stability; the market path can't replace machines at 5.4× scale → `capital_refresh` rule | `sweeps/p3/` + gate ladder |
| Research | the anti-famine superweapon | `sweeps/society/` |
| Wealth tax | the **threshold** is the knob, not the rate | `sweeps/society/` |
| Harsh disasters (0.8%/tick) | do NOT cascade — production within ±0.5% of control | `sweeps/p3/` |
| Panic buying | inert — bots can't panic (this justified the LLM seats) | p3 study |
| Entrepreneur emergence | bots never found new businesses (same justification) | p3 study |
| Skills | safe; old "bottleneck" effects were scarcity-regime artifacts | `sweeps/p2_rerun/` |
| Proposal spam | 253 filed, 0 pass — attention scarcity (1 token/month) makes spam structurally harmless | soak governance counts |
| The republic at scale | 56,550 votes, 970 audits, ~590 proposals, Gini ~180, 6,000 ticks, zero invariant breaks | `sweeps/rc1_soak/` |

**Verdict expiry rule:** engine changes invalidate old conclusions. The p2 re-run (2026-09-20) proved it — the confiscation verdict changed twice as capacity was fixed. **Re-run the battery whenever an engine-changing milestone lands** (pattern: `scripts/p2_rerun.py` — output-redirect wrapper over the original probe, historical data untouched).

---

## 3. LLM Seats — the honest assessment

**What they proved:**
- **Bug oracle (exceptional):** Mercury found the trust-farming exploit on its own — exactly what a human min-maxer would find. Its full sessions exposed the round-attribution bug and the cadence bug that 1–2-tick tests structurally couldn't. Even its malformed replies (3/199) forced the robustness the engine needed anyway.
- **Politician (works):** 4/4 proposals passed legitimately; adapts when rules change mid-session; builds trust honestly once farming was closed.
- **Adversary (survived, didn't win):** 200 ticks, damage 520, hoarding + free-riding flags, Gini pushed to 2,637bp — the system held. Caveat: the smart multi-step attack remains unproven.
- **Cost:** $0.00 per session so far (A0 Venice endpoint); ~$0.04-class if paid. 199 calls / 346k tokens per 200-tick round.

**The architecture win:** LLM decisions recorded as ledger inputs → **byte-identical replay at zero model cost** (6.6s vs 207.5s verified). This is simultaneously (a) test determinism and (b) the multiplayer architecture, built before multiplayer exists.

**Design meaning:** bots are too well-behaved. The economy's full surface — fear, ambition, exploitation, persuasion — only gets exercised by human-like actors. The LLM seat is the only test audience that behaves badly on purpose.

---

## 4. Weak or useless tests (the honest list)

- **Panic-buying arm:** fully inert. Only value: proving bots can't panic → justified the LLM seats.
- **Land study's first framing:** asked "does land monopoly cause famine?" — wrong fear. The useful part (pool-dump safety) came after re-aiming.
- **P4's "is the lever safe" framing:** measured the wrong thing until the founder challenged it — safe levers ≠ good society. The 51-world study was the corrected version.
- **"Looks fine" interpretation error:** the test wasn't useless; the interpretation was. The founder's push exposed the broken founder trigger, disabled scarcity pricing, and the broken grain chain.

---

## 5. Process mistakes (and what they birthed)

- **API tests ran 1–2 ticks** → round-scoring bug survived them. Lesson: behavioral paths need full cycles (≥50 ticks for game scoring).
- **No end-to-end UI tests until the UX pass** → human votes silently dead, blank page shipped as a feature.
- **Two framework freezes from bare probes (2026-09-08)** → the memrun discipline was born the hard way: 14 GiB cap, one world process at a time, read-the-log-before-retry, CPU holdback. **Zero freezes since.**
- **Shock draws not pinned between paired arms** → some crisis splits were directional, not exact.
- **Own-script bugs:** gini(dict) summed names; model id fumbles; diffusion-model token budget. All caught by smoke-first — which is why smoke-first exists.

---

## 6. What the evidence says about the design

**The core claim survived everything we threw at it.** A transparent cooperative economy with capacity-true production, dividends, and strict conservation absorbed: 50%/tick confiscation, harsh disasters, adversarial hoarders, proposal spam, and its own crisis levers — with zero deaths and exact money conservation throughout.

- Every genuine failure was a **bug or a mis-scaling, never a design flaw** — and the design's own mechanisms (research, dividends, capacity reserves) were always the recovery path.
- **Realism features are the dangerous ones** (spoilage killed; machine wear nearly did). New realism must face survival gates by default.
- **Democracy self-balances:** majorities can vote self-harm, and the system converts it into equality, not collapse. Attention scarcity caps the spam channel.

---

## 7. Test standards going forward (binding for future milestones)

1. **Every UI affordance gets an automated click-path test** — the human-vote lesson.
2. **Behavioral windows, not snapshots** — assert after governance cycles fire, never at tick 5 (the votes=0 false alarm).
3. **Minimum ~50-tick behavioral tests** for any game-scoring path — the attribution lesson.
4. **Version-tagged verdicts** — FINDINGS carry the engine commit; batteries re-run on engine change (the p2_rerun pattern).
5. **LLM red-team as a release gate** — one adversary + one politician session per release; replay is free and byte-identical, so CI can diff behavior against the last release.
6. **Pin shock draws for paired arms; 2-seed confirmation for finalists** (chaos rule: within-seed comparisons only).
7. **Keep the probe discipline:** smoke-first, one combo per process, resumable JSONs, memrun for every launch, PC-probe before remote use.

**The meta-lesson:** the two best testing decisions were (1) making worlds deterministic and replayable — every later change became a provable A/B instead of an argument, and (2) running **full sessions** (bots, LLMs, humans, soaks) instead of trusting the unit suite on behavioral paths.

---

*Authored 2026-09-20 at freeze-gate green (soak 3/3 PASS, suite 540/540, commit `ce3acf3`).*
