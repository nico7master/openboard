"""OpenBoard engine server — the dashboard backend and seed of the game.

Owns ONE run in memory: world state, ledger, bot roster, pending human
actions, recorded batches, injections, a metrics timeline, and a rolling
event feed. Human actions join the next tick's batch — nothing mutates
state outside the engine's tick discipline.

Spec: docs/superpowers/specs/2026-08-21-dashboard-server-design.md
"""

from __future__ import annotations

import copy
import random
import sys
import threading
import time
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from openboard.bots import ARCHETYPES  # noqa: E402
from openboard.engine import apply_tick  # noqa: E402
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
    "toolmaker": make_specialist("hand_tools_craft", "hand_tools", {"steel": 2, "lumber": 1}, stock_target=60),
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
    ("steel_a", SPECIALISTS["steelworker"], "steelworks"),
    ("steel_b", SPECIALISTS["steelworker"], "steelworks"),
    ("sand_a", SPECIALISTS["sand_worker"], "sand_co"),
    ("sand_b", SPECIALISTS["sand_worker"], "sand_co"),
    ("glass_a", SPECIALISTS["glassmaker"], "glassworks"),
    ("glass_b", SPECIALISTS["glassmaker"], "glassworks"),
    ("elec_a", SPECIALISTS["electronics_worker"], "electronics_co"),
    ("elec_b", SPECIALISTS["electronics_worker"], "electronics_co"),
    ("tool_a", SPECIALISTS["toolmaker"], "toolworks"),
    ("tool_b", SPECIALISTS["toolmaker"], "toolworks"),
    ("mach_a", SPECIALISTS["machinist"], "machine_works"),
    ("mach_b", SPECIALISTS["machinist"], "machine_works"),
    # Competition: second power, grain, bread
    ("wind_a", SPECIALISTS["wind_worker"], "wind_farm"),
    ("wind_b", SPECIALISTS["wind_worker"], "wind_farm"),
    ("wind_c", SPECIALISTS["wind_worker"], "wind_farm"),
    ("wind_d", SPECIALISTS["wind_worker"], "wind_farm"),
    ("farmer_c", SPECIALISTS["farmer"], "farmers_north"),
    ("farmer_d", SPECIALISTS["farmer"], "farmers_north"),
    ("farmer_g", SPECIALISTS["farmer"], "farmers_north"),
    ("farmer_h", SPECIALISTS["farmer"], "farmers_north"),
    ("farmer_i", SPECIALISTS["farmer"], "farmers_north"),
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
    {"coop_id": "farmers", "members": ["farmer_a", "farmer_b", "farmer_e", "farmer_f", "worker_a", "worker_b"]},
    {"coop_id": "millers", "members": ["miller_a", "miller_b", "miller_c"]},
    {"coop_id": "bakers", "members": ["baker_a", "baker_b", "baker_e"]},
    {"coop_id": "miners", "members": ["miner_a", "miner_b", "miner_c", "miner_d", "miner_e", "miner_f", "miner_g", "miner_h", "miner_i", "miner_j", "miner_k", "miner_l"]},
    {"coop_id": "power_plant", "members": ["power_a", "power_b", "power_c"]},
    {"coop_id": "water_works", "members": ["water_a", "water_b", "water_e", "water_f"]},
    {"coop_id": "loggers", "members": ["logger_a", "logger_b"]},
    {"coop_id": "sawmill_co", "members": ["sawyer_a", "sawyer_b"]},
    {"coop_id": "iron_miners", "members": ["iron_a", "iron_b"]},
    {"coop_id": "steelworks", "members": ["steel_a", "steel_b"]},
    {"coop_id": "sand_co", "members": ["sand_a", "sand_b"]},
    {"coop_id": "glassworks", "members": ["glass_a", "glass_b"]},
    {"coop_id": "electronics_co", "members": ["elec_a", "elec_b"]},
    {"coop_id": "toolworks", "members": ["tool_a", "tool_b"]},
    {"coop_id": "machine_works", "members": ["mach_a", "mach_b"]},
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

    def __init__(self, seed: int = 42, governance: bool = False):
        self.lock = threading.RLock()
        self.seed = seed
        self.governance = governance
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
        for coop, amount in BASELINE_TREASURIES.items():
            self._inject({"after_tick": 1, "op": "treasury", "coop": coop, "amount": amount})
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
        if op == "treasury":
            coop = self.state.coops[inj["coop"]]
            coop["treasury"] = coop.get("treasury", 0) + inj["amount"]
        elif op == "add_citizen":
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
            self.bots[name] = {"fn": fn, "coop": coop}

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
            "bots": {name: {"coop": b["coop"], "kind": "specialist" if b["fn"] in SPECIALISTS.values() else "archetype"}
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

            for tstr, batch in sorted(data.get("batches", {}).items(), key=lambda kv: int(kv[0])):
                t = int(tstr)
                txs = [Transaction(tick=d["tick"], sender=d["sender"], action=d["action"],
                                   payload=d["payload"], ruleset_version=d["ruleset_version"])
                         for d in batch]
                run._apply_batch(t, txs)
                for inj in injections_by_tick.get(t, []):
                    run._apply_injection(inj)
                    run.injections.append(inj)
                run._record_timeline()

            # restore bots (fn resolved from kind; specialists lose their
            # exact closure — default to the matching baseline specialist)
            run.bots = {}
            for name, meta in data.get("bots", {}).items():
                coop = meta.get("coop")
                if name in {b[0] for b in BASELINE_BOTS}:
                    fn = dict((b[0], b[1]) for b in BASELINE_BOTS)[name]
                else:
                    fn = ARCHETYPES.get("honest_worker")
                run.bots[name] = {"fn": _wrap_politics(name, fn, run.governance), "coop": coop}
        return run

    def _params(self) -> dict[str, Any]:
        params = copy.deepcopy(DEFAULT_RULESET_PARAMS)
        # Stage 4: society classifies need-goods as essential (votable,
        # D8) so citizens can BUY_ESSENTIAL them at cost floors.
        # Stage 4 finding: deterministic FCFS essential clearing starved
        # alphabetically-late citizens forever even with surplus supply.
        # Fair clearing rotates service order by tick (votable).
        params["fair_clearing"] = True
        # Stage 4 fix: producer input priority — coops buy their inputs
        # at cost BEFORE the citizen essential pass (share-capped), so
        # downstream producers (kitchen/meals, household goods, capital
        # maintenance) are not starved by citizen FCFS demand.
        params["producer_input_priority"] = {"enabled": True, "share_cap_bp": 5_000}
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
        # Progressive wealth tax: savings above 5,000 pay 2%/tick into the
        # pool (recycled via dividends) — caps savings concentration.
        params["wealth_tax"] = {"threshold": 5_000, "rate_bp": 200}
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
    with RUN.lock:
        RUN.autoplay["running"] = False
    RUN = Run(seed=seed, governance=governance)
    return jsonify({"ok": True, "tick": RUN.state.tick})


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


def main() -> None:
    global AUTOPLAY_THREAD
    AUTOPLAY_THREAD = threading.Thread(target=_autoplay_loop, daemon=True)
    AUTOPLAY_THREAD.start()
    app.run(host="0.0.0.0", port=8421, debug=False)


if __name__ == "__main__":
    main()
