"""OpenBoard engine server — the dashboard backend and seed of the game.

Owns ONE run in memory: world state, ledger, bot roster, pending human
actions, recorded batches, injections, a metrics timeline, and a rolling
event feed. Human actions join the next tick's batch — nothing mutates
state outside the engine's tick discipline.

Spec: docs/superpowers/specs/2026-08-21-dashboard-server-design.md
"""

from __future__ import annotations

import copy
import json
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openboard.bots import ARCHETYPES  # noqa: E402
from openboard.breaksystem import PLAYBOOKS, ROUND_TICKS, STOP_FLAGS, STOP_UNMET, attack_score, attack_tick, capture_baseline, invariants_ok, round_verdict  # noqa: E402
from openboard.accounts import Accounts  # noqa: E402
from openboard.story import build_story  # noqa: E402
from openboard.flows import build_flows  # noqa: E402
from openboard.engine import loan_owed, apply_tick  # noqa: E402
from openboard.ledger import Ledger, Transaction  # noqa: E402
from openboard.metrics import SimMetrics, gini  # noqa: E402
from openboard.rules import DEFAULT_RULESET_PARAMS  # noqa: E402
from openboard.politics import make_politician  # noqa: E402
from openboard.sim import make_specialist  # noqa: E402
from openboard.state import WorldState, genesis_state  # noqa: E402

SAVE_FORMAT = "openboard-run-v2"

# stock_target = produce while stock+listed < target. Utilities serve the
# WHOLE economy (14 citizens + industry), so their buffers must exceed any
# single consumer's daily flow — under-sized targets starve downstream
# coops (auction bidders lose to FCFS citizens every tick).
def _coop_recipe_intent(plan: dict) -> str | None:
    """Declared trade for a founded coop: the recipe its first specialist
    member runs. Used by society's founding equipment grant."""
    from openboard.catalog import EXTENDED_RECIPES, RECIPES
    # BASELINE_BOTS: (citizen, specialist_fn, coop) — the exact mapping
    bot_of = {name: fn for name, fn, _ in BASELINE_BOTS}
    for m in plan["members"]:
        fn = bot_of.get(m)
        if fn is None:
            # fallback: role name = citizen minus trailing _<letter>
            role = m.rsplit("_", 1)[0]
            fn = SPECIALISTS.get(role)
        rid = getattr(fn, "recipe_id", None)
        # extended recipes count too: steelworks/machine_works run *_batch
        # recipes from EXTENDED_RECIPES — excluding them founded those
        # coops with intent=None and the first-run advance skipped them
        # (observed: steelworks/machine_works frozen at treasury 0 forever)
        if isinstance(rid, str) and (rid in RECIPES or rid in EXTENDED_RECIPES):
            return rid
    return None


SPECIALISTS = {
    "farmer": make_specialist("grain_farming", "grain", {"water": 5}, stock_target=450),
    "miller": make_specialist("grain_to_flour", "flour", {"grain": 10}, stock_target=260),
    "baker": make_specialist("flour_to_bread", "bread", {"flour": 5}, stock_target=420),
    "miner": make_specialist("coal_mining", "coal", {}, stock_target=120, fallback_recipe_id="primitive_coal_mining"),
    "power_worker": make_specialist("electricity_coal", "electricity", {"coal": 4}, stock_target=250),
    "water_worker": make_specialist("water_service", "water", {"electricity": 5}, stock_target=250),
    # Stage 3: toolsmith chain (recipes live in the extended catalog)
    "logger": make_specialist("logging", "timber", {}, stock_target=40, fallback_recipe_id="primitive_logging"),
    "sawyer": make_specialist("sawmill", "lumber", {"timber": 5}, stock_target=40),
    "iron_miner": make_specialist("iron_mining", "iron_ore", {}, stock_target=60, fallback_recipe_id="primitive_iron_mining"),
    "steelworker": make_specialist("steelmaking_batch", "steel", {"iron_ore": 20, "coal": 12}, stock_target=60),
    "sand_worker": make_specialist("sand_extraction", "sand", {}, stock_target=60, fallback_recipe_id="primitive_sand_extraction"),
    "glassmaker": make_specialist("glassmaking", "glass", {"sand": 4}, stock_target=40),
    "electronics_worker": make_specialist("electronics_assembly", "electronics", {"steel": 1, "glass": 2, "coal": 1}, stock_target=30),
    "toolmaker": make_specialist("hand_tools_craft", "hand_tools", {"steel": 2, "lumber": 1}, stock_target=60, fallback_recipe_id="primitive_toolmaking"),
    # 2026-09-01: circular capital chain deadlock fix — tools need steel,
    # steel needs iron mining, iron mining needs tools. With zero steel listings
    # the sole toolmaker idled forever (hand_tools 0 economy-wide).
    # primitive_toolmaking (25 labor, no inputs) breaks the circle; the bridge
    # retires once steel returns via the exit ramp.
    "machinist": make_specialist("machine_building_batch", "machines", {"steel": 20, "electronics": 6, "glass": 4}, stock_target=25),
    # Competition: second power producer
    "wind_worker": make_specialist("wind_farm", "electricity", {}, stock_target=250),
    # Stage 4: breadth — every good has a producer
    "fisher": make_specialist("fishing", "fish", {}, stock_target=60),
    "orchardist": make_specialist("orchard", "fruit", {"water": 4}, stock_target=80),
    "vegetable_farmer": make_specialist("vegetable_farming", "vegetables", {"water": 6}, stock_target=100),
    "herder": make_specialist("livestock", "meat", {"grain": 20, "water": 10}, stock_target=40),
    "dairy_worker": make_specialist("cheesemaking", "cheese", {"milk": 40}, stock_target=30),
    "canner": make_specialist("canning", "canned_food", {"vegetables": 8, "fruit": 4}, stock_target=40),
    "cook": make_specialist("meal_service", "meals", {"vegetables": 3, "meat": 2, "bread": 2}, stock_target=40),
    "weaver": make_specialist("fabric_weaving", "fabric", {"grain": 2, "water": 3}, stock_target=120),
    "tailor": make_specialist("clothing_sewing", "clothing", {"fabric": 10}, stock_target=20),
    "printer": make_specialist("book_printing", "books", {"fabric": 1, "water": 1}, stock_target=20),
    "carpenter": make_specialist("furniture_craft", "furniture", {"lumber": 3, "fabric": 2, "steel": 1}, stock_target=15),
    "homewright": make_specialist("household_goods_craft", "household_goods", {"steel": 1, "glass": 1, "fabric": 1}, stock_target=25),
    "brickmaker": make_specialist("brickmaking", "bricks", {"sand": 3, "water": 2}, stock_target=400),
    "quarryman": make_specialist("quarrying", "stone", {}, stock_target=60, fallback_recipe_id="primitive_quarrying"),
    "builder": make_specialist("housing_service", "housing", {"lumber": 2, "bricks": 50, "steel": 1}, stock_target=10),
    "healer": make_specialist("healthcare_service", "healthcare", {}, stock_target=20),
    "teacher": make_specialist("education_service", "education", {}, stock_target=10),
    "carer": make_specialist("childcare_service", "childcare", {}, stock_target=20),
    "driver": make_specialist("transport_service", "transport", {"electricity": 10}, stock_target=60),
    "fixer": make_specialist("maintenance_service", "maintenance", {"hand_tools": 1}, stock_target=20),
    "refiner": make_specialist("heating_fuel_refining", "heating_fuel", {"coal": 2, "water": 1}, stock_target=60),
    "herbalist": make_specialist("herbal_medicine", "medicine", {"fruit": 5, "water": 2}, stock_target=20),
    # Endowments-off bootstrap: labor-only toolmaking lets society make
    # its first tools by hand when no capital seeds exist
    "toolwright": make_specialist("primitive_toolmaking", "hand_tools", {}, stock_target=30),
}

