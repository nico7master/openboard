# 🏦 OpenBoard Economy — Player Guide

*How to play a working cooperative economy — and how to try to break it.*

## Start a world

```bash
python dashboard/server.py     # WebUI on :8421
```

Every new world ships with **democracy ON**: the monthly vote token, persuasion tiers, reachable quorum, whistleblower rewards, public audits, need allocation, and scarcity pricing. Research runs with the proven p4fix config, and the rescue faucet decays (B8): repeated rescues shrink, honest work restores.

## The unequal world (the story)

You start where the drama is: **the top 1% own half of all money, the Society Pool starts empty.** The mission banner says it, and the win screen defines victory: *equality rebuilt (Gini under a third of the start), nobody unfed, ledger exact.*

## Play as a citizen (Your Seat)

1. **Claim a citizen** and open **Your Seat** (header tab).
2. **Work** produces; **dividends** from the Society Pool arrive monthly.
3. **Found a coop** with friends — workers own the surplus.
4. **Spend your monthly vote token** (10,000 bp): split it across proposals with the token gauge. Your bp is your say — you can put half on a tax change, a quarter on a rent rule, and keep the rest.
5. **Delegate** if you'd rather follow someone you trust. Delegations are snapshotted when a proposal opens — last-second sweeps don't flip votes.
6. **Blow the whistle** on cheaters: successful flags pay.

## Vote like a republic (Civic Board)

- Proposals are shown in **plain language** ("the wealth tax: sets rate from 8% to 12%"), not raw JSON.
- **Structural changes** (taxes, research, crisis, need rules, vote rules, surplus spending, credit, scarcity pricing) need a **60% supermajority of everyone** — abstention doesn't shrink the bar.
- Crisis votes: **one per citizen**, tracked.
- **Voting with money attached is flagged** (vote-buying): the bought delegation dies, the payer is fined into the pool.
- The **Reign scoreboard** tracks your governance: days, laws, crises, Gini trajectory, ledger ✓.

## Watch Mercury legislate (AI seats)

Attach **Mercury-2.5** to the politician seat and watch its reasoning stream as it drafts proposals, campaigns, and spends its own token. Same API as you use — no god mode. Sessions are recorded; replays are byte-identical with zero model calls. Cost per session: ~$0.00.

## Break the System (adversary mode)

Try to crash a fair economy: hoard, dump, corner, flag-storm. Choose your **pacing** (steady/bold), watch the **oversight meter** fill as the system closes in on you, and mind the scoreboard: damage counts only **harm you worsened** over baseline, flags are capped, and games are per-player. Can you beat it before the audits catch you?

## The economic soul of it

- **Transparent ledger**: every action recorded; money conserved exactly, every tick.
- **Prices are signals**: scarcity raises markups (capped); crises zero the signal (no gouging).
- **Society invests in its producers**: deadlocked coops get an input advance — but repeat dependence decays it, and clean work restores it.
- **Land is leasehold**: use it, pay the land-value tax; the pool recaptures the rent.
- **Research pays**: the Innovation Fund turns surplus into capability, with a protected dividend reserve.

## Tips

- Governance needs **participation**: quorum is reachable but not free — talk, post, delegate.
- Trust is earned: passed proposals raise it, failures lower it, and undecided voters follow trusted voices.
- Don't rescue-rush: society's help is real but fading — build the productive habit.
- If a policy backfires, vote it back: rollbacks of structural rules keep the supermajority bar.

*The full science behind these rules lives in `docs/STUDY_PLAN.md`, `docs/AUDIT_FIXES.md`, and `docs/TESTING_RETROSPECTIVE.md`.*
