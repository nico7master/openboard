# Stage 3 Spec: Competition & Real Capital (roadmap-approved)

## Goal
Co-ops buy their machines and tools from other co-ops. The economy
builds its own capital end-to-end. capital_refresh scaffolding retired
from baseline. Real competition in at least two sectors.

## Design
1. Toolsmith chain as new coops (all recipes already in catalog):
   loggers (logging->timber), sawmillers (sawmill->lumber),
   iron_miners (iron_mining->iron_ore), steelworkers (steelmaking),
   sand_workers (sand_extraction), glassmakers (glassmaking),
   electronics_workers (electronics_assembly), toolmakers
   (hand_tools_craft), machinists (machine_building).
2. Capital purchase needs NO engine change: recipe inputs already flow
   through BID_FOR_COOP; toolmakers/machinists LIST at cost floor like
   every other producer. Capital burns per run (existing mechanics),
   rent flows to capital_fund (existing), replacement is now a MARKET
   purchase instead of a rule.
3. Bootstrap: one-time documented endowment injection (hand_tools for
   extraction coops to break the chicken-and-egg; machines for iron
   mining; treasuries). Smaller than before — society builds the rest.
4. Retire capital_refresh in baseline params (rule stays available for
   adversarial what-if study).
5. Competition: second producer coops in grain (farmers_north) and
   bread (city_bakers), 1 member each — market power oversight gets a
   real competitor signal; resilience improves.

## Gate
- 3 seeds x 2000 ticks: zero unmet needs, invariants exact
- capital self-sustained: capital_burned > 0 with capital_refresh OFF
  and toolmakers/machinists producing steadily (no endowment top-ups
  after bootstrap) tools/machines actually trade (ledger contains BID_FOR_COOP fills
  on hand_tools/machines)
- resilience: grain supply continues if one grain coop stops producing
- all tests green