BASELINE_BOTS: list[tuple[str, Any, str]] = [
    # (name, decision fn, coop)
    ("farmer_a", SPECIALISTS["farmer"], "farmers"),
    ("farmer_b", SPECIALISTS["farmer"], "farmers"),
    ("farmer_e", SPECIALISTS["farmer"], "farmers"),
    ("farmer_f", SPECIALISTS["farmer"], "farmers"),
    ("miller_a", SPECIALISTS["miller"], "millers"),
    ("miller_b", SPECIALISTS["miller"], "millers"),
    ("miller_c", SPECIALISTS["miller"], "millers"),
    ("baker_a", SPECIALISTS["baker"], "bakers"),
    ("baker_b", SPECIALISTS["baker"], "bakers"),
    ("baker_e", SPECIALISTS["baker"], "bakers"),
    ("miner_a", SPECIALISTS["miner"], "miners"),
    ("miner_b", SPECIALISTS["miner"], "miners"),
    ("miner_c", SPECIALISTS["miner"], "miners"),
    ("miner_d", SPECIALISTS["miner"], "miners"),
    ("miner_e", SPECIALISTS["miner"], "miners"),
    ("miner_f", SPECIALISTS["miner"], "miners"),
    ("miner_g", SPECIALISTS["miner"], "miners"),
    ("miner_h", SPECIALISTS["miner"], "miners"),
    ("miner_i", SPECIALISTS["miner"], "miners"),
    ("miner_j", SPECIALISTS["miner"], "miners"),
    ("miner_k", SPECIALISTS["miner"], "miners"),
    ("miner_l", SPECIALISTS["miner"], "miners"),
    ("power_d", SPECIALISTS["power_worker"], "power_plant"),
    ("power_a", SPECIALISTS["power_worker"], "power_plant"),
    ("power_b", SPECIALISTS["power_worker"], "power_plant"),
    ("power_c", SPECIALISTS["power_worker"], "power_plant"),
    ("water_a", SPECIALISTS["water_worker"], "water_works"),
    ("water_b", SPECIALISTS["water_worker"], "water_works"),
    ("water_e", SPECIALISTS["water_worker"], "water_works"),
    ("water_f", SPECIALISTS["water_worker"], "water_works"),
    ("worker_a", ARCHETYPES["honest_worker"], "farmers"),
    ("worker_b", ARCHETYPES["honest_worker"], "farmers"),
    # Stage 3: capital chain
    ("logger_a", SPECIALISTS["logger"], "loggers"),
    ("logger_b", SPECIALISTS["logger"], "loggers"),
    ("sawyer_a", SPECIALISTS["sawyer"], "sawmill_co"),
    ("sawyer_b", SPECIALISTS["sawyer"], "sawmill_co"),
    ("iron_a", SPECIALISTS["iron_miner"], "iron_miners"),
    ("iron_b", SPECIALISTS["iron_miner"], "iron_miners"),
    # 2026-09-01: capital-chain thickness (design review #3). A serial
    # chain of 2-member coops cannot refill a 20-ore steel run via
    # primitive bridges (~1.2 ore/tick) inside any recovery window.
    ("iron_c", SPECIALISTS["iron_miner"], "iron_miners"),
    ("iron_d", SPECIALISTS["iron_miner"], "iron_miners"),
    ("steel_a", SPECIALISTS["steelworker"], "steelworks"),
    ("steel_b", SPECIALISTS["steelworker"], "steelworks"),
    ("steel_c", SPECIALISTS["steelworker"], "steelworks"),
    ("sand_a", SPECIALISTS["sand_worker"], "sand_co"),
    ("sand_b", SPECIALISTS["sand_worker"], "sand_co"),
    ("glass_a", SPECIALISTS["glassmaker"], "glassworks"),
    ("glass_b", SPECIALISTS["glassmaker"], "glassworks"),
    ("elec_a", SPECIALISTS["electronics_worker"], "electronics_co"),
    ("elec_b", SPECIALISTS["electronics_worker"], "electronics_co"),
    ("tool_a", SPECIALISTS["toolmaker"], "toolworks"),
    ("tool_b", SPECIALISTS["toolmaker"], "toolworks"),
    ("tool_c", SPECIALISTS["toolmaker"], "toolworks"),
    ("mach_a", SPECIALISTS["machinist"], "machine_works"),
    ("mach_b", SPECIALISTS["machinist"], "machine_works"),
    ("mach_c", SPECIALISTS["machinist"], "machine_works"),
    # Competition: second power, grain, bread
    ("wind_a", SPECIALISTS["wind_worker"], "wind_farm"),
    ("wind_b", SPECIALISTS["wind_worker"], "wind_farm"),
    ("wind_c", SPECIALISTS["wind_worker"], "wind_farm"),
    ("wind_d", SPECIALISTS["wind_worker"], "wind_farm"),
    # 2026-09-02: grain margin — livestock runs burn 20 grain each; at the
    # old farmer count grain listings ran dry during cycle-day bursts and
    # livestock starved (milk streak 7). +2 herder-chain grain capacity.
    ("farmer_j", SPECIALISTS["farmer"], "farmers"),
    ("farmer_k", SPECIALISTS["farmer"], "farmers"),
    ("farmer_c", SPECIALISTS["farmer"], "farmers_north"),
    ("farmer_d", SPECIALISTS["farmer"], "farmers_north"),
    ("farmer_g", SPECIALISTS["farmer"], "farmers_north"),
    ("farmer_h", SPECIALISTS["farmer"], "farmers_north"),
    ("farmer_i", SPECIALISTS["farmer"], "farmers_north"),
    ("baker_g", SPECIALISTS["baker"], "bakers"),
    ("baker_c", SPECIALISTS["baker"], "city_bakers"),
    ("baker_d", SPECIALISTS["baker"], "city_bakers"),
    ("baker_f", SPECIALISTS["baker"], "city_bakers"),
    # Stage 4: breadth cast
    ("water_c", SPECIALISTS["water_worker"], "water_works_north"),
    ("water_d", SPECIALISTS["water_worker"], "water_works_north"),
    ("water_g", SPECIALISTS["water_worker"], "water_works_north"),
    ("water_h", SPECIALISTS["water_worker"], "water_works_north"),
    # third water utility: two coops (160 water/tick) left only ~9/tick
    # for ALL producers after 161 citizens drank — the master constraint
    # starved grain->flour->bread, livestock, fabric and books at once
    ("water_i", SPECIALISTS["water_worker"], "water_works_east"),
    ("water_j", SPECIALISTS["water_worker"], "water_works_east"),
    ("water_k", SPECIALISTS["water_worker"], "water_works_east"),
    ("water_l", SPECIALISTS["water_worker"], "water_works_east"),
    ("fisher_a", SPECIALISTS["fisher"], "fishery"),
    ("fisher_b", SPECIALISTS["fisher"], "fishery"),
    ("fisher_c", SPECIALISTS["fisher"], "fishery"),
    ("fisher_d", SPECIALISTS["fisher"], "fishery"),
    ("orchard_a", SPECIALISTS["orchardist"], "orchard_co"),
    ("orchard_b", SPECIALISTS["orchardist"], "orchard_co"),
    ("orchard_c", SPECIALISTS["orchardist"], "orchard_co"),
    ("orchard_d", SPECIALISTS["orchardist"], "orchard_co"),
    ("orchard_e", SPECIALISTS["orchardist"], "orchard_co"),
    ("veg_a", SPECIALISTS["vegetable_farmer"], "vegetable_farm"),
    ("veg_b", SPECIALISTS["vegetable_farmer"], "vegetable_farm"),
    ("veg_c", SPECIALISTS["vegetable_farmer"], "vegetable_farm"),
    ("veg_d", SPECIALISTS["vegetable_farmer"], "vegetable_farm"),
    ("veg_e", SPECIALISTS["vegetable_farmer"], "vegetable_farm"),
    ("veg_f", SPECIALISTS["vegetable_farmer"], "vegetable_farm"),
    ("veg_g", SPECIALISTS["vegetable_farmer"], "vegetable_farm"),
    ("herder_a", SPECIALISTS["herder"], "livestock_co"),
    ("herder_b", SPECIALISTS["herder"], "livestock_co"),
    ("herder_c", SPECIALISTS["herder"], "livestock_co"),
    ("herder_d", SPECIALISTS["herder"], "livestock_co"),
    ("herder_e", SPECIALISTS["herder"], "livestock_co"),
    ("herder_f", SPECIALISTS["herder"], "livestock_co"),
    ("herder_g", SPECIALISTS["herder"], "livestock_co"),
    ("herder_h", SPECIALISTS["herder"], "livestock_co"),
    ("rancher_a", SPECIALISTS["herder"], "livestock_north"),
    ("rancher_b", SPECIALISTS["herder"], "livestock_north"),
    ("rancher_c", SPECIALISTS["herder"], "livestock_north"),
    ("rancher_d", SPECIALISTS["herder"], "livestock_north"),
    ("rancher_e", SPECIALISTS["herder"], "livestock_north"),
    ("rancher_f", SPECIALISTS["herder"], "livestock_north"),
    ("rancher_g", SPECIALISTS["herder"], "livestock_north"),
    ("rancher_h", SPECIALISTS["herder"], "livestock_north"),
    ("dairy_a", SPECIALISTS["dairy_worker"], "dairy"),
    ("dairy_b", SPECIALISTS["dairy_worker"], "dairy"),
    ("dairy_c", SPECIALISTS["dairy_worker"], "dairy"),
    ("canner_a", SPECIALISTS["canner"], "cannery"),
    ("canner_b", SPECIALISTS["canner"], "cannery"),
    ("cook_a", SPECIALISTS["cook"], "kitchen"),
    ("cook_b", SPECIALISTS["cook"], "kitchen"),
    ("cook_c", SPECIALISTS["cook"], "kitchen"),
    ("cook_c", SPECIALISTS["cook"], "kitchen"),
    ("cook_d", SPECIALISTS["cook"], "kitchen"),
    ("cook_e", SPECIALISTS["cook"], "kitchen"),
    ("cook_f", SPECIALISTS["cook"], "kitchen"),
    ("cook_g", SPECIALISTS["cook"], "kitchen"),
    ("weaver_a", SPECIALISTS["weaver"], "weavers"),
    ("weaver_b", SPECIALISTS["weaver"], "weavers"),
    ("tailor_a", SPECIALISTS["tailor"], "tailors"),
    ("tailor_b", SPECIALISTS["tailor"], "tailors"),
    ("printer_a", SPECIALISTS["printer"], "printshop"),
    ("printer_b", SPECIALISTS["printer"], "printshop"),
    ("carpenter_a", SPECIALISTS["carpenter"], "furniture_shop"),
    ("carpenter_b", SPECIALISTS["carpenter"], "furniture_shop"),
    ("carpenter_c", SPECIALISTS["carpenter"], "furniture_shop"),
    ("carpenter_d", SPECIALISTS["carpenter"], "furniture_shop"),
    ("homewright_a", SPECIALISTS["homewright"], "household_co"),
    ("homewright_b", SPECIALISTS["homewright"], "household_co"),
    ("homewright_c", SPECIALISTS["homewright"], "household_co"),
    ("homewright_c", SPECIALISTS["homewright"], "household_co"),
    ("homewright_d", SPECIALISTS["homewright"], "household_co"),
    ("homewright_e", SPECIALISTS["homewright"], "household_co"),
    ("brickmaker_a", SPECIALISTS["brickmaker"], "brickworks"),
    ("brickmaker_b", SPECIALISTS["brickmaker"], "brickworks"),
    ("quarryman_a", SPECIALISTS["quarryman"], "quarry_co"),
    ("quarryman_b", SPECIALISTS["quarryman"], "quarry_co"),
    ("quarryman_c", SPECIALISTS["quarryman"], "quarry_co"),
    ("quarryman_d", SPECIALISTS["quarryman"], "quarry_co"),
    ("quarryman_e", SPECIALISTS["quarryman"], "quarry_co"),
    ("builder_a", SPECIALISTS["builder"], "housing_guild"),
    ("builder_b", SPECIALISTS["builder"], "housing_guild"),
    # housing was chronically underbuilt for 164 citizens: 2 builders
    # could not absorb brickworks' output (30k idle hours there) —
    # housing oscillated 86 unmet for 1,500 ticks
    ("builder_c", SPECIALISTS["builder"], "housing_guild"),
    ("builder_d", SPECIALISTS["builder"], "housing_guild"),
    ("healer_a", SPECIALISTS["healer"], "clinic"),
    ("healer_b", SPECIALISTS["healer"], "clinic"),
    ("teacher_a", SPECIALISTS["teacher"], "school"),
    ("teacher_b", SPECIALISTS["teacher"], "school"),
    ("teacher_c", SPECIALISTS["teacher"], "school"),
    ("teacher_d", SPECIALISTS["teacher"], "school"),
    ("teacher_e", SPECIALISTS["teacher"], "school"),
    ("teacher_f", SPECIALISTS["teacher"], "school"),
    ("carer_a", SPECIALISTS["carer"], "childcare_co"),
    ("carer_b", SPECIALISTS["carer"], "childcare_co"),
    ("driver_a", SPECIALISTS["driver"], "transport_co"),
    ("driver_b", SPECIALISTS["driver"], "transport_co"),
    ("fixer_a", SPECIALISTS["fixer"], "maintenance_co"),
    ("fixer_b", SPECIALISTS["fixer"], "maintenance_co"),
    ("fixer_c", SPECIALISTS["fixer"], "maintenance_co"),
    ("fixer_d", SPECIALISTS["fixer"], "maintenance_co"),
    ("fixer_e", SPECIALISTS["fixer"], "maintenance_co"),
    ("fixer_f", SPECIALISTS["fixer"], "maintenance_co"),
    ("refiner_a", SPECIALISTS["refiner"], "fuel_works"),
    ("refiner_b", SPECIALISTS["refiner"], "fuel_works"),
    ("refiner_c", SPECIALISTS["refiner"], "fuel_works"),
    ("refiner_c", SPECIALISTS["refiner"], "fuel_works"),
    ("refiner_d", SPECIALISTS["refiner"], "fuel_works"),
    ("refiner_e", SPECIALISTS["refiner"], "fuel_works"),
    ("refiner_f", SPECIALISTS["refiner"], "fuel_works"),
    ("refiner_g", SPECIALISTS["refiner"], "fuel_works"),
    ("herbalist_a", SPECIALISTS["herbalist"], "apothecary"),
    ("herbalist_b", SPECIALISTS["herbalist"], "apothecary"),
]

BASELINE_COOPS = [
    {"coop_id": "farmers", "members": ["farmer_a", "farmer_b", "farmer_e", "farmer_f", "farmer_j", "farmer_k", "worker_a", "worker_b"]},
    {"coop_id": "millers", "members": ["miller_a", "miller_b", "miller_c"]},
    {"coop_id": "bakers", "members": ["baker_a", "baker_b", "baker_e", "baker_g"]},
    {"coop_id": "miners", "members": ["miner_a", "miner_b", "miner_c", "miner_d", "miner_e", "miner_f", "miner_g", "miner_h", "miner_i", "miner_j", "miner_k", "miner_l"]},
    {"coop_id": "power_plant", "members": ["power_a", "power_b", "power_c", "power_d"]},
    {"coop_id": "water_works", "members": ["water_a", "water_b", "water_e", "water_f"]},
    {"coop_id": "loggers", "members": ["logger_a", "logger_b"]},
    {"coop_id": "sawmill_co", "members": ["sawyer_a", "sawyer_b"]},
    {"coop_id": "iron_miners", "members": ["iron_a", "iron_b", "iron_c", "iron_d"]},
    {"coop_id": "steelworks", "members": ["steel_a", "steel_b", "steel_c"]},
    {"coop_id": "sand_co", "members": ["sand_a", "sand_b"]},
    {"coop_id": "glassworks", "members": ["glass_a", "glass_b"]},
    {"coop_id": "electronics_co", "members": ["elec_a", "elec_b"]},
    {"coop_id": "toolworks", "members": ["tool_a", "tool_b", "tool_c"]},
    {"coop_id": "machine_works", "members": ["mach_a", "mach_b", "mach_c"]},
    {"coop_id": "wind_farm", "members": ["wind_a", "wind_b", "wind_c", "wind_d"]},
    {"coop_id": "farmers_north", "members": ["farmer_c", "farmer_d", "farmer_g", "farmer_h", "farmer_i"]},
    {"coop_id": "city_bakers", "members": ["baker_c", "baker_d", "baker_f"]},
    # Stage 4: breadth — all remaining sectors
    {"coop_id": "water_works_north", "members": ["water_c", "water_d", "water_g", "water_h"]},
    {"coop_id": "water_works_east", "members": ["water_i", "water_j", "water_k", "water_l"]},
    {"coop_id": "toolwrights", "members": ["wright_a", "wright_b", "wright_c", "wright_d"]},
    {"coop_id": "fishery", "members": ["fisher_a", "fisher_b", "fisher_c", "fisher_d"]},
    {"coop_id": "orchard_co", "members": ["orchard_a", "orchard_b", "orchard_c", "orchard_d", "orchard_e"]},
    {"coop_id": "vegetable_farm", "members": ["veg_a", "veg_b", "veg_c", "veg_d", "veg_e", "veg_f", "veg_g"]},
    {"coop_id": "livestock_co", "members": ["herder_a", "herder_b", "herder_c", "herder_d", "herder_e", "herder_f", "herder_g", "herder_h"]},
    {"coop_id": "livestock_north", "members": ["rancher_a", "rancher_b", "rancher_c", "rancher_d", "rancher_e", "rancher_f", "rancher_g", "rancher_h"]},
    {"coop_id": "dairy", "members": ["dairy_a", "dairy_b", "dairy_c"]},
    {"coop_id": "cannery", "members": ["canner_a", "canner_b"]},
    {"coop_id": "kitchen", "members": ["cook_a", "cook_b", "cook_c", "cook_d", "cook_e", "cook_f", "cook_g"]},
    {"coop_id": "weavers", "members": ["weaver_a", "weaver_b"]},
    {"coop_id": "tailors", "members": ["tailor_a", "tailor_b"]},
    {"coop_id": "printshop", "members": ["printer_a", "printer_b"]},
    {"coop_id": "furniture_shop", "members": ["carpenter_a", "carpenter_b", "carpenter_c", "carpenter_d"]},
    {"coop_id": "household_co", "members": ["homewright_a", "homewright_b", "homewright_c", "homewright_d", "homewright_e"]},
    {"coop_id": "brickworks", "members": ["brickmaker_a", "brickmaker_b"]},
    {"coop_id": "quarry_co", "members": ["quarryman_a", "quarryman_b", "quarryman_c", "quarryman_d", "quarryman_e"]},
    {"coop_id": "housing_guild", "members": ["builder_a", "builder_b", "builder_c", "builder_d"]},
    {"coop_id": "clinic", "members": ["healer_a", "healer_b"]},
    {"coop_id": "school", "members": ["teacher_a", "teacher_b", "teacher_c", "teacher_d", "teacher_e", "teacher_f"]},
    {"coop_id": "childcare_co", "members": ["carer_a", "carer_b"]},
    {"coop_id": "transport_co", "members": ["driver_a", "driver_b"]},
    {"coop_id": "maintenance_co", "members": ["fixer_a", "fixer_b", "fixer_c", "fixer_d", "fixer_e", "fixer_f"]},
    {"coop_id": "fuel_works", "members": ["refiner_a", "refiner_b", "refiner_c", "refiner_d", "refiner_e", "refiner_f", "refiner_g"]},
    {"coop_id": "apothecary", "members": ["herbalist_a", "herbalist_b"]},
]

