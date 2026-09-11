# Spec — Policy Realism Contracts (effect-fidelity gate)

Status: APPROVED (user, 2026-09-11 "Do that!"). Target restated by the user:
**"Every new policy we add should reflect what really happens in the real
world — not all details, but the effect. Simulate the real world close
enough to study the effects."**

This spec defines a standing gate (like the survival gate) plus the five
mechanism fixes that close our current effect-fidelity gaps. Detail-
simulation is explicitly out of scope; mechanism fidelity is the product.

---

## Part I — The Contract Standard (applies to every future policy lever)

No policy lever lands without all three artifacts:

1. **Contract block** in the lever's spec: the real-world documented
   effect, with citation, expressed as exactly four fields:
   - DIRECTION (e.g. "inequality falls, output roughly holds")
   - MECHANISM (the causal chain the policy travels)
   - MAGNITUDE (rough real-world size, as an order of magnitude or range)
   - FLIP CONDITIONS (regime where the effect reverses, e.g. "tax above
     evasion threshold" or "price control below cost")
2. **Effect test** in `tests/`: automated, seed-pinned, asserting the sim
   reproduces direction AND mechanism signature (the intermediate steps,
   not just the endpoint). Failure modes are tested too — a lever whose
   absence-causes-wrong-behavior claim is part of the contract (e.g.
   `test_free_credit_causes_overborrowing`).
3. **Robustness band**: the effect holds across >=3 seeds and a parameter
   band (the harvest-rerun sweeps harness pattern). Single-seed proofs
   are not contracts.

Enforcement: contract tests join the 425-test suite; a red contract test
blocks merge exactly like a red survival gate. Every contract test cites
its spec section in its docstring.

Existing levers already passing the standard (audited 2026-09-11):
wealth-tax+dividend (54-run grid, top-1% 50->5.2bp, all fed), skills
premium, demand-memory/adaptive expectations, perishability, capital
starvation under credit constraints (emergent, probe-verified), durable
capital wear. They get retrofit contract tests in backlog order.

---

## Part II — The five mechanism fixes (priority order)

### Lever 1 — Interest on loans (smallest effort, immediate fidelity gain)

- **DIRECTION**: positive interest prices time; free credit causes
  over-borrowing and no rationing discipline; interest above return
  chokes investment.
- **MECHANISM**: interest raises the cost of carrying principal ->
  borrowing shrinks toward high-return uses; lenders (the society pool)
  earn carry -> pool grows in tight-money regimes.
- **MAGNITUDE**: real central-bank rates 0-15%/yr; credit-union/mutual
  rates 2-8%. A tick = 1 day, so rate_bp per loan term must be annualized
  (default 500bp/yr => ~1.4bp/day, charged at REPAY).
- **FLIP**: crisis mode can zero rates (solidarity credit, like real
  emergency lending facilities).
- **Implementation**: LOAN records principal + annual rate at issue;
  REPAY computes interest = principal * rate_bp * days_outstanding //
  10000 // 365; interest flows to surplus_pool (society earns the carry,
  nobody privatizes it). Default handler unchanged.
- **Contract tests**: `test_loan_charges_interest` (repay > principal
  after N ticks), `test_free_credit_causes_overborrowing` (rate=0 world
  borrows more and defaults more than rate=500bp world),
  `test_crisis_zeroes_rates`.

### Lever 2 — Scarcity pricing (price discovery above floors)

- **DIRECTION**: persistent excess demand -> price rises above cost
  (rationing + attract supply); glut -> price sags toward clearance;
  administered prices produce chronic shortages (Kornai).
- **MECHANISM**: markup allowed proportional to persistent unserved bids
  (scarcity signal), decaying back to cost as supply responds. This is
  the missing inflation/deflation channel — the deflation study
  (2026-09-07) already proved its absence distorts conclusions.
- **MAGNITUDE**: markup cap votable (default +25%); decay half-life ~10
  ticks; essentials keep oversight-council watch for price-gouging flags.
- **FLIP**: sub-floor clearance already exists (WP1.1); crisis price
  caps can suspend markup (real anti-gouging rules).
- **Implementation**: LIST_GOOD accepts optional `markup_bp` <= cap;
  listing price = floor + floor*markup_bp//10000; markup allowed only
  while `unserved_bids[good] > 0` persists (demand_memory signal);
  oversight flags markup>threshold on essentials.
