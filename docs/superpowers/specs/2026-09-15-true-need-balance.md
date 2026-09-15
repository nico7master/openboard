# 2026-09-15 True-Need Balance (kcal model, capacity rescale, founding unlock)

**Status:** APPROVED by user 2026-09-15 ("okay balance everything out as it
should be!") following the findings presentation: quota basket demanded
~81,000 kcal/citizen/tick (~35× physiology), triple-counted starch
(grain+flour+bread), forced identical 12-food diets, installed essential
capacity covered only 2–62% of declared need, founding structurally dead
(founder stay-rule + 6 founders for 966 citizens), member cap 20 an
undocumented throughput ceiling.

## 1. Calorie-true food model (replaces the forced 12-food basket)

Real requirement: ~2,300 kcal/day; intake target ~2,800 with activity + waste
margin. Citizens eat a CALORIE BUDGET, not a fixed shopping list:

### 1a. Citizen `needs` basket (new default)

| good | old quota | new quota | kcal/unit (game serving) | kcal |
|---|---|---|---|---|
| grain | 10 | **0 (dropped — intermediate: mill/livestock input)** | 3,400 | – |
| flour | 5 | **0 (dropped — intermediate)** | 3,600 | – |
| bread | 4 | **1** | 650 (250g loaf) | 650 |
| meals | 3 | **1** | 700 (hot meal) | 700 |
| vegetables | 8 | **1** | 400 | 400 |
| fruit | 5 | **1** | 250 | 250 |
| eggs | 6 | **2** | 80 (piece) | 160 |
| fish | 4 | **1** | 200 (serving) | 200 |
| meat | 2 | **1** | 250 (serving) | 250 |
| milk | 6 | **1** | 300 (glass) | 300 |
| canned_food | 3 | **0 (dropped — emergency stock good, not daily)** | – | – |
| cheese | 1 | **0 (dropped — preference market good)** | – | – |
| **Total** | | | | **~2,910** |

### 1b. kcal substitution (engine, opt-in `kcal_needs` param)

`kcal_needs = {enabled, daily_kcal: 2900, kcal_per_unit: {...}}` (OPTIONAL_PARAMS;
absent → legacy per-good behavior, replay-safe).

- `_consume_phase`: foods in `kcal_per_unit` form a SUBSTITUTION GROUP. Engine
  eats held units up to the per-good preference cap (variety), sums kcal; the
  group is UNMET only when kcal < daily_kcal → single streak key `"food"`.
  Per-food starvation keys end for foods — missing your favorite is preference
  disappointment, not hunger.
- `personal_needs` (bots): deterministic taste-hash diet per citizen (staple
  bread/meals for all + 2–3 sides; some never buy fish). Buy rule: pantry kcal
  < 2 days budget → buy diet foods up to preference caps.
- Downstream keys: society probe unmet set becomes {"food", "water"};
  entrepreneur shortage map: `"food"` → found/join ANY kcal good producer that
  is under-capacity; crisis triage: "food" emergency-eligible.

### 1c. Other physical quotas

| good | old | new | rationale |
|---|---|---|---|
| water | 10 | **3** | drinking + cooking (3L); cleaning rides housing/maintenance |
| electricity | 50 | **12** | ~12 kWh/day/person (unit = kWh) |
| heating_fuel | 20 | **6** | temperate-climate average day |
| housing | 1/tick | **1 per 360 ticks** (needs_cycle) | a house lasts a year, not a day |
| clothing | 2/tick | **1 per 30 ticks** | garments last |
| furniture | 1/tick | **1 per 360 ticks** | durables |
| household_goods | 2/tick | **1 per 30 ticks** | durables |
| maintenance | 2/tick | **1 per 30 ticks** | periodic |
| books | 2/tick | **1 per 90 ticks** | durables-ish |
| education | 1/tick | **1 per 10 ticks** | sessions |
| childcare | 2/tick | **1 per 5 ticks** | sessions |
| healthcare | 2/tick | **1 per 10 ticks** | visits |
| medicine | 1/tick | **1 per 30 ticks** | courses |
| transport | 4/tick | **2/tick** | daily commute |

## 2. Recipe capacity rescale (close the labor-budget identity)

Identity: `workers_needed = need_per_tick × hrs_per_run ÷ (8 × out_per_run)`.
Target: installed capacity ≥ need × ~1.2 at the NEW quotas (966 citizens).

| recipe (good) | hrs/run | out/run old→new | workers installed | new capacity/tick | new need/tick |
|---|---|---|---|---|---|
| water_treatment (water) | 120 | 320→**800** | 66 | 3,520 | 2,898 |
| power (electricity) | 105 | 600→**4,000** | 44 | ~12,000 | 11,592 |
| fuel_works (heating_fuel) | 32 | 40→**800** | 39 | 7,800 | 5,796 |
| egg_farming (eggs) | 480→**60** | 144→**300** | 88 | 3,520 | 1,932 |
| dairy (milk) | 480→**60** | 144→**600** | 88 | 7,040 | 966 |
| livestock (meat) | 480→**60** | 144→**400** | 88 | 4,693 | 966 |
| fishery (fish) | 90→**60** | 150→**400** | 22 | 1,173 | 966 |
| grain_farming (grain) | 280→**200** | 700→**1,500** | 63 | 3,780 | chain demand |
| milling (flour) | 6 | 27→**150** | 17 | 3,400 | chain demand |
| bread_making (bread) | 15 | 100→**400** | 45 | 9,600 | 966 |
| kitchen (meals) | 24 | 40→**300** | 39 | 3,900 | 966 |
| vegetable_farm (vegetables) | 200→**80** | 320→(keep) | 39 | 1,248 | 966 |
| orchard (fruit) | 105→**60** | 180→**400** | 28 | 1,493 | 966 |
| builders (housing) | 300→**120** | 6→**24** | 22 | 352 | ~2.7 steady |
| transport_co (transport) | 10→**30** | 40→**800** | 11 | 2,346 | 1,932 |
| childcare/education/health/medicine/books/tailors | moderate | batch ×10–12 | – | ≥ need | cycle-scaled |

(members/coops grow dynamically via the founding lever below — static numbers
get close, founders close residual gaps.)

## 3. Founding lever: finish the unlock

1. **Stay-rule fix (bots.entrepreneur):** a seated founder LEAVES when their
   coop's own output good is under-capacity (demand_ema vs need) — they were
   absorbed at t=6 and neutralized forever; mobility is their job.
2. **Founder cast scales:** `founders = max(4, population // 100)` at genesis
   (server.py) and topped up by `scale_world` (harness) — 6 hardcoded was a
   village constant.
3. **Under-capacity signal stays** (demand_ema vs pop×quota — shipped
   2026-09-14); need maps now come from the new basket; food maps to the
   under-capacity kcal good set.

## 4. Member cap 20 → 50 (votable)

No documented rationale ever existed; engine fallback (12) disagreed with
ruleset (20). New: `max_coop_members: 50` in defaults, fallback aligned.
Everything stays rule-change/votable in-game. ≥2-producers-per-essential is
served by founder targeting (join smallest WITH room, else found) + the
single-producer candidate rule: an essential with exactly 1 producer and
non-trivial demand is founding-grade.

## 5. Research: bigger honest multiplier

`max_output_bonus_bp` default 2,500 (+25%) → **5,000 (+50%)**, same +250bp per
10k funding step, reserve-floor protection unchanged. Research becomes a real
growth dial over the now-sane base (user requirement: research raises
production by percents).

## 6. Verification

1. New unit tests: kcal group consume semantics; diet buying; founder leave rule.
2. Full regression via memrun (expect fixture updates where old basket totals
   were encoded — recorded-param worlds replay unchanged).
3. **Proof world:** 650 ticks, 966 citizens: coops must EXCEED 124 (net new
   foundings), food/water unmet ≈ 0 at stable state, money conservation exact.
4. Capacity audit re-run: every essential ≥ ~100% coverage.