# Input-buying coops need starting treasuries to bootstrap their chains.
BASELINE_TREASURIES = {
    "millers": 600, "bakers": 600, "power_plant": 600, "water_works": 600,
    "sawmill_co": 600, "glassworks": 600,
    "toolworks": 600, "city_bakers": 600, "farmers_north": 600,
    # heavy-batch coops: seeds cover MULTIPLE batch cycles until the
    # chain's internal trade reaches steady state (a machine batch alone
    # costs ~2,200cr in inputs; too-small seeds froze the chain mid-flight)
    "steelworks": 2_600, "electronics_co": 1_600, "machine_works": 4_200,
    # Stage 4: input-buying coops (600 covers several runs of their
    # recipes; housing is the heavy one: 50 bricks + lumber + steel/run)
    "maintenance_co": 1_800, "orchard_co": 600, "vegetable_farm": 600, "livestock_co": 600,
    "water_works_east": 600, "dairy": 600, "cannery": 600, "kitchen": 600, "weavers": 600,
    "tailors": 600, "printshop": 600, "furniture_shop": 600,
    "household_co": 600, "brickworks": 600, "housing_guild": 2_400,
    "transport_co": 600, "maintenance_co": 600, "fuel_works": 600,
    "apothecary": 600,
}
# Stage 3 one-time capital bootstrap: extraction coops get seed tools and
# machines ONLY at founding; every replacement is bought on the market
# from toolworks/machine_works at cost. Breaks the chicken-and-egg (nothing
# can be produced before tools exist) without a standing rule.
CAPITAL_BOOTSTRAP = {
    "loggers": {"hand_tools": 10},
    "sand_co": {"hand_tools": 10},
    "iron_miners": {"hand_tools": 5, "machines": 2},
    "miners": {"hand_tools": 5, "machines": 3},
    "power_plant": {"machines": 2},
}


# Stage 1 — democracy in the loop: a balanced electorate overlaid on the
# economic cast when governance is LIVE. Egalitarians (equality), a
# libertarian (low tax), pragmatists (fix shortages) — politics emerges
# from the same citizens who work and eat. Name-based so saves round-trip.
POLITICAL_ROLES = {
    "worker_a": "egalitarian",
    "worker_b": "egalitarian",
    "baker_a": "egalitarian",
    "farmer_b": "egalitarian",
    "miner_b": "egalitarian",
    "wind_a": "egalitarian",
    "baker_c": "egalitarian",
    "tool_a": "egalitarian",
    "glass_a": "egalitarian",
    "farmer_a": "libertarian",
    "miner_a": "libertarian",
    "power_b": "libertarian",
    "water_b": "libertarian",
    "water_j": "libertarian",
    "water_k": "pragmatist",
    "water_l": "egalitarian",
    "water_i": "pragmatist",
    "iron_a": "libertarian",
    "sawyer_a": "libertarian",
    "mach_a": "libertarian",
    "miller_a": "pragmatist",
    "miller_b": "pragmatist",
    "power_a": "pragmatist",
    "water_a": "pragmatist",
    "baker_b": "pragmatist",
    "logger_a": "pragmatist",
    "steel_a": "pragmatist",
    "elec_a": "pragmatist",
    "sand_a": "pragmatist",
}


def _wrap_politics(name: str, fn, governance: bool):
    role = POLITICAL_ROLES.get(name)
    if governance and role:
        return make_politician(fn, role)
    return fn


