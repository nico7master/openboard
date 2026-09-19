# Spec: P2 — LLM Politician Seat + Persuasion Rolls + Major-Change Tier

**Status:** APPROVED by founder 2026-09-18 ("okay lets try" after three design decisions).
**Builds on:** `2026-09-18-llm-living-world.md` (P0/P1 adversary seat: mercury-2-5, A0 Venice API, per-call accounting, record/replay determinism).

## Approved design decisions

1. **Loaded persuasion dice for undecided voters.** The tally is ALWAYS counted
   arithmetic (never random). Individual *undecided* bot voters roll a seeded die:
   `p_yes = clamp(base + alignment_term + trust_term)`.
   - The roll is derived from `(tick, proposal_id, citizen)` — same world seed ⇒ same
     rolls ⇒ byte-identical replay. No true randomness enters the engine.
   - Citizens with a decided stance vote their stance (never rolled).
   - The founder's default-approve directive still applies to non-constitutional
     matters; the roll governs the undecided band so elections feel human.
2. **Major-change tier: 60% supermajority.** Proposals whose params touch structural
   rule groups (`wealth_tax`, `governance`, `research`, `crisis`, `need_allocation`,
   `whistleblower`, `vote_token_bp`) require yes-bp ≥ 60% of all bp cast on them.
   Routine proposals keep simple majority + quorum. Constitutional guard unchanged
   (governance can never be disabled; default-approve never applies to constitutional
   matters).
3. **Accountability loop (politician trust).** Failed proposal ⇒ −trust for its
   author; passed ⇒ +trust. Trust (0..100, start 100) feeds the persuasion roll's
   effort term. Trust is engine state, snapshotted with the world; legacy worlds
   default every citizen to 100 (byte-identical behavior when nobody proposes).

## LLM politician seat

- New role `politician` in the existing seat harness (`src/openboard/llm_seat.py`):
  same digest philosophy, recording, replay, accounting (calls, tokens in/out,
  cost_usd, malformed count).
- Digest: open proposals (id, structural groups, deadline), own trust, own monthly
  token bp, recent pass/fail outcomes, public reasons.
- Allowed actions (exact validator schemas): `PROPOSE {params, activation_tick}` and
  `VOTE {proposal_id, choice, bp}` (token mode). Market/self actions are excluded —
  separation of powers: the politician does not also trade.
- Cadence: decide on events (proposal filed, own-proposal deadline, monthly token
  cycle) plus a low-frequency pulse; ~40 calls/100-ticks class per the doctrine.
- Driver: `scripts/llm_politician_session.py --record/--replay` mirroring the
  attack driver.

## Engine changes (minimal)

- `src/openboard/politics.py`: seeded persuasion roll for undecided voters;
  trust lookup/adjust helpers.
- `src/openboard/engine.py`: proposal classification (structural groups) + 60%
  tier in vote resolution; trust update on resolution (pass/fail, author).
- `src/openboard/state.py`: `politician_trust` dict (snapshotted, replay-stable).
- **No memrun/gate changes.** Old worlds replay byte-identically: with no
  politician proposals, trust stays 100, rolls never fire (no undecided band
  change vs default-approve), thresholds unchanged for routine proposals.

## Verification

- New tests: roll determinism (same seed ⇒ same votes), stance voters unrolled,
  60% tier (major fails at 55%, passes at 65%; routine unaffected), trust
  updates on pass/fail, politician seat schema conformance (PROPOSE/VOTE only),
  full-session fake-client smoke, record/replay roundtrip.
- Full regression suite must stay green (520+).
- Live session: Mercury politician files ≥1 reasoned proposal and campaigns it;
  verdict + accounting recorded; replay byte-identical.