- **Contract tests**: `test_scarcity_raises_price` (unserved bids ->
  listings clear above floor), `test_markup_decays_after_shortage_ends`,
  `test_price_cap_stops_gouging_flag_not_market`.

### Lever 3 — Research -> productivity (endogenous growth; the deepest gap)

- **DIRECTION**: R&D spending raises output per hour (TFP); >50% of
  long-run growth in real economies is TFP, not factor accumulation
  (Solow residual; endogenous-growth literature).
- **MECHANISM**: the two-layer design the user already approved
  (memory, 2026-09): global innovation pool (votable share of surplus)
  -> field allocation via citizen demand voting (linear fractional
  voting, crisis override suspends priorities) -> allocation feeds
  ENGINE EFFECTS, which today do not exist (verified: research.py has
  zero engine.py call sites).
- **Engine effects** (added): field level >= threshold grants scaled
  output bonuses to recipes in that field (food/health/energy/
  infrastructure/computing map onto recipe categories already in the
  catalog); top-tier allocation in a field for K consecutive ticks
  unlocks one cataloged variant recipe (cheaper input mix, same output)
  — technology as unlocked recipes, not floating multipliers.
- **MAGNITUDE**: max output bonus ~+25% per field at full sustained
  funding; variant unlock ~-30% one input. Growth is bounded and
  lumpy, like real TFP.
- **FLIP**: crisis redirects all innovation funding to the crisis field
  (already implemented in crisis.py); research does not instantly
  transfer between fields (1-field-per-coop lockout ticks).
- **Contract tests**: `test_funded_field_raises_output`,
  `test_unfunded_field_does_not`, `test_crisis_redirects_innovation`,
  `test_variant_unlock_lowers_input_cost`.

### Lever 4 — Land (structural inequality channel)

- **DIRECTION**: ownership of non-produced fixed assets (land) is a
  primary driver of persistent inequality (Ricardo; George; Piketty's
  r>g); land rent accrues to owners without production.
- **MECHANISM**: fixed stock of land units at genesis; housing/food
  recipes consume land services; land ownable, rentable at market;
  wealth tax already covers land values (no new tax needed).
- **MAGNITUDE**: land services = small but mandatory input share in
  housing + agriculture recipes; fixed supply => rent rises with
  population/growth.
- **FLIP**: the wealth tax + dividend loop is our counter-design;
  contract test must show land concentration WITH tax stays bounded vs
  WITHOUT tax diverges — the two levers fight, like reality.
- **Effort**: ~1 week (catalog, founding distribution, recipes, tests).

### Lever 5 — Foreign sector (terms of trade)

- **DIRECTION**: open economies dampen domestic shortages via imports
  and leak demand via exports; world-price exposure transmits external
  shocks (biggest real-world stressor class we cannot currently deploy).
- **MECHANISM**: one external price-taker market per good (world price =
  baseline * exogenous factor, seeded random walk); coops may BID/SELL
  to it; imports when world < domestic, exports when world > domestic.
- **MAGNITUDE**: world factor band 0.7-1.3x; shock module gains
  `trade_shock` kind (export collapse, import price spike).
- **FLIP**: crisis can suspend exports for essentials (real export
  bans); society-pool tariffs possible later as votable rule.
- **Effort**: ~1 week + adversary-lab integration.

---

## Part III — Order of execution and gates

1. Lever 1 (interest) — hours. Lever 2 (scarcity pricing) — ~1 day.
   Both land under the normal protocol: fingerprint-style equivalence
   where applicable (LOAN changes are opt-in per tx so no replay risk),
   contract tests, full suite, sweeps band.
2. Lever 3 (research) — ~1 day + design pass reconciling with the
   user's two-layer voting design; lands behind its contract tests.
3. Levers 4-5 — separate specs (week scale), sequenced AFTER the
   performance gate (regional markets) since both add per-tick work.
4. Retrofit contract tests for the six existing passing levers —
   background task, no rush.

Every lever must keep: money invariant exact, essentials gate, and the
established distribution results (the wealth-tax win must survive
scarcity pricing — that combination test is part of lever 2's band).

---

## Honest limit (standing)

Contracts guarantee DIRECTION + MECHANISM + rough MAGNITUDE vs documented
reality. Sim numbers are indicative ranges, not forecasts. The gate's
promise: a policy that passes its realism contract behaves in sim the way
it behaves in the real world for the mechanism under study — so studying
effects here transfers to reality at the level decisions need.