class Run:
    """One engine run: world, bots, timeline, feed, save/replay."""

    def __init__(self, seed: int = 42, governance: bool = False, scenario: str = "equal"):
        self.lock = threading.RLock()
        self.seed = seed
        self.governance = governance
        self.scenario = scenario
        self.autoplay = {"running": False, "interval": 0.75}

        # circular-flow params + governance via one source of truth
        citizens = {name: 500 for name, _, _ in BASELINE_BOTS}
        self.state: WorldState = genesis_state(citizens, ruleset_params=self._params())
        self.ledger = Ledger()
        self.metrics = SimMetrics()

        self.bots: dict[str, dict[str, Any]] = {}  # name -> {fn, coop}
        self.pending: list[Transaction] = []
        self.batches: dict[int, list[dict[str, Any]]] = {}  # tick -> tx dicts
        self.injections: list[dict[str, Any]] = []  # recorded state edits

        self.timeline = {"tick": [], "gini": [], "money": [], "surplus": [],
                         "produced": [], "bought": [],
                         "produced_cat": {}, "bought_cat": {},
                         "consumed": [], "dividends": [], "unmet": []}
        self.feed: list[dict[str, Any]] = []  # rolling events
        self.totals: dict[str, dict[str, int]] = {"produced": {}, "bought": {}}
        self._last_events: list[dict[str, Any]] = []

        # tick 1: founding (each coop declares its trade so society can
        # equip it before its first shift if it lacks capital seeds)
        founding = [
            Transaction(tick=1, sender=plan["members"][0], action="FOUND_COOP",
                        payload={"coop_id": plan["coop_id"], "name": plan["coop_id"],
                                 "members": plan["members"],
                                 "recipe_id": _coop_recipe_intent(plan)},
                        ruleset_version=1)
            for plan in BASELINE_COOPS
        ]
        self._apply_batch(1, founding)
        _upc = int(self._params().get("money_cap", {}).get("units_per_credit", 100)) if self._params().get("money_cap", {}).get("enabled") else 1
        for coop, amount in BASELINE_TREASURIES.items():
            self._inject({"after_tick": 1, "op": "treasury", "coop": coop, "amount": amount * _upc})
        # one-time capital seed (recorded injection, replayed on load)
        for coop, goods in CAPITAL_BOOTSTRAP.items():
            self._inject({"after_tick": 1, "op": "capital", "coop": coop, "goods": goods})
        # starting pantry: 3 days of essentials so the bootstrap transient
        # (first production/sales ticks) never registers as unmet need
        for name, _, _ in BASELINE_BOTS:
            self._inject({"after_tick": 1, "op": "pantry", "citizen": name,
                          "goods": {"bread": 3, "water": 3, "electricity": 3}})
        for name, fn, coop in BASELINE_BOTS:
            self.bots[name] = {"fn": _wrap_politics(name, fn, self.governance), "coop": coop}
        # 2026-09-01: A2's entrepreneur bot was built and tested but never
        # wired into the live cast (all citizens pre-seated as specialists;
        # the 43 FOUND_COOP events were genesis scenario coops). Meanwhile
        # the capital chain starved 400 ticks (hand_tools 7,741 coop bids
        # vs 6 clears) with no founder ever responding. Seed 3 free-handed
        # entrepreneurs: they watch chronic unfilled coop-bid pressure and
        # citizen unmet streaks, then FOUND_COOP with the matching recipe.
        for i in range(6):
            name = f"founder_{chr(ord('a') + i)}"
            self._inject({"after_tick": 1, "op": "add_citizen",
                          "name": name, "balance": 500})
            self.bots[name] = {"fn": _wrap_politics(name, ARCHETYPES["entrepreneur"], self.governance), "coop": None, "arch": "entrepreneur"}
        self._record_timeline()

    # ------------------------------------------------------------ internals

    def _apply_batch(self, tick: int, batch: list[Transaction]) -> None:
        pre = len(self.state.applied)
        apply_tick(self.state, self.ledger, batch, current_tick=tick)
        self.batches[tick] = [t.to_dict() for t in batch]
        events = self.state.applied[pre:]
        self._last_events = events
        self.metrics.record_tick(self.state, events)
        for e in events:
            self.feed.append(dict(e))
        if len(self.feed) > 400:
            self.feed = self.feed[-400:]

    def _inject(self, inj: dict[str, Any]) -> None:
        """Recorded direct state edit (dev tool — replayed on load)."""
        self.injections.append(inj)
        self._apply_injection(inj)

    def _apply_injection(self, inj: dict[str, Any]) -> None:
        op = inj["op"]
        # D15: under a fixed money supply, founding capital is a TRANSFER
        # from the Society Pool (the nation's credit fund), never new
        # money. Otherwise the cap leaks by every injection (observed:
        # +29,400 over the 21M cap in 20 ticks).
        fixed = bool((self.state.active_ruleset_params().get("money_cap") or {}).get("enabled"))
        if op == "treasury":
            if fixed:
                take = min(int(self.state.surplus_pool), int(inj["amount"]))
                self.state.surplus_pool -= take
                self.state.coops[inj["coop"]]["treasury"] = (
                    self.state.coops[inj["coop"]].get("treasury", 0) + take)
                return
            coop = self.state.coops[inj["coop"]]
            coop["treasury"] = coop.get("treasury", 0) + inj["amount"]
        elif op == "add_citizen":
            if fixed:
                # D15: a new citizen's stake is a transfer from the Society
                # Pool (same as engine birth stakes), never new money.
                stake = int(inj["balance"])
                take = min(int(self.state.surplus_pool), stake)
                self.state.surplus_pool -= take
                self.state.balances[inj["name"]] = take
            else:
                self.state.balances[inj["name"]] = inj["balance"]
            self.state.labor_hours[inj["name"]] = self.state.labor_hours.get(inj["name"], 0)
            self.state.citizen_inventory.setdefault(inj["name"], {})
        elif op == "capital":
            inv = self.state.coops[inj["coop"]]["inventory"]
            for good, qty in inj["goods"].items():
                inv[good] = inv.get(good, 0) + qty
        elif op == "pantry":
            inv = self.state.citizen_inventory.setdefault(inj["citizen"], {})
            for good, qty in inj["goods"].items():
                inv[good] = inv.get(good, 0) + qty
        elif op == "join_coop":
            members = self.state.coops[inj["coop"]]["members"]
            if inj["name"] not in members:
                members.append(inj["name"])

    def _record_timeline(self) -> None:
        s = self.state
        treasuries = sum(c.get("treasury", 0) for c in s.coops.values())
        money = sum(s.balances.values()) + s.surplus_pool + treasuries + s.capital_fund + getattr(s, "innovation_pool", 0)
        self.timeline["tick"].append(s.tick)
        wealth = (list(s.balances.values()) + [s.surplus_pool]
                  + [c.get("treasury", 0) for c in s.coops.values()])
        self.timeline["gini"].append(gini(wealth))
        self.timeline["money"].append(money)
        self.timeline["surplus"].append(s.surplus_pool)

        # --- flow aggregates (God View) ---
        produced_by_cat: dict[str, int] = {}
        bought_by_cat: dict[str, int] = {}
        for e in self._last_events:
            act = e.get("action")
            if act == "PRODUCE":
                for good, qty in e.get("outputs", {}).items():
                    cat = s.goods.get(good, {}).get("category", "other")
                    produced_by_cat[cat] = produced_by_cat.get(cat, 0) + qty
                    self.totals["produced"][good] = self.totals["produced"].get(good, 0) + qty
            elif act == "MARKET_CLEAR_ESSENTIAL":
                good = e.get("good")
                qty = e.get("sold", 0)
                if qty:
                    cat = s.goods.get(good, {}).get("category", "other")
                    bought_by_cat[cat] = bought_by_cat.get(cat, 0) + qty
                    self.totals["bought"][good] = self.totals["bought"].get(good, 0) + qty
            elif act == "MARKET_CLEAR_AUCTION":
                good = e.get("good")
                qty = 0
                for w in e.get("winners", []):
                    if w.get("coop_id") is None:  # citizens only (flat winner dict)
                        qty += w.get("qty", 0)
                if qty:
                    cat = s.goods.get(good, {}).get("category", "other")
                    bought_by_cat[cat] = bought_by_cat.get(cat, 0) + qty
                    self.totals["bought"][good] = self.totals["bought"].get(good, 0) + qty
        # --- circular-flow aggregates ---
        consumed_units = 0
        unmet_count = 0
        dividend_paid = 0
        for e in self._last_events:
            act = e.get("action")
            if act == "CONSUMED":
                consumed_units += sum(e.get("consumed", {}).values())
                unmet_count += len(e.get("unmet", {}))
            elif act == "SURPLUS_SPEND" and e.get("kind") == "dividend":
                dividend_paid += e.get("total", 0)
        self.timeline["consumed"].append(consumed_units)
        self.timeline["unmet"].append(unmet_count)
        self.timeline["dividends"].append(dividend_paid)

        self.timeline["produced"].append(sum(produced_by_cat.values()))
        self.timeline["bought"].append(sum(bought_by_cat.values()))
        for key in ("produced_cat", "bought_cat"):
            hist = self.timeline[key]
            for cat in set(list(produced_by_cat) + list(bought_by_cat)):
                hist.setdefault(cat, []).append(0)
            src = produced_by_cat if key == "produced_cat" else bought_by_cat
            for cat, series in hist.items():
                series.append(src.get(cat, 0))
        for key in self.timeline:
            if isinstance(self.timeline[key], list):
                if len(self.timeline[key]) > 600:
                    self.timeline[key] = self.timeline[key][-600:]
            else:  # category series dict
                for cat in self.timeline[key]:
                    if len(self.timeline[key][cat]) > 600:
                        self.timeline[key][cat] = self.timeline[key][cat][-600:]

    # ------------------------------------------------------------ actions

    def tick(self) -> list[dict[str, Any]]:
        """Advance one tick: bots decide + pending human actions merge."""
        with self.lock:
            t = self.state.tick + 1
            params = self.state.active_ruleset_params()
            batch: list[Transaction] = []
            for name in sorted(self.bots.keys()):
                bot = self.bots[name]
                rng = random.Random(f"{self.seed}:{t}:{name}")
                batch.extend(bot["fn"](name, self.state, params, t, rng))
            batch.extend(self.pending)
            self.pending = []
            self._apply_batch(t, batch)
            self._record_timeline()
            pre_feed = len(self.feed)
            return self.feed[pre_feed - min(40, len(self.feed)):] if self.feed else []

    def queue_action(self, sender: str, action: str, payload: dict[str, Any]) -> Transaction:
        """Queue a human action for the next tick (version auto-pinned)."""
        with self.lock:
            tx = Transaction(
                tick=self.state.tick + 1,
                sender=sender,
                action=action,
                payload=payload,
                ruleset_version=self.state.ruleset_version,
            )
            self.pending.append(tx)
            return tx

    def add_bot(self, name: str, archetype: str, coop: str | None) -> None:
        with self.lock:
            if archetype in SPECIALISTS:
                fn = SPECIALISTS[archetype]
            else:
                fn = ARCHETYPES[archetype]
            self._inject({"after_tick": self.state.tick, "op": "add_citizen",
                          "name": name, "balance": 500})
            if coop and coop in self.state.coops:
                self._inject({"after_tick": self.state.tick, "op": "join_coop",
                              "coop": coop, "name": name})
            self.bots[name] = {"fn": fn, "coop": coop, "arch": archetype}

    def remove_bot(self, name: str) -> None:
        with self.lock:
            self.bots.pop(name, None)

    # ------------------------------------------------------------ save/load

    def to_save(self) -> dict[str, Any]:
        return {
            "format": SAVE_FORMAT,
            "seed": self.seed,
            "governance": self.governance,
            "injections": list(self.injections),
            "batches": {str(t): batch for t, batch in sorted(self.batches.items())},
            "bots": {name: {"coop": b["coop"], "kind": "specialist" if b["fn"] in SPECIALISTS.values() else "archetype",
                           "arch": b.get("arch")}
                     for name, b in self.bots.items()},
        }

    @classmethod
    def from_save(cls, data: dict[str, Any]) -> "Run":
        if data.get("format") != SAVE_FORMAT:
            raise ValueError("unknown save format")
        run = cls(seed=data.get("seed", 42), governance=data.get("governance", False))
        with run.lock:
            # reset bookkeeping, replay everything
            run.batches = {}
            run.injections = []
            run.feed = []
            run.timeline = {"tick": [], "gini": [], "money": [], "surplus": [],
                             "produced": [], "bought": [],
                             "produced_cat": {}, "bought_cat": {},
                             "consumed": [], "dividends": [], "unmet": []}
            run.totals = {"produced": {}, "bought": {}}
            run.metrics = SimMetrics()
            run.state = genesis_state({n: 500 for n, _, _ in BASELINE_BOTS},
                                      ruleset_params=run._params())
            run.ledger = Ledger()

            injections_by_tick: dict[int, list[dict[str, Any]]] = {}
            for inj in data.get("injections", []):
                injections_by_tick.setdefault(inj["after_tick"], []).append(inj)

            deferred_injections: list[dict[str, Any]] = []
            for tstr, batch in sorted(data.get("batches", {}).items(), key=lambda kv: int(kv[0])):
                t = int(tstr)
                txs = [Transaction(tick=d["tick"], sender=d["sender"], action=d["action"],
                                   payload=d["payload"], ruleset_version=d["ruleset_version"])
                         for d in batch]
                run._apply_batch(t, txs)
                for inj in injections_by_tick.get(t, []):
                    try:
                        run._apply_injection(inj)
                        run.injections.append(inj)
                    except KeyError:
                        # target (coop/citizen) not yet created by replayed
                        # batches (live order vs replay order can differ):
                        # defer to after the last batch, order preserved
                        deferred_injections.append(inj)
                run._record_timeline()
            for inj in deferred_injections:
                run._apply_injection(inj)
                run.injections.append(inj)

            # restore bots (fn resolved from kind; specialists lose their
            # exact closure — default to the matching baseline specialist)
            run.bots = {}
            for name, meta in data.get("bots", {}).items():
                coop = meta.get("coop")
                arch = meta.get("arch")
                if arch and arch in SPECIALISTS:
                    fn = SPECIALISTS[arch]
                elif arch and arch in ARCHETYPES:
                    fn = ARCHETYPES[arch]
                elif name in {b[0] for b in BASELINE_BOTS}:
                    fn = dict((b[0], b[1]) for b in BASELINE_BOTS)[name]
                else:
                    # legacy saves without arch: default
                    fn = ARCHETYPES.get("honest_worker")
                run.bots[name] = {"fn": _wrap_politics(name, fn, run.governance), "coop": coop, "arch": arch}
        return run

    def _params(self) -> dict[str, Any]:
        params = copy.deepcopy(DEFAULT_RULESET_PARAMS)
        # Stage 4: society classifies need-goods as essential (votable,
        # D8) so citizens can BUY_ESSENTIAL them at cost floors.
        # Stage 4 finding: deterministic FCFS essential clearing starved
        # alphabetically-late citizens forever even with surplus supply.
        # Fair clearing rotates service order by tick (votable).
        params["fair_clearing"] = True
        # D15: fixed money supply — 21,000,000 credits, divisible to 0.01
        # (100 units per credit). The full stock exists at genesis (citizen
        # stakes + the Society Pool); no minting ever follows. Wages pay
        # treasury-first with visible coop wage-debt; birth stakes are a
        # pool transfer. The money invariant is exact: balances + pool +
        # coop treasuries == 21,000,000 credits, forever.
        params["money_cap"] = {"enabled": True, "total": 2_100_000_000,
                               "units_per_credit": 100}
        params["bid_escrow"] = {"enabled": True}
        # WP1.1 clearance must be ON for new worlds: the specialist bots'
        # overstock-dump path (D18 demand-starvation fix) depends on it,
        # and honest price discovery in both directions was the point of
        # the feature. Without it, an oversupplied coop can never shed
        # dead inventory -> produce gate stays false -> wage-debt spiral.
        params["sub_floor_clearance"] = {"enabled": True, "max_discount_bp": 3_000}
        # D19 durable capital: machines/hand_tools are OWNED EQUIPMENT with
        # wear (1 unit serves 20 runs), not ingredients consumed per run.
        # Legacy model priced ~12.6 member-days of capital into every
        # 24-coal run (machine baseline ~10,095u x 1/run): electricity was
        # structurally unaffordable and the whole breadth economy was
        # energy-rationed (power plant: 4.6 elec/tick for 181 citizens).
        params["durable_capital"] = {"enabled": True, "goods": ["machines", "hand_tools"], "durability": 20}
        # Stage 4 fix: producer input priority — coops buy their inputs
        # at cost BEFORE the citizen essential pass (share-capped), so
        # downstream producers (kitchen/meals, household goods, capital
        # maintenance) are not starved by citizen FCFS demand.
        params["producer_input_priority"] = {"enabled": True, "share_cap_bp": 5_000}
        # D16 scenario: start like the real world — the top 1% own 50% of
        # ALL money, the Society Pool starts empty. The game is using
        # policies (wealth tax, dividends, credit union) to rebalance.
        if getattr(self, "scenario", "equal") == "unequal":
            params["inequality_seed"] = {"enabled": True, "top_pct_bp": 100,
                                         "top_share_bp": 5_000}
        params["triage_overrides"] = {
            g: "essential" for g in (
                "vegetables", "fruit", "meat", "milk", "eggs", "cheese",
                "meals", "fish", "clothing", "healthcare", "education",
                "childcare", "housing", "transport", "heating_fuel",
                "medicine", "maintenance", "books", "furniture",
                "household_goods",
            )
        }
        # Circular flow (2026-08-21): citizens need goods daily, surplus
        # returns to society. Both votable rule params like everything else.
        # Stage 4 breadth: full-spectrum citizen needs. Fractional daily
        # quotas are integer-native via needs_cycle (consume quota every
        # N ticks). Triage overrides make need-goods essential so citizens
        # can BUY_ESSENTIAL them at cost floors.
        params["needs"] = {
            "bread": 1, "water": 1, "electricity": 1,
            "vegetables": 5, "fruit": 5, "meat": 4, "milk": 4, "eggs": 4,
            "cheese": 1, "meals": 2, "fish": 3,
            "clothing": 1, "healthcare": 1, "education": 1, "childcare": 1,
            "housing": 1, "transport": 2, "heating_fuel": 2, "medicine": 1,
            "maintenance": 1, "books": 1, "furniture": 1, "household_goods": 1,
        }
        params["needs_cycle"] = {
            "vegetables": 20, "fruit": 20, "meat": 25, "milk": 25, "eggs": 25,
            "cheese": 100, "meals": 50, "fish": 33,
            "clothing": 100, "healthcare": 100, "education": 200,
            "childcare": 100, "housing": 500, "transport": 50,
            "heating_fuel": 50, "medicine": 200, "maintenance": 100,
            "books": 100, "furniture": 500, "household_goods": 100,
        }
        params["surplus_spending"] = {
            "dividend_share_bp": 5_000,       # 50% of spendable pool
            "services_share_bp": 5_000,        # 50% funds essential refunds
            "min_pool_buffer": 500,            # never spend below this
            "max_dividend_per_tick": 200,      # anti-flood cap (TOTAL, legacy)
            "max_dividend_per_citizen_tick": 2,  # per-capita cap, scales with population
        }
        # Public capital, private use: co-ops consuming machines as inputs
        # pay society the replacement cost into the surplus pool, which
        # recycles it to citizens (dividends/services).
        params["capital_rent"] = {"per_machine_used": 1_500, "per_tool_used": 60}
        # True-cost accounting: baselines stamp from realized purchase
        # costs (VWAP), not book values (hard core A1).
        params["cost_accounting"] = {"method": "vwap"}
        params["honest_wages"] = {"enabled": True}
        # D21d: baselines track TRUE current costs even when a producer
        # barely runs — kills the stale-baseline death spiral (fishery).
        params["live_cost_baselines"] = {"enabled": True}
        # D21e supply_buffer_runs TRIED at 3 runs and REJECTED by the gate:
        # essentials 1->3, breadth 5->14 (all seeds identical) -- a 3-run
        # input buffer makes millers strip grain from livestock and bakers
        # outbid others 3x at once: smoothing at one stage starves a
        # neighbor stage. Kept votable (default OFF) as a policy experiment
        # for the Lab; NOT enabled by default. Evidence 2026-09-07.
        # D21g: smooth the OFFER (release rate) — production lumps no
        # longer pass straight into the market as 0/438 swings. Neighbor-
        # safe: total production and input use unchanged.
        params["offer_smoothing"] = {"enabled": True}
        # D21f demand_smoothing TRIED and REJECTED by the gate:
        # essentials 1->2, breadth 5->12 (all seeds identical). Smoothing
        # the demand signal changes WHERE production lands but not the
        # burst cadence of INPUT arrivals; the market-socialist economy's
        # remaining 1-tick bread miss is structural (fair-rotation of a
        # thin supply margin), not a planning-signal artifact. Kept
        # votable (default OFF) as a Lab policy experiment. 2026-09-07.
        # Progressive wealth tax: savings above 5,000 pay 4%/tick into the
        # pool (recycled via dividends) — caps savings concentration.
        # Stage 6 sweep evidence (2026-09-01): 200bp is UNSTABLE (Gini trend
        # +0.153, drifts 1.5k->3k unchecked); 400-600bp is the stable region
        # (trend -0.24). Default moved to the proven-stable 400bp.
        if getattr(self, "scenario", "equal") == "unequal":
            # D16: the unequal world starts UNREDACTED — no wealth tax.
            # The top 1% keep their 50% until the player enacts policy.
            # Enacting redistribution IS the first game.
            params["wealth_tax"] = {"threshold": 5_000, "rate_bp": 0}
        else:
            params["wealth_tax"] = {"threshold": 5_000, "rate_bp": 400}
        # Anti multi-tx mint exploit: cumulative WORK hours per citizen per
        # tick are capped (per-tx cap alone allowed 10 txs = 10x mint).
        params["max_work_hours_cumulative"] = 8
        # NOTE: labor_pool_cap stays OFF in the baseline. Stress runs proved
        # idle-pool wages are the income pump (D4 right-to-work): capping
        # them starved all demand (balances hit 0). Wage farming is instead
        # self-limiting: wealth_tax 2%/tick above 5,000 caps a pure farmer
        # at ~5,400 cr — the honest-worker equilibrium. See
        # tests/test_hardcore.py::test_zombie_wage_farming_is_bounded.
        # params["labor_pool_cap"] = 2_000  # available for adversarial study
        # Stage 3: the toolsmith chain replaces the capital_refresh rule.
        # Co-ops buy tools/machines on the market; the rule stays available
        # for adversarial what-if study but is OFF in the baseline.
        params["extended_catalog"] = True
        params["capital_backstop"] = {"interval_ticks": 10, "input_advance": {"max_per_coop": 500}, "founding_equipment": True}
        # Patronage: co-op surplus above an operating buffer flows back to
        # worker-members. The buffer (1,600) also reserves rent capacity:
        # capital rent is charged from the treasury at use time, so a drained
        # treasury would underpay society (observed: miners captured ~1,100/machine).
        params["coop_distribution"] = {"buffer": 1_600, "share_bp": 5_000}
        # Utilities bridge: coal_mining consumes hand_tools/machines per
        # run and no toolsmith coop exists yet (capital goods = next
        # milestone). Larger votable endowment keeps utilities alive.
        # Utilities-only endowment: capital comes from the market now
        # (targeted seed via CAPITAL_BOOTSTRAP, replacements purchased).
        params["bootstrap_endowment"] = {
            "water": 200, "electricity": 500,
        }
        if self.governance:
            params["governance"] = {"enabled": True, "vote_window_ticks": 3,
                                    "quorum_bp": 5_000, "trial_period_ticks": 10}
            params["oversight"] = dict(params["oversight"])
            params["oversight"]["council_members"] = ["worker_a", "worker_b"]
        # D18: money-denominated rule constants above were tuned in LEGACY
        # credits. Fixed-supply worlds run in base units (upc per credit) —
        # scale them once here, AFTER all assignments, so institutional
        # channels (advances, buffers, tax thresholds, dividend caps,
        # rents) keep their real purchasing power. Without this the
        # channels collapsed to rounding errors: coops starved at birth
        # while the pool hoarded 20.9M cr (gate seed42
        # worst_essential=1999, 2026-09-03).
        upc = int(params.get("money_cap", {}).get("units_per_credit", 100)) if params.get("money_cap", {}).get("enabled") else 1
        if upc != 1:
            params["surplus_spending"]["min_pool_buffer"] *= upc
            params["surplus_spending"]["max_dividend_per_tick"] *= upc
            params["surplus_spending"]["max_dividend_per_citizen_tick"] *= upc
            params["capital_rent"]["per_machine_used"] *= upc
            params["capital_rent"]["per_tool_used"] *= upc
            params["wealth_tax"]["threshold"] *= upc
            params["capital_backstop"]["input_advance"]["max_per_coop"] *= upc
            params["coop_distribution"]["buffer"] *= upc
        return params

    # ------------------------------------------------------------ views

    def view(self) -> dict[str, Any]:
        with self.lock:
            s = self.state
            coops = {}
            for cid, c in s.coops.items():
                coops[cid] = {
                    "name": c["name"],
                    "members": list(c["members"]),
                    "treasury": c.get("treasury", 0),
                    "labor_pool_hours": c.get("labor_pool_hours", 0),
                    "inventory": {g: q for g, q in c["inventory"].items() if q},
                }
            proposals = {}
            for pid, pr in s.proposals.items():
                ballots = pr.get("ballots", {})
                proposals[pid] = {
                    "proposer": pr["proposer"],
                    "status": pr["status"],
                    "opened_tick": pr["opened_tick"],
                    "closes_tick": pr["closes_tick"],
                    "votes_for": sum(1 for v in ballots.values() if v == "for"),
                    "votes_against": sum(1 for v in ballots.values() if v == "against"),
                    "is_rollback": pr.get("is_rollback", False),
                    "is_intervention": pr.get("intervention") is not None,
                    "intervention": pr.get("intervention"),
                    "params": pr.get("params"),
                }
            recent = [
                {"seq": r.seq, "tick": r.tick, "accepted": r.accepted, "reason": r.reason,
                 "action": r.tx.get("action"), "sender": r.tx.get("sender")}
                for r in self.ledger.records[-30:]
            ]
            active = s.active_ruleset_params()
            return {
                "ok": True,
                "tick": s.tick,
                "autoplay": dict(self.autoplay),
                "citizens": sorted(s.balances.keys()),
                "balances": dict(sorted(s.balances.items())),
                "citizen_inventory": {c: {g: q for g, q in inv.items() if q}
                                      for c, inv in sorted(s.citizen_inventory.items())},
                "labor_hours": dict(sorted(s.labor_hours.items())),
                "coops": coops,
                "proposals": proposals,
                "flags": list(s.flags[-40:]),
                "common_pool": {g: q for g, q in s.common_pool.items() if q},
                "last_clearing": dict(s.last_clearing),
                "surplus_pool": s.surplus_pool,
                "money_minted": s.money_minted,
                "money_retired": s.money_retired,
                "ruleset_version": s.ruleset_version,
                "ruleset_count": len(s.rulesets),
                "good_cost_baseline": dict(sorted(s.good_cost_baseline.items())),
                "governance_enabled": bool(active.get("governance", {}).get("enabled", False)),
                "constitution_phase": active.get("constitution_phase", "bootstrap"),
                "council_members": list(active.get("oversight", {}).get("council_members", [])),
                "archetypes": sorted(ARCHETYPES.keys()) + sorted(SPECIALISTS.keys()),
                "recipes": {rid: {"inputs": r["inputs"], "labor_hours": r["labor_hours"],
                                  "energy": r["energy"], "outputs": r["outputs"]}
                            for rid, r in sorted(s.recipes.items())},
                "goods": sorted(s.goods.keys()),
                "active_params": active,
                "timeline": {k: list(v) for k, v in self.timeline.items()},
                "events": self.feed[-120:],
                "ledger_recent": recent,
                "ledger_counts": {"accepted": self.ledger.accepted_count(),
                                  "rejected": self.ledger.rejected_count()},
                "bots": {name: {"coop": b["coop"]} for name, b in sorted(self.bots.items())},
                "pending": [t.to_dict() for t in self.pending],
            }


