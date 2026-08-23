# Stage 4 — Breadth: All 39 Goods

## Goal
Every good in the catalog has at least one producer co-op; citizen needs are
met with **endowments switched off**. The economy bootstraps its own capital
chain from nothing.

## Survey findings
- 2 goods have NO recipe: `heating_fuel`, `medicine` → new recipes needed
- ~24 recipes exist but no baseline co-op runs them → new co-ops + specialists
- Citizen needs today: bread/water/electricity only → expand to food variety,
  clothing, healthcare, education, housing, transport, heating_fuel
- Bootstrap deadlock risk: nearly every extraction recipe consumes hand_tools;
  with zero endowments the metal chain can never start → **primitive_tools**
  recipe (labor-only, low yield) lets society bootstrap tools from bare labor

## Design
### 1. New recipes (catalog.py)
- `heating_fuel_refining`: coal 2 + water 1 → heating_fuel 10 (energy 4, labor 8)
- `herbal_medicine`: fruit 5 + water 2 → medicine 3 (energy 1, labor 10)
- `primitive_toolmaking`: labor 25, energy 0 → hand_tools 1 (the bootstrap)

### 2. New co-ops + specialists (server.py)
| Co-op | Recipe | Members |
|---|---|---|
| fishery | fishing | fisher_a/b |
| orchard_co | orchard | orchard_a/b |
| vegetable_farm | vegetable_farming | veg_a/b |
| livestock_co | livestock | herder_a/b |
| dairy | cheesemaking | dairy_a/b |
| cannery | canning | canner_a/b |
| kitchen | meal_service | cook_a/b |
| weavers | fabric_weaving | weaver_a/b |
| tailors | clothing_sewing | tailor_a/b |
| printshop | book_printing | printer_a/b |
| furniture_shop | furniture_craft | carpenter_a/b |
| household_co | household_goods_craft | homewright_a/b |
| brickworks | brickmaking | brickmaker_a/b |
| quarry_co | quarrying | quarryman_a/b |
| housing_guild | housing_service | builder_a/b |
| clinic | healthcare_service | healer_a/b |
| school | education_service | teacher_a/b |
| childcare_co | childcare_service | carer_a/b |
| transport_co | transport_service | driver_a/b |
| maintenance_co | maintenance_service | fixer_a/b |
| fuel_works | heating_fuel_refining | refiner_a/b |
| apothecary | herbal_medicine | herbalist_a/b |

### 3. Expanded citizen needs (votable rule param)
bread 1 · water 1 · electricity 1 · vegetables 0.25 · fruit 0.25 ·
meat 0.2 · milk 0.2 · eggs 0.2 · cheese 0.05 · meals 0.1 · fish 0.15 ·
clothing 0.02 · healthcare 0.01 · education 0.005 · childcare 0.01 ·
housing 0.002 · transport 0.1 · heating_fuel 0.1 · medicine 0.005 ·
maintenance 0.01 · books 0.01 · furniture 0.002 · household_goods 0.01
(integer quotas per tick via ×1000 scaling or per-N-tick consumption)

### 4. Endowments-off gate (`scripts/stage4_gate.py`)
- CAPITAL_BOOTSTRAP = {} · BASELINE_TREASURIES = {} · pantry = bread/water only
- one-time seed: each extraction coop gets 1 primitive-tool worker action
- PASS: zero unmet needs after transient (t>100), money invariant exact,
  all sectors producing, gini bounded, loop closure ≥ 0.6

## Non-goals
- No new engine mechanisms (uses existing phases)
- No UI changes beyond goods table naturally showing more rows

## Verification
- Unit tests: new recipes valid, primitive toolmaking bootstraps chain,
  expanded needs consumable
- Gate: 3 seeds × 2,000 ticks, endowments off, zero unmet
