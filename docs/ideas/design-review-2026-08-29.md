# OpenBoard — Full Design Review (2026-08-29)

Scope: the whole system as (a) a world-government concept and (b) a game.
Everything below is grounded in verified evidence from Stages 1–6,
the sweep findings, and the diagnostic history.

## What is proven and works

- **Deterministic core**: append-only hash-chained ledger, money invariant
  exact across every test and gate ever run; replay byte-identical.
- **Democracy in the loop**: proposals/votes/rule changes live; constitutional
  guard blocks governance-rigging; all attack classes from the adversary lab fail.
- **Real economy**: 39 goods, full input chains (loggers→sawmill→steel→machines),
  competition with entry, capital backstop, essential needs met at 1k citizens
  through the 'fatal' shock tier, real death + births + childhood absorbed.
- **Scale**: 1k full-fidelity citizens in budget; 100k people in cohort mode;
  stability region charted (45 combos + 2 cliff zooms).
- **Verifiability path**: anchor.py protocol layer done; Cardano metadata
  anchoring investigated (~$0.05/day, production precedent exists).

## Lacking as a world-government concept

1. **No credit, loans, or insurance.** The deepest economic gap. No citizen or
   co-op can borrow against future production, smooth a bad month, or insure
   against shocks. The capital backstop is a grant mechanism, not a credit
   market. Real communities run on trust-over-time; we have none.
2. **No dynamic firm entry by agents.** FOUND_COOP exists as an action, but
   co-ops are seeded by the scenario; bots never *found* co-ops in response to
   shortages. Democratic market entry — the core socialist answer to capitalist
   entrepreneurship — is not yet emergent.
3. **Politics is 4 scripted archetypes.** No delegation (the approved algorithmic-
   delegative design is only partially live via research voting), no parties,
   no media, no persuasion, no information asymmetry. Voter competence is
   assumed, which the user explicitly flagged as unrealistic.
4. **No wage bargaining or labor mobility pressure.** Wages are rule-fixed;
   workers switch co-ops only via JOIN_COOP scripts; there is no competition
   for workers (only for customers).
5. **No geography or finite resources.** Land, ores, water are abstracted;
   nothing depletes; no transport costs; the 'one country implements it first'
   story has no territorial model.
6. **No outside world.** No trade, migration, or comparison with other systems;
   the takeover story ('one country, then the world') is currently un-simulable.
7. **Money supply policy is not votable** in practice: mint/retire rules are
   hardcoded per event type. The democracy cannot run monetary policy.
8. **Justice is thin.** Flags + council interventions (FINE/DISSOLVE_HOARD/
   EMERGENCY_TRIAGE) exist, but there are no trials, no appeals, no restorative
   outcomes — and no mechanism for a citizen to *file* a grievance.

## Lacking as a game

1. **No multiplayer.** One Flask server, no accounts, no concurrent humans.
   The Citizen Seat is single-tenant by design.
2. **No game modes or goals.** Sandbox only. 'Break the System' (the approved
   first game) does not exist as a playable mode yet — the adversary lab is
   scripted, not player-driven.
3. **No pacing controls for players**: no speed presets (pause/slow/fast),
   no event notifications beyond a toast, no mobile layout.
4. **No persistence/shards**: save/load exists but no world list, no long-term
   campaign, no spectator sharing of a world link.
5. **Onboarding**: nothing teaches the loop (work → earn → buy → vote).
   A new player sees 23 needs rows and no guidance.

## What does not work well (evidence-based)

- **Dividend channel is dormant at scale**: surplus pool hovers at ~435 cr,
  below min_pool_buffer (500) -> citizens almost never receive dividends
  (sweeps finding). The main redistribution valve is effectively closed at
  986 citizens — the circular flow leans on services instead.
- **Bounded but persistent service wobble** (maintenance/meat streaks ≤30):
  stable per the gate, but visible as oscillation in God View.
- **Bootstrap needs genesis seeding** (founding capital/equipment); a from-zero
  start still produces a 200-tick starvation transient. Fine for the game
  (we seed), but the 'any community can start from nothing' claim is not proven.
- **Absolute-denominator params** (labor_pool_cap, max_dividend_per_tick) do
  not scale with population — two knobs already found mis-scaled at 1k.
- **Gini instruments are crude**: wealth tax works, but there is no
  redistribution *policy space* (it is one knob, one threshold).

## Recommended next moves (priority order)

1. **Financial depth package**: credit union (loans against future labor),
   mutual insurance pool, shock-indexed rainy-day accounts. Unlocks resilience
   AND gameplay (debt, risk, trust).
2. **Emergent entrepreneurship**: bots/citizens detect chronic shortages and
   FOUND_COOP in response; entry reacts to the stability map's signals.
3. **Delegation in live politics**: implement the algorithmic-proposal +
   delegative-vote loop from the Stage 5 spec for ALL votable params, not just
   research.
4. **'Break the System' game mode**: give a human the adversary toolkit
   (hoard, wash-bid, faction, capture) against a live world — the proven
   attack suite becomes the tutorial.
5. **Accounts + concurrency** in the dashboard (the gateway to multiplayer).
6. **Onboarding quest**: first session as a citizen (work, eat, vote) guided.

## Honest bottom line

The *economic core* is the strongest part: proven, invariant-clean, scaled.
The *society layer* is proven mechanically but shallow behaviorally (4
archetypes, no credit, no geography). The *game* is an excellent observation
deck that is not yet a game — one human seat, no goals, no rivals. The next
leap is not more stability proofs; it is **financial depth + real multiplayer
+ the adversarial game mode**.