# ------------------------------------------------------------------ app

app = Flask(__name__, static_folder=str(Path(__file__).parent / "static"), static_url_path="/static")
RUN = Run()
# async policy-experiment jobs: job_id -> {status, result, error}
POLICY_JOBS: dict[str, dict[str, Any]] = {}
POLICY_JOBS_LOCK = threading.Lock()
AUTOPLAY_THREAD: threading.Thread | None = None


def _autoplay_loop() -> None:
    while True:
        with RUN.lock:
            running = RUN.autoplay["running"]
            interval = RUN.autoplay["interval"]
        if running:
            RUN.tick()
            time.sleep(max(0.05, interval))
        else:
            time.sleep(0.15)


@app.get("/")
def index():
    return send_from_directory(str(Path(__file__).parent / "static"), "index.html")


# ---- D9: story + flows (game-style dashboard) ----------------------


@app.get("/api/story")
def api_story():
    """The front page: plain-language story cards with chart series."""
    with RUN.lock:
        return jsonify(build_story(RUN.state, RUN.timeline))


@app.get("/api/flows")
def api_flows():
    """Node/edge/pool flow data for the living map and circular stage."""
    with RUN.lock:
        return jsonify(build_flows(RUN))


@app.get("/api/state")
def api_state():
    return jsonify(RUN.view())


