# Implementation Plan — Phase 4: Markets

**Date:** 2026-08-20
**Spec:** `docs/superpowers/specs/2026-08-19-openboard-economy-engine-design.md` (§9, §12 Phase 4)
**Gate:** market tests green + baseline stability campaign green + Phases 1–3 still green

---

## Goal

Price discovery with a cost floor, essential-goods priority at cost, and the SurplusPool: every credit earned above production cost flows to society (D4/D8/D11 foundations). Money retirement beyond the reserve cap goes live.

## Design Decisions

- **Listings**: `LIST_GOOD {coop_id, good, qty}` escrows qty from coop inventory at tick of submission. Listing floor = cost-baseline at listing time (published price). Listings live for exactly one tick; unsold qty returns to inventory at clearing.
- **Auction (market goods)**: `BID {good, max_price, qty, coop_id?}` — uniform-price batch auction cleared at END of tick:
  - Bids sorted by (price desc, bidder, content hash) — deterministic
  - Valid bid: price ≥ baseline floor, qty > 0, buyer can afford max_price × qty at submission (citizen balance or coop treasury)
  - Clearing price = lowest winning bid; all winners pay clearing price; winners short of funds at settlement are dropped (recorded)
  - Multiple sellers: pooled supply, proceeds + unsold returns split pro-rata by listed qty
  - **Seller receives floor × sold; (clearing − floor) × sold → SurplusPool** — production at cost, surplus to society (§9)
- **Essentials (D8)**: `BUY_ESSENTIAL {good, qty}` — triage essential/emergency only; price = baseline; per-citizen per-tick quota from rule param `essential_need_quota`; FCFS in deterministic order; leftover essential listings then join the normal auction ("rations to all first, surplus to auction"). Emergency = same channel, tighter quota (crisis auto-triggers arrive Phase 6).
- **Co-op treasury**: new coop field `treasury` (credit balance). Listing revenue lands there; coop BIDs (input purchases) pay from it. Wage funding from treasury arrives Phase 5 (minting model documented, unchanged this phase).
- **Retirement (v1 default, §9)**: after clearing, pool above `surplus_reserve_cap` is retired (`money_retired += excess`). Pool inflow has no outflows yet (allocation voting = Phase 5).
- **Citizen inventory**: purchases land in `citizen_inventory` (consumption mechanics arrive with bots, Phase 7).
- **Money invariant v2**: `sum(balances) + surplus_pool + sum(coop treasuries) == initial + money_minted − money_retired` (test-enforced).
- **New rule params**: `essential_need_quota` (good → qty, essentials only), `surplus_reserve_cap` (int ≥ 0). Complete-document schema grows again (dev-phase flexibility, documented).

## New Actions

- `LIST_GOOD {coop_id, good, qty}` — member-only; qty ≤ coop inventory of good
- `BID {good, max_price, qty}` — citizen buy (goods → citizen_inventory)
- `BID_FOR_COOP {coop_id, good, max_price, qty}` — member-only coop input purchase (goods → coop inventory, paid from treasury)
- `BUY_ESSENTIAL {good, qty}` — citizen, quota-capped, baseline price

## New Reason Codes

`GOOD_UNKNOWN`, `INVALID_QTY`, `INVALID_PRICE`, `INSUFFICIENT_FUNDS`, `NOT_ESSENTIAL`, `QUOTA_EXCEEDED`, `NOT_ENOUGH_INVENTORY`

## Settlement Records

Tick clearing writes one applied entry per good with listings or bids: listed qty, essential qty sold, bids, clearing price, winners (bidder, qty, price), seller proceeds, surplus delta. Full auditability of price formation on the Open Board.

## Tasks

- **P4-T1** `errors.py`: new reason codes
- **P4-T2** `rules.py`: new params + validation (+ update `params_with()` helpers in test_phase2/test_phase3)
- **P4-T3** `state.py`: coop treasury; citizen_inventory; surplus_pool; listings/bids tick-scoped storage; snapshot/hash coverage; money invariant helper `total_credits()`
- **P4-T4** `engine.py`: 4 actions + `_clear_markets(state)` at tick end (essential FCFS pass, then per-good uniform auction, then retirement); all deterministic
- **P4-T5** `test_phase4.py`: listing/bid/essential validation battery; clearing math on scripted scenarios (single bid at floor = no surplus; two bids = uniform price; pool retirement at cap; pro-rata multi-seller); invariant v2; tamper/replay determinism with markets
- **P4-T6** Baseline stability campaign (the phase gate): multi-co-op scripted economy (farmers/grain → millers/flour → bakers/bread + citizens buying) across 30+ ticks; assert invariant, no negative balances/inventories, surplus monotone, retirement beyond cap, replay identical

## Definition of Done

- [x] All market unit tests green
- [x] Baseline campaign green
- [x] Phases 1–3 tests green (schema updated)
- [x] Invariant v2 enforced in fuzz + campaign

## Out of Scope

Surplus outflow allocation (Phase 5 voting), wages from treasury (Phase 5), crisis auto-triage (Phase 6), pro-rata rationing under scarcity (Phase 6), bots (Phase 7)
