# OpenBoard Economy — One-Month Shipping-Ready Plan

Date: 2026-09-03 · Baseline: v0.02 + D16 unequal scenario · Goal: **shippable v1.0 in 4 weeks**

## Definition of "shipping ready"

A new player can, in one sitting: open the dashboard, understand the world in 30 seconds, enact a policy, watch the consequence, and undo it — without asking anyone what a number means. The economy survives 2,000 ticks × 5 seeds under the fixed 21M supply. Daily anchor chain replicates on Cardano preprod. A second human can join a live world without breaking it.

---

## Week 1 — Economic completeness (v0.03: make the model honest)

| WP | Item | Why | Gate |
|---|---|---|---|
| 1.1 | **Sub-floor clearance listings (L1)** — prices on listings, honest clearance below cost floor, anti-predation kept | Real price discovery, both directions. Currently prices can never fall | Prices observed falling on oversupply in 200-tick run; no predator exploit passes adversary lab |
| 1.2 | **Perishability (R1)** — shelf-life per essential good, FIFO consumption, spoilage events | Closes the hoard-without-cost arbitrage; inventory is already taxed (D12) but never rots | Spoilage visible on Chronicle + Living Map; hoarder adversary strategy now unprofitable |
| 1.3 | **Skills (R2)** — per-citizen skill levels per sector, learning-by-doing, skill decay when idle | Biggest realism unlock; makes labor mobility costly and specialization meaningful | Hardcore gate still passes; retrain path exists so shocks don't strand workers forever |
| 1.4 | **Demand memory (R4)** — shortage memory already exists; extend to pre-buying before *predictable* recurring shocks | Bots stop being myopic; smoother price curves | Shock-recovery time improves vs baseline in stage5 battery |

**Weekend gate:** full suite green + hardcore gate 5 seeds + new-feature tests ≈ 40 added.

## Week 2 — Prove the unequal world + campaign harvest

| WP | Item | Why | Gate |
|---|---|---|---|
| 2.1 | **Re-run the 100+ variant sweeps under the 21M fixed cap** — deflation dynamics, treasury-first wages, pool-funded founding | Fixed money changes stability math; the banked data is pre-cap | Stability heat-card for the *new* defaults committed to sweeps/ |
| 2.2 | **Unequal-scenario stability region** — from 50%-owns-50% start, map which policy paths (tax rates × dividend shares × credit) converge to equity without breaking production | The core game loop must have verified winning paths | ≥3 distinct policy paths proven to reach <15% top-1 share while needs stay met |
| 2.3 | **Adviser upgrade — diagnosis → prescription chains** | Advisor names upstream causes; extend to multi-step plans and auto-verification of whether the fix worked | Breadth: every advisor card carries a verifiable prediction |
| 2.4 | **Deflation policy study** — fixed money + growth = falling prices; decide the votable counter-cyclical knobs (credit velocity, demurrage option) | Known consequence of hard money; make it a game decision, not a bug | One-pager + Policy Lab knob if warranted |

## Week 3 — Multiplayer & game modes hardening

| WP | Item | Why | Gate |
|---|---|---|---|
| 3.1 | **Multi-human seats at scale** — accounts + concurrency exist (A-series); stress-test 10+ concurrent humans with real latencies, seat conflict rules | Two people in one world is the minimum shippable multiplayer | 10 concurrent seats, 1,000-tick soak, zero invariant breaks |
| 3.2 | **Break the System v2** — the attack API exists; add scoring, timed rounds, leaderboard | This is the fun first game per the game-concepts doc | Playable 20-min round with a verdict screen |
| 3.3 | **Onboarding quest** — guided first session: watch → enact → observe → adopt (extends the 3-step tour) | Human-first mandate: playable without a manual | New-player scripted session completes unaided |
| 3.4 | **Persistence & campaign** — autosave exists; add named saves, world list, crash-recovery drill | Never lose a reign again (already bit us once) | Kill -9 during autoplay → world restores to ≤30s loss |

## Week 4 — Public verifiability, performance, release

| WP | Item | Why | Gate |
|---|---|---|---|
| 4.1 | **Cardano preprod anchoring live** — anchor.py v1.5 (rules_hash, engine_version, tick_height) metadata transactions on preprod; verifier script anyone can run | The trust story: determinism + public ledger | Independent replay from anchor chain reproduces state hash |
| 4.2 | **Performance floor** — 1,000 citizens, 300 coops at ≥5 ticks/sec; cohort-scaling (stage6 WP7) wired into the dashboard as the 10k-citizen view | Engine must handle the promised scale | scale gate passes on container hardware |
| 4.3 | **UX final pass** — hover-only numbers everywhere, story verdicts on every view, tunnel/URL reliability, empty-state screens | The standing complaint: nothing may read like lab equipment | User (you) plays 30 min without asking "what is this?" |
| 4.4 | **Release gate** — fresh-clone install → run → play e2e; README; versioned tag v1.0.0; known-issues doc | Shipping means someone else can run it | Fresh-store e2e passes from clean state |

---

## Standing rules during the month

- Every WP lands with tests + gate; no "done" without evidence
- Decision save points capture before every rule change (already automatic)
- Weekly tag: v0.3 (wk1), v0.4 (wk2), v0.5 (wk3), v1.0-rc (wk4)
- Anything that breaks the hardcore gate blocks the week

## Known risks

1. **Skills (1.3) is the biggest change** — touches every bot script; schedule the week, not a day
2. **Deflation could interact badly with credit** (loans get heavier in real terms) — study before shipping credit knobs
3. **Perishability re-tunes every food chain** — recipes were demand-balanced assuming no rot; re-run dairy/livestock balance after 1.2
4. **Cardano preprod faucet flakiness** — anchor work must degrade gracefully (local anchor chain stays authoritative)