@app.get("/api/analytics")
def api_analytics():
    """God View analytics: money locations, production/purchase pies,
    per-good flows, plain-language alerts. Derived read-only."""
    with RUN.lock:
        s = RUN.state
        # money locations
        citizens_money = sum(s.balances.values())
        treasuries = {cid: c.get("treasury", 0) for cid, c in sorted(s.coops.items())}
        treasury_money = sum(treasuries.values())
        money_pie = {
            "citizens": citizens_money,
            "coop_treasuries": treasury_money,
            "surplus_pool": s.surplus_pool,
                    "capital_fund": s.capital_fund,
        }
        # category pies from run totals
        def _by_cat(kind: str) -> dict[str, int]:
            out: dict[str, int] = {}
            for good, qty in RUN.totals.get(kind, {}).items():
                if qty <= 0:
                    continue
                cat = s.goods.get(good, {}).get("category", "other")
                out[cat] = out.get(cat, 0) + qty
            return dict(sorted(out.items()))

        # per-good flow table
        goods_table = []
        for good in sorted(s.goods.keys()):
            meta = s.goods[good]
            coop_stock = sum(c["inventory"].get(good, 0) for c in s.coops.values())
            citizen_stock = sum(inv.get(good, 0) for inv in s.citizen_inventory.values())
            listed = sum(e["qty"] for e in s.listings.get(good, []) if e["qty"] > 0)
            goods_table.append({
                "good": good,
                "category": meta.get("category", "other"),
                "triage": meta.get("triage", "market"),
                "produced_total": RUN.totals["produced"].get(good, 0),
                "bought_total": RUN.totals["bought"].get(good, 0),
                "listed_now": listed,
                "coop_stock": coop_stock,
                "citizen_stock": citizen_stock,
                "common_pool": s.common_pool.get(good, 0),
                "last_price": s.last_clearing.get(good),
                "cost_baseline": s.good_cost_baseline.get(good),
            })

        # plain-language alerts
        alerts: list[dict[str, str]] = []
        for cid, amount in treasuries.items():
            if amount < 50:
                alerts.append({"level": "warn",
                               "msg": f"{cid} nearly bankrupt (₡{amount} treasury)"})
        for cid, c in s.coops.items():
            for good, qty in c["inventory"].items():
                if good not in s.goods or s.goods[good].get("category") in ("utility",):
                    continue
                if qty > 200 and good not in ("electricity", "water"):
                    alerts.append({"level": "warn",
                                   "msg": f"{cid} overproduction pile: {qty} {good} unsold"})
        for name, bal in s.balances.items():
            if bal < 10:
                alerts.append({"level": "alert", "msg": f"{name} is out of money (₡{bal})"})
        recent_flags = s.flags[-8:]
        for f in recent_flags:
            kind = f.get("kind", "?")
            target = f.get("target", "?")
            good = f.get("good", "")
            alerts.append({"level": "flag",
                           "msg": f"Oversight {kind}: {target} {('(' + good + ')') if good else ''} t{f.get('tick', '?')}"})
        # circular-flow welfare: persistent unmet needs are a policy signal
        for citizen, streaks in sorted(s.unmet_needs.items()):
            for good, streak in sorted(streaks.items()):
                if streak >= 5:
                    alerts.append({"level": "alert",
                                   "msg": f"{citizen} unmet need {good} for {streak} ticks — supply or income failing"})
        # supply halt: persistent unmet demand + near-zero world stock (A3)
        halt_demand: dict[str, int] = {}
        for citizen, streaks in s.unmet_needs.items():
            for good, streak in streaks.items():
                if streak >= 10:
                    halt_demand[good] = halt_demand.get(good, 0) + 1
        for good, sufferers in sorted(halt_demand.items()):
            total_stock = sum(c["inventory"].get(good, 0) for c in s.coops.values())
            total_stock += sum(ls["qty"] for ls in s.listings.get(good, []))
            total_stock += sum(inv.get(good, 0) for inv in s.citizen_inventory.values())
            if total_stock <= 5:
                alerts.append({"level": "alert",
                               "msg": f"SUPPLY HALT: {good} — {sufferers} citizens unserved 10+ ticks, world stock {total_stock}"})
        # insolvency warning: treasury below a production run's input cost (A3).
        # A coop's recipe is derived from its last PRODUCE event (state-only).
        last_recipe: dict[str, str] = {}
        for e in reversed(s.applied):
            if e and e.get("action") == "PRODUCE" and e.get("coop_id") not in last_recipe:
                last_recipe[e["coop_id"]] = e["recipe_id"]
        for cid, c in sorted(s.coops.items()):
            recipe = s.recipes.get(last_recipe.get(cid, ""))
            if not recipe:
                continue
            est = recipe.get("energy", 0) * (s.good_cost_baseline.get("electricity", 2) + 1)
            est += sum(q * (s.good_cost_baseline.get(g, 1) + 1) for g, q in recipe.get("inputs", {}).items() if g != "electricity")
            if c.get("treasury", 0) < est:
                alerts.append({"level": "warn",
                               "msg": f"{cid} cannot afford next production run (₡{c.get('treasury', 0)} < ~₡{est} inputs)"})

        return jsonify({
            "ok": True,
            "tick": s.tick,
            "money_pie": money_pie,
            "money_total": (citizens_money + treasury_money
                            + s.surplus_pool + s.capital_fund + getattr(s, "innovation_pool", 0)),
            "money_minted": s.money_minted,
            "money_retired": s.money_retired,
            "produced_pie": _by_cat("produced"),
            "bought_pie": _by_cat("bought"),
            "goods_table": goods_table,
            "alerts": alerts,
            "timeline": {
                "tick": list(RUN.timeline["tick"]),
                "produced": list(RUN.timeline["produced"]),
                "bought": list(RUN.timeline["bought"]),
                "produced_cat": {c: list(v) for c, v in RUN.timeline["produced_cat"].items()},
                "bought_cat": {c: list(v) for c, v in RUN.timeline["bought_cat"].items()},
                "consumed": list(RUN.timeline.get("consumed", [])),
                "dividends": list(RUN.timeline.get("dividends", [])),
                "unmet": list(RUN.timeline.get("unmet", [])),
            },
            "circular": {
                "consumed_totals": dict(sorted(s.consumed_totals.items())),
                "dividends_paid": s.dividends_paid,
                "services_paid": s.services_paid,
                "unmet_needs": {c: dict(sorted(v.items())) for c, v in sorted(s.unmet_needs.items())},
            },
        })


@app.post("/api/tick")
def api_tick():
    events = RUN.tick()
    return jsonify({"ok": True, "events": events})


def availability_producers(st, good: str) -> list[dict[str, Any]]:
    out = []
    for cid, c in st.coops.items():
        rid = c.get("recipe_intent") or c.get("trade") or ""
        outs = (st.recipes.get(rid) or {}).get("outputs") or {}
        if good in outs:
            out.append(c)
    return out


@app.get("/api/chronicle")
def api_chronicle():
    """Story feed: day-numbered plain sentences derived from the ledger.
    Covers rule changes, shocks, and essentials-shortage onsets."""
    import json as _json
    st = RUN.state
    day = max(st.tick, 1)
    events: list[dict[str, Any]] = []
    prev_shocks: set[str] = set()
    prev_unmet_goods: set[str] = set()
    streak_start: dict[str, int] = {}
    # walk applied events in order, emitting sentences on transitions
    for ev in st.applied:
        a = ev.get("action")
        t = ev.get("tick") or 0
        if a == "RULE_CHANGE":
            events.append({"day": t, "icon": "⚖️",
                           "text": f"Day {t} — A new rule was adopted (v{ev.get('to_version', st.ruleset_version)})."})
        elif a == "SHOCK_START":
            kind = str(ev.get("kind", "shock")).replace("_", " ")
            events.append({"day": t, "icon": "🌩️",
                           "text": f"Day {t} — A {kind} hit the economy.",
                           "cls": "bad"})
            prev_shocks.add(kind)
        elif a == "SHOCK_END":
            kind = str(ev.get("kind", "shock")).replace("_", " ")
            events.append({"day": t, "icon": "🌤️",
                           "text": f"Day {t} — The {kind} is over.",
                           "cls": "good"})
            prev_shocks.discard(kind)
        elif a == "MARKET_CLEAR_ESSENTIAL":
            good = ev.get("good")
            sold = ev.get("sold", 0) or 0
            if sold == 0 and good not in prev_unmet_goods:
                prev_unmet_goods.add(good)
                streak_start[good] = t
            elif sold > 0 and good in prev_unmet_goods:
                # shortage ENDED: one summary line instead of daily spam
                d0 = streak_start.pop(good, t)
                if t - d0 >= 3:
                    events.append({"day": t, "icon": "🔄",
                                   "text": f"Day {t} — {str(good).replace('_',' ')} is back after {t - d0} days short.",
                                   "cls": "good"})
                prev_unmet_goods.discard(good)
        elif a == "FOUND_COOP":
            events.append({"day": t, "icon": "🌱",
                           "text": f"Day {t} — Citizens founded a new workshop ({ev.get('coop_id', '?').replace('_', ' ')}).",
                           "cls": "good"})
    # chronic shortages that NEVER came back get one honest line, with cause
    for good in sorted(prev_unmet_goods):
        d0 = streak_start.get(good, day)
        if day - d0 >= 3:
            n_p = len(availability_producers(st, good))
            why = ("no workshop can make it — found a co-op for it in 🧪 The Lab?"
                   if n_p == 0 else
                   "its workshop(s) are starved of their own inputs — fix the supply chain above them")
            events.append({"day": d0, "icon": "⛔",
                           "text": f"Day {d0} — {good.replace('_',' ')} ran out and never came back ({day - d0}+ days). {why}",
                           "cls": "bad"})
    events.sort(key=lambda e: e["day"])
    # keep the feed bounded, newest last
    return jsonify({"ok": True, "now": day, "events": events[-250:]})


def availability_rows(st) -> list[dict[str, Any]]:
    """One row per essential good — who can make it, how much is around,
    and WHY it's missing when it is."""
    from openboard.catalog import GOODS

    # who produces what (from live coops' recipe intents)
    producers: dict[str, list[dict[str, Any]]] = {}
    for cid, c in st.coops.items():
        rid = c.get("recipe_intent") or c.get("trade") or ""
        rec = st.recipes.get(rid) or {}
        outs = rec.get("outputs") or {}
        if not outs:
            continue
        for g in outs:
            producers.setdefault(g, []).append({
                "name": c.get("name") or cid,
                "members": len(c.get("members") or []),
                "inventory": float((c.get("inventory") or {}).get(g, 0)),
            })

    # demand signal: unmet needs right now
    unmet: dict[str, int] = {}
    for cit, needs in st.unmet_needs.items():
        for g in needs:
            unmet[g] = unmet.get(g, 0) + 1

    rows = []
    for g, meta in sorted(GOODS.items()):
        if meta.get("triage") != "essential":
            continue
        ps = producers.get(g, [])
        stock = sum(p["inventory"] for p in ps)
        listing = st.listings.get(g) or []
        n_away = unmet.get(g, 0)
        # why missing: no producer / producer starved of inputs / has stock but not sold
        if not ps:
            why = "nobody can make this yet — no workshop has the recipe"
            status = "missing"
        elif n_away == 0:
            why = "" if stock > 0 else "produced and sold out each day — demand outruns supply"
            status = "ok" if (stock > 0 or listing) else "tight"
            if not why:
                why = f"{len(ps)} workshop(s) producing, available today"
            else:
                status = "tight"
        else:
            starved = [p for p in ps if p["inventory"] <= 0]
            if starved and len(starved) == len(ps):
                why = f"producer(s) ran out of THEIR inputs — the supply chain above them is broken"
            elif listing:
                why = f"{len(listing)} lot(s) for sale but {n_away} citizen(s) can't afford them — prices too high for the poor"
            else:
                why = f"{n_away} citizen(s) need it and none is for sale — producers not listing"
            status = "missing" if n_away > 20 else "tight"
        rows.append({
            "good": g,
            "status": status,
            "unmet": n_away,
            "producers": len(ps),
            "producer_names": [p["name"] for p in ps][:3],
            "stock": round(stock, 1),
            "why": why,
        })
    rows.sort(key=lambda r: (-r["unmet"], r["good"]))
    return rows


@app.get("/api/availability")
def api_availability():
    rows = availability_rows(RUN.state)
    return jsonify({"ok": True, "tick": RUN.state.tick, "rows": rows})


def _recipe_making(st, good: str) -> str | None:
    """The first recipe whose outputs include this good."""
    for rid, rec in sorted(st.recipes.items()):
        if good in (rec.get("outputs") or {}):
            return rid
    return None


@app.get("/api/advice")
def api_advice():
    """The built-in advisor: ranks what's wrong, explains the cause in plain
    words, and names the concrete lever the player can pull."""
    import collections
    st = RUN.state
    tick = st.tick
    rows = availability_rows(st)

    # producer side: who is idle and why
    idle = []
    for cid, c in st.coops.items():
        inv = c.get("inventory") or {}
        rid = c.get("recipe_intent") or c.get("trade") or ""
        rec = st.recipes.get(rid) or {}
        inputs = rec.get("inputs") or {}
        missing_inputs = [g for g, need in inputs.items() if (inv.get(g, 0) or 0) < float(need)]
        if missing_inputs:
            idle.append({"coop": c.get("name") or cid,
                         "makes": sorted((rec.get("outputs") or {}).keys()),
                         "needs": missing_inputs})

    advice = []
    for r in rows:
        if r["unmet"] <= 0:
            continue
        good = r["good"]
        n = r["unmet"]
        if r["producers"] == 0:
            recipe_id = _recipe_making(st, good)
            advice.append({
                "problem": f"{n} citizens can't buy {good.replace('_', ' ')} — nobody produces it",
                "cause": "No workshop has this recipe. The good was never part of the production plan.",
                "action": f"Found a workshop for {good.replace('_', ' ')} — one click below",
                "lever": "found_coop",
                "fix": {"type": "found_coop", "recipe_id": recipe_id} if recipe_id else None,
            })
        elif "supply chain" in r["why"] or "inputs" in r["why"]:
            starved = [i for i in idle if good in (i.get("makes") or [])]
            hint = (f"Workshops making {good.replace('_', ' ')} need: " +
                    ", ".join(sorted({g for i in starved for g in i['needs']})) +
                    ". Fix that upstream good first — more producers or more of it listed for sale.") if starved else                 "Fix the upstream good: more producers, or list more of it for sale."
            fix = None
            for i in starved:
                for g in (i.get("needs") or []):
                    rid = _recipe_making(st, g)
                    if rid:
                        fix = {"type": "found_coop", "recipe_id": rid, "for_good": g}
                        break
                if fix:
                    break
            advice.append({
                "problem": f"{n} citizens can't buy {good.replace('_', ' ')} — the chain above it is broken",
                "cause": r["why"],
                "action": hint or "Fix the upstream good: more producers, or list more of it for sale",
                "lever": "supply_chain",
                "fix": fix,
            })
        elif "afford" in r["why"]:
            advice.append({
                "problem": f"{n} citizens can't afford {good.replace('_', ' ')}",
                "cause": "It's for sale but priced beyond their balances.",
                "action": "Raise dividends share or quotas in 🧪 The Lab — put more buying power in citizens' hands",
                "lever": "lab",
            })
        else:
            advice.append({
                "problem": f"{n} citizens can't buy {good.replace('_', ' ')} — none for sale",
                "cause": r["why"],
                "action": "Producers hold stock but aren't listing it — check listing rules or add competition",
                "lever": "market",
            })
    advice.sort(key=lambda a: -len(a["problem"]))
    return jsonify({"ok": True, "tick": tick, "advice": advice[:6], "idle_workshops": idle[:6]})


@app.get("/api/saves")
def api_saves():
    """Decision save points: the world frozen just before each rule change."""
    saves_dir = Path(__file__).resolve().parent / "saves"
    out = []
    if saves_dir.is_dir():
        for f in sorted(saves_dir.glob("decision_*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                d = json.loads(f.read_text())
                out.append({"file": f.name, "tick": d.get("tick"),
                            "label": f.name[len("decision_"):-5].replace("-", " ")})
            except Exception:
                continue
    return jsonify({"ok": True, "saves": out[:25]})


@app.post("/api/restore")
def api_restore():
    """Roll the world back to a decision save point."""
    global RUN
    data = request.get_json(force=True, silent=True) or {}
    name = str(data.get("file", ""))
    if not name.startswith("decision_") or "/" in name or ".." in name:
        return jsonify({"ok": False, "error": "bad save name"}), 400
    f = Path(__file__).resolve().parent / "saves" / name
    if not f.exists():
        return jsonify({"ok": False, "error": "save not found"}), 404
    try:
        new_run = Run.from_save(json.loads(f.read_text()))
    except (ValueError, KeyError) as exc:
        return jsonify({"ok": False, "error": f"restore failed: {exc}"}), 400
    with RUN.lock:
        RUN.autoplay["running"] = False
    RUN = new_run
    return jsonify({"ok": True, "tick": RUN.state.tick})


@app.post("/api/fix/found_coop")
def api_fix_found_coop():
    """One-click fix for 'nobody can make this good': submit a real
    FOUND_COOP through the engine's own validation. Picks two citizens
    (jobless first, then from the largest coops) and declares the recipe."""
    body = request.get_json(force=True, silent=True) or {}
    recipe_id = str(body.get("recipe_id", ""))
    if not recipe_id:
        return jsonify({"ok": False, "error": "recipe_id required"}), 400
    with RUN.lock:
        s = RUN.state
        if recipe_id not in s.recipes:
            return jsonify({"ok": False, "error": f"unknown recipe {recipe_id}"}), 400
        in_coop: set[str] = set()
        for c in s.coops.values():
            in_coop.update(c.get("members") or [])
        free = [c for c in sorted(s.balances.keys()) if c not in in_coop]
        members = free[:2]
        if len(members) < 2:
            big = sorted(s.coops.values(), key=lambda c: -len(c.get("members") or []))
            for c in big:
                for m in (c.get("members") or []):
                    if m not in members:
                        members.append(m)
                    if len(members) >= 2:
                        break
                if len(members) >= 2:
                    break
        if len(members) < 2:
            return jsonify({"ok": False, "error": "not enough citizens to found a coop"}), 400
        coop_id = f"{recipe_id}_coop_{s.tick}"
        RUN.pending.append(Transaction(
            tick=s.tick + 1, sender=members[0], action="FOUND_COOP",
            payload={"coop_id": coop_id, "name": recipe_id.replace("_", " ") + " coop",
                     "members": members, "recipe_id": recipe_id},
            ruleset_version=s.ruleset_version))
    return jsonify({"ok": True, "coop": coop_id, "members": members,
                    "note": "founding queued — the workshop appears after the next day clears"})


@app.get("/api/stability")
def api_stability():
    """WP5 heat-card source: aggregates sweeps/*.json into a stability
    map keyed by (knob, value). Read-only; empty when no sweeps exist."""
    import json
    from collections import defaultdict

    rows = defaultdict(list)
    sweeps_dir = Path(__file__).resolve().parents[1] / "sweeps"
    if sweeps_dir.is_dir():
        for f in sorted(sweeps_dir.glob("*.json")):
            try:
                r = json.loads(f.read_text())
            except (OSError, ValueError):
                continue
            if all(k in r for k in ("knob", "value", "verdict")):
                rows[(r["knob"], r["value"])].append(r)
    combos = []
    for (knob, value), rs in sorted(rows.items()):
        combos.append({
            "knob": knob,
            "value": value,
            "stable": sum(1 for r in rs if r.get("verdict") == "stable"),
            "total": len(rs),
            "mean_unmet_tail": round(sum(r.get("mean_unmet_tail", 0) for r in rs) / len(rs), 1),
            "worst_streak": max(r.get("worst_streak", 0) for r in rs),
            "invariant_ok": all(r.get("inv_bad", 1) == 0 for r in rs),
        })
    return jsonify({"ok": True, "combos": combos})


def sweeps_dir_exists(d: Path) -> bool:
    return d.is_dir()


# ------------------------------------------------- Policy Lab (fork experiments)

@app.get("/api/policy/knobs")
def api_policy_knobs():
    """Plain-language policy knobs + the live world's current setting."""
    from openboard.policy import KNOBS
    with RUN.lock:
        params = RUN.state.active_ruleset_params()
    knobs = []
    for k in KNOBS:
        cur = "?"
        if k.get("kind") == "needs_scale":
            cur = "Standard"
        else:
            cur_key = k.get("current_of")
            val = params.get(k["param"])
            if k["param"] in ("max_work_hours_cumulative", "labor_pool_cap"):
                cur = f"{val}h" if k["param"] == "max_work_hours_cumulative" else (
                    "Capped" if val is not None else "Uncapped")
            elif isinstance(val, dict) and cur_key:
                cur = f"{val.get(cur_key):,} bp"
            elif val is None:
                cur = "None"
            else:
                cur = str(val)
        knobs.append({"id": k["id"], "question": k["question"],
                      "options": [o["label"] for o in k["options"]],
                      "current": cur})
    return jsonify({"ok": True, "knobs": knobs})


@app.post("/api/policy/adopt")
def api_policy_adopt():
    """Adopt a knob option in the LIVE world via ledger RULE_CHANGE
    (D-PL.3: the Lab proposes; the recorded rule path adopts)."""
    from openboard.policy import knob_by_id, option_by_id, _apply_patch_to_params
    from openboard.rules import validate_params
    from openboard.ledger import Transaction
    body = request.get_json(force=True, silent=True) or {}
    knob = knob_by_id(body.get("knob_id", ""))
    if knob is None:
        return jsonify({"ok": False, "error": "unknown knob"}), 400
    opt = option_by_id(knob, body.get("option_id", ""))
    if opt is None:
        return jsonify({"ok": False, "error": "unknown option"}), 400
    with RUN.lock:
        s = RUN.state
        # decision save point: freeze the world exactly as it was BEFORE this
        # law, so the player can always roll the decision back
        try:
            saves_dir = Path(__file__).resolve().parent / "saves"
            saves_dir.mkdir(exist_ok=True)
            snap_tick = RUN.state.tick
            snap_name = (f"decision_t{snap_tick}_{body.get('knob_id', 'x')}"
                         f"_{body.get('option_id', 'x')}.json").replace("/", "-")
            (saves_dir / snap_name).write_text(json.dumps(RUN.to_save()))
        except Exception:
            pass  # a snapshot failure must never block a democratic decision
        params = _apply_patch_to_params(s.active_ruleset_params(), opt["patch"])
        reason = validate_params(params, known_goods=set(s.goods.keys()))
        if reason is not None:
            return jsonify({"ok": False, "error": f"invalid: {reason}"}), 400
        sender = sorted(s.balances.keys())[0]
        tx = Transaction(tick=s.tick + 1, sender=sender, action="RULE_CHANGE",
                         payload={"params": params, "activation_tick": s.tick + 2},
                         ruleset_version=s.ruleset_version)
        RUN.pending.append(tx)
    return jsonify({"ok": True, "adopted": opt["label"], "knob": knob["id"]})


@app.post("/api/autoplay")
def api_autoplay():
    data = request.get_json(force=True, silent=True) or {}
    with RUN.lock:
        if "running" in data:
            RUN.autoplay["running"] = bool(data["running"])
        if "interval" in data:
            try:
                RUN.autoplay["interval"] = max(0.05, float(data["interval"]))
            except (TypeError, ValueError):
                pass
    return jsonify({"ok": True, "autoplay": RUN.autoplay})


@app.post("/api/reset")
def api_reset():
    global RUN
    data = request.get_json(force=True, silent=True) or {}
    governance = bool(data.get("governance", False))
    seed = int(data.get("seed", 42))
    scenario = str(data.get("scenario", "equal"))
    if scenario not in ("equal", "unequal"):
        return jsonify({"ok": False, "error": "unknown scenario"}), 400
    with RUN.lock:
        RUN.autoplay["running"] = False
    RUN = Run(seed=seed, governance=governance, scenario=scenario)
    top_share = 0
    if scenario == "unequal":
        top = sorted(RUN.state.balances.values(), reverse=True)
        top_share = (top[0] * max(1, len(top) // 100)) * 100 if top else 0
    return jsonify({"ok": True, "tick": RUN.state.tick, "scenario": scenario,
                    "money_cap_credits": 21_000_000 if (RUN.state.active_ruleset_params().get("money_cap") or {}).get("enabled") else None})


@app.get("/api/seat")
def api_seat():
    """Citizen Seat: personalized cockpit for one citizen.
    Wallet, needs bar, my co-ops, open votes (flagging ones waiting on me),
    computed one-click affordances, and my recent event feed."""
    with RUN.lock:
        s = RUN.state
        params = s.active_ruleset_params()
        citizens = sorted(s.balances.keys())
        if not citizens:
            return jsonify({"who": None})
        humans = [c for c in citizens if c not in RUN.bots]
        who = request.args.get("citizen") or ""
        if who not in s.balances:
            who = (humans or citizens)[0]

        needs_cfg = params.get("needs") or {}
        cycles = params.get("needs_cycle") or {}
        inv = s.citizen_inventory.get(who, {})
        unmet = s.unmet_needs.get(who, {})
        balance = int(s.balances.get(who, 0))

        # needs bar: quota vs held, cycle, price
        needs_rows = []
        for good in sorted(needs_cfg.keys()):
            quota = int(needs_cfg[good])
            if quota <= 0:
                continue
            cyc = int(cycles.get(good, 1))
            needs_rows.append({
                "good": good,
                "quota": quota,
                "held": int(inv.get(good, 0)),
                "unmet": int(unmet.get(good, 0) or 0),
                "price": s.good_cost_baseline.get(good),
                "due_today": cyc <= 1 or s.tick % cyc == 0,
            })

        my_coops = []
        for cid, c in sorted(s.coops.items()):
            if who in c.get("members", ()):
                my_coops.append({
                    "id": cid,
                    "name": c.get("name", cid),
                    "treasury": int(c.get("treasury", 0)),
                    "recipe_intent": c.get("recipe_intent"),
                    "members": len(c.get("members", [])),
                    "inventory": c.get("inventory", {}),
                })

        open_proposals = []
        for pid, pr in sorted(s.proposals.items()):
            if pr.get("status") != "open":
                continue
            open_proposals.append({
                "proposal_id": pid,
                "proposer": pr.get("proposer"),
                "params": pr.get("params", {}),
                "opened_tick": pr.get("opened_tick"),
                "closes_tick": pr.get("closes_tick"),
                "ballots": len(pr.get("ballots", {})),
                "my_vote": (pr.get("ballots") or {}).get(who),
                "needs_my_vote": who not in (pr.get("ballots") or {}),
            })

        # what can I do right now
        max_hours = int(params.get("max_work_hours_cumulative", 8) or 8)
        hours_done = int(s.labor_hours.get(who, 0))
        hours_left = max(0, max_hours - hours_done)
        actions = []
        if hours_left > 0:
            for cid, c in sorted(s.coops.items()):
                if who in c.get("members", ()):
                    h = min(hours_left, 8)
                    actions.append({
                        "type": "WORK",
                        "label": f"Work {h}h at {c.get('name', cid)}",
                        "payload": {"coop_id": cid, "hours": h},
                        "why": f"labor today {hours_done}/{max_hours}h",
                    })
        for good in sorted((unmet or {}).keys()):
            ls = [l for l in s.listings.get(good, []) if (l.get("qty") or 0) > 0]
            floors = [int(l["floor"]) for l in ls if l.get("floor") is not None]
            price = min(floors) if floors else int(s.good_cost_baseline.get(good, 1))
            want = int(unmet.get(good) or 1)
            afford = max(1, balance // max(1, price))
            qty = max(1, min(want, afford))
            actions.append({
                "type": "BUY_ESSENTIAL" if floors else "BID",
                "label": f"Buy {good} x{qty} (~{price} cr)",
                "payload": {"good": good, "qty": qty},
                "affordable": balance >= price,
                "listed": bool(floors),
            })
        for pr in open_proposals:
            if pr["needs_my_vote"]:
                actions.append({
                    "type": "VOTE",
                    "label": f"Vote on {pr['proposal_id']}",
                    "payload": {"proposal_id": pr["proposal_id"], "choice": "for"},
                    "proposal_id": pr["proposal_id"],
                    "why": f"closes tick {pr['closes_tick']}",
                    "summary": json.dumps(pr.get("params") or {}, sort_keys=True)[:100],
                })
        for cid, c in sorted(s.coops.items()):
            if who not in c.get("members", ()):
                actions.append({
                    "type": "JOIN_COOP",
                    "payload": {"coop_id": cid},
                    "why": f"join {c.get('name', cid)} ({len(c.get('members', []))} members)",
                })
                break

        # A1 financial depth: credit union affordances (only when enabled)
        loan_info = None
        cp = params.get("credit") or {}
        if cp.get("enabled"):
            loan = s.loans.get(who)
            if loan and not loan.get("defaulted"):
                owed = int(loan_owed(loan, s.tick))  # engine formula (incl. interest, L1)
                loan_info = {"principal": int(loan["principal"]), "owed": owed,
                             "due_tick": int(loan["due_tick"]), "defaulted": False}
                if balance > 0:
                    pay = min(balance, owed)
                    actions.append({
                        "type": "REPAY",
                        "label": f"Repay loan ({pay} of {owed} cr owed)",
                        "payload": {"amount": pay},
                        "why": f"due tick {loan['due_tick']}, fee {loan.get('fee_bp', 0)}/10000",
                    })
            elif loan:
                loan_info = {"principal": int(loan["principal"]), "owed": None,
                             "due_tick": int(loan["due_tick"]), "defaulted": True}
            else:
                cap = int(cp.get("max_per_citizen", 0) or 0)
                if cap > 0 and s.surplus_pool > 0:
                    amt = min(cap, s.surplus_pool)
                    actions.append({
                        "type": "LOAN",
                        "label": f"Borrow {amt} cr from the credit union",
                        "payload": {"amount": amt},
                        "why": f"cap {cp.get('max_per_citizen')}, fee {cp.get('fee_bp', 0)}/10000, term {cp.get('term_ticks', 100)} ticks",
                    })

        my_events = [e for e in s.applied
                     if isinstance(e, dict) and (e.get("citizen") == who or e.get("sender") == who)][-40:]

        return jsonify({
            "who": who,
            "citizens": citizens,
            "humans": humans,
            "is_bot": who in RUN.bots,
            "tick": s.tick,
            "balance": balance,
            "hours": {"done": hours_done, "max": max_hours, "left": hours_left},
            "needs_rows": needs_rows,
            "unmet": unmet or {},
            "my_coops": my_coops,
            "open_proposals": open_proposals,
            "actions": actions,
            "loan": loan_info,
            "my_events": my_events,
            "crisis": bool(getattr(s, "crisis_active", False)),
        })


@app.post("/api/action")
def api_action():
    data = request.get_json(force=True, silent=True) or {}
    sender = data.get("sender")
    action = data.get("action")
    payload = data.get("payload")
    if not isinstance(sender, str) or not isinstance(action, str) or not isinstance(payload, dict):
        return jsonify({"ok": False, "error": "sender, action, payload(dict) required"}), 400
    tx = RUN.queue_action(sender, action, payload)
    return jsonify({"ok": True, "queued": tx.to_dict()})


# ---- B2: Break the System (playable attack mode) -------------------


def _attack_game() -> "Run | None":
    return getattr(app, "attack_game", None)


# ---- B1: accounts (multiplayer foundation) -------------------------

app.accounts = Accounts()


def _citizen_from_token() -> str | None:
    """Resolve the session token (X-Auth-Token header) to a citizen."""
    token = request.headers.get("X-Auth-Token", "")
    return app.accounts.citizen_for_token(token) if token else None


@app.post("/api/account/register")
def api_account_register():
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    password = data.get("password")
    citizen = data.get("citizen")
    if not (isinstance(name, str) and isinstance(password, str) and isinstance(citizen, str)):
        return jsonify({"ok": False, "error": "name, password, citizen required"}), 400
    with RUN.lock:
        if citizen not in RUN.state.balances:
            return jsonify({"ok": False, "error": "unknown citizen"}), 400
        if citizen in RUN.bots:
            return jsonify({"ok": False, "error": "citizen is a bot"}), 400
    token = app.accounts.register(name, password, citizen)
    if token is None:
        return jsonify({"ok": False, "error": "account exists, citizen taken, or weak password"}), 400
    return jsonify({"ok": True, "token": token, "citizen": citizen})


@app.post("/api/account/login")
def api_account_login():
    data = request.get_json(force=True, silent=True) or {}
    token = app.accounts.login(data.get("name"), data.get("password"))
    if token is None:
        return jsonify({"ok": False, "error": "bad credentials"}), 401
    return jsonify({"ok": True, "token": token, "citizen": app.accounts.citizen_for_token(token)})


@app.get("/api/account/me")
def api_account_me():
    who = _citizen_from_token()
    if who is None:
        return jsonify({"ok": False, "error": "not logged in"}), 401
    return jsonify({"ok": True, "citizen": who})


@app.post("/api/attack/start")
def api_attack_start():
    """Fresh governance-live world; you are the attacker. Timed round:
    200 ticks to do as much damage as you can before the system stops you."""
    data = request.get_json(force=True, silent=True) or {}
    playbook = data.get("playbook", "hoarder")
    if playbook not in PLAYBOOKS:
        return jsonify({"ok": False, "error": f"unknown playbook; choose from {sorted(PLAYBOOKS)}"}), 400
    player = str(data.get("player") or "anon")[:24]
    game = Run(seed=99, governance=True)
    app.attack_game = game
    app.attack_round = {"playbook": playbook, "player": player,
                        "start_tick": game.state.tick}
    return jsonify({"ok": True, "playbook": playbook,
                    "player": player,
                    "round_ticks": ROUND_TICKS,
                    "attacker": sorted(game.state.balances.keys())[0],
                    "score": attack_score(game.state)})


@app.post("/api/attack/act")
def api_attack_act():
    """Advance one tick of the attack game: your playbook acts, the world
    (bots + democracy) responds, invariants are asserted. Timed round:
    returns the final verdict + leaderboard entry when the round ends."""
    import random

    game = _attack_game()
    if game is None:
        return jsonify({"ok": False, "error": "no attack game; POST /api/attack/start first"}), 400
    data = request.get_json(force=True, silent=True) or {}
    playbook = data.get("playbook", "hoarder")
    if playbook not in PLAYBOOKS:
        return jsonify({"ok": False, "error": "unknown playbook"}), 400
    rnd = getattr(app, "attack_round", None) or {"playbook": playbook,
                                                 "player": "anon",
                                                 "start_tick": game.state.tick}
    with game.lock:
        s = game.state
        t = s.tick + 1
        atxs = attack_tick(s, sorted(s.balances.keys())[0], t, playbook, random.Random(t))
        for atx in atxs:
            game.queue_action(atx.sender, atx.action, atx.payload)
        game.tick()  # attacker acts AND the world (bots, democracy, oversight) responds in one advance
        verdict = round_verdict(s, rnd["playbook"], rnd["start_tick"])
        over = verdict["outcome"] != "round_in_progress"
        entry = None
        if over:
            entry = _leaderboard_record(rnd["player"], verdict)
    return jsonify({"ok": True, "tick": attack_score(s)["tick"],
                    "score": attack_score(s), "verdict": verdict,
                    "system_response": "flagged" if verdict["flags_caused"] > 0 else "none",
                    "over": bool(over), "leaderboard_entry": entry})


# ---- B2 v2: persistent leaderboard (top damage before the system stops you)

LEADERBOARD_PATH = Path(__file__).resolve().parent / "saves" / "attack_leaderboard.json"


def _leaderboard_load() -> list[dict[str, Any]]:
    try:
        return json.loads(LEADERBOARD_PATH.read_text())
    except Exception:
        return []


def _leaderboard_record(player: str, verdict: dict[str, Any]) -> dict[str, Any]:
    """Record a finished round in the persistent leaderboard (top 20)."""
    import time as _time

    LEADERBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)
    board = _leaderboard_load()
    entry = {
        "player": player,
        "playbook": verdict["playbook"],
        "damage": verdict["damage"],
        "flags_caused": verdict["flags_caused"],
        "worst_unmet_streak": verdict["worst_unmet_streak"],
        "ticks_played": verdict["ticks_played"],
        "outcome": verdict["outcome"],
        "at": int(_time.time()),
    }
    board.append(entry)
    board.sort(key=lambda e: -e["damage"])
    LEADERBOARD_PATH.write_text(json.dumps(board[:20], indent=1))
    return entry


@app.get("/api/attack/leaderboard")
def api_attack_leaderboard():
    return jsonify({"ok": True, "board": _leaderboard_load()[:10]})


@app.get("/api/attack/score")
def api_attack_score():
    game = _attack_game()
    if game is None:
        return jsonify({"ok": False, "error": "no attack game"}), 400
    with game.lock:
        return jsonify({"ok": True, "score": attack_score(game.state)})


@app.post("/api/bots")
def api_bots():
    data = request.get_json(force=True, silent=True) or {}
    op = data.get("op", "add")
    name = data.get("name")
    if not isinstance(name, str) or not name:
        return jsonify({"ok": False, "error": "name required"}), 400
    if op == "add":
        archetype = data.get("archetype", "honest_worker")
        coop = data.get("coop") or None
        try:
            RUN.add_bot(name, archetype, coop)
        except KeyError:
            return jsonify({"ok": False, "error": f"unknown archetype {archetype}"}), 400
        return jsonify({"ok": True, "bots": {n: b["coop"] for n, b in RUN.bots.items()}})
    elif op == "remove":
        RUN.remove_bot(name)
        return jsonify({"ok": True, "bots": {n: b["coop"] for n, b in RUN.bots.items()}})
    return jsonify({"ok": False, "error": "op must be add or remove"}), 400


@app.get("/api/save")
def api_save():
    payload = jsonify(RUN.to_save())
    payload.headers["Content-Disposition"] = "attachment; filename=openboard-run.json"
    return payload


@app.post("/api/load")
def api_load():
    global RUN
    data = request.get_json(force=True, silent=True) or {}
    content = data.get("content")
    if not isinstance(content, dict):
        return jsonify({"ok": False, "error": "content (save object) required"}), 400
    try:
        new_run = Run.from_save(content)
    except (ValueError, KeyError) as exc:
        return jsonify({"ok": False, "error": f"load failed: {exc}"}), 400
    with RUN.lock:
        RUN.autoplay["running"] = False
    RUN = new_run
    return jsonify({"ok": True, "tick": RUN.state.tick})


AUTOSAVE_PATH = Path(__file__).resolve().parent / "autosave.json"


def _autosave_loop() -> None:
    """Persist the live world every 30s so a server restart never erases
    a reign again (the day-818 world died exactly that way)."""
    while True:
        time.sleep(30)
        try:
            with RUN.lock:
                snap = RUN.to_save()
            tmp = AUTOSAVE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(snap))
            tmp.replace(AUTOSAVE_PATH)
        except Exception:
            pass  # autosave must never take the server down


def _try_autoload() -> None:
    if not AUTOSAVE_PATH.exists():
        return
    try:
        snap = json.loads(AUTOSAVE_PATH.read_text())
        new_run = Run.from_save(snap)
        global RUN
        RUN = new_run
        print(f"autosave restored: tick {RUN.state.tick}", flush=True)
    except Exception as exc:
        print(f"autosave load failed: {exc}", flush=True)


def main() -> None:
    global AUTOPLAY_THREAD
    _try_autoload()
    AUTOPLAY_THREAD = threading.Thread(target=_autoplay_loop, daemon=True)
    AUTOPLAY_THREAD.start()
    threading.Thread(target=_autosave_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=8421, debug=False)


if __name__ == "__main__":
    main()
