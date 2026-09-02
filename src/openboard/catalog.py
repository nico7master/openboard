"""Starter goods catalog and recipes (spec §13.1).

39 goods across 8 categories; triage defaults per D8. Recipes are pure data
(labor + energy + materials -> outputs, integer quantities only) — Phase 3
executes them; this module only defines them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Good:
    good_id: str
    category: str
    triage: str  # market | essential | emergency
    unit: str


def _g(good_id: str, category: str, triage: str, unit: str) -> tuple[str, dict[str, str]]:
    return good_id, {"category": category, "triage": triage, "unit": unit}


GOODS: dict[str, dict[str, str]] = dict(
    [
        # Food (raw) — essential
        _g("grain", "food_raw", "essential", "kg"),
        _g("vegetables", "food_raw", "essential", "kg"),
        _g("fruit", "food_raw", "essential", "kg"),
        _g("fish", "food_raw", "essential", "kg"),
        _g("meat", "food_raw", "essential", "kg"),
        _g("eggs", "food_raw", "essential", "piece"),
        _g("milk", "food_raw", "essential", "liter"),
        # Food (processed) — essential
        _g("flour", "food_processed", "essential", "kg"),
        _g("bread", "food_processed", "essential", "loaf"),
        _g("canned_food", "food_processed", "essential", "can"),
        _g("cheese", "food_processed", "essential", "kg"),
        _g("meals", "food_processed", "essential", "meal"),
        # Materials — market
        _g("timber", "materials", "market", "m3"),
        _g("stone", "materials", "market", "ton"),
        _g("iron_ore", "materials", "market", "ton"),
        _g("coal", "materials", "market", "ton"),
        _g("sand", "materials", "market", "ton"),
        # Processed materials — market
        _g("lumber", "processed_materials", "market", "m3"),
        _g("bricks", "processed_materials", "market", "piece"),
        _g("steel", "processed_materials", "market", "ton"),
        _g("glass", "processed_materials", "market", "panel"),
        _g("fabric", "processed_materials", "market", "m2"),
        # Tools & machines — market (medicine emergency-eligible)
        _g("hand_tools", "tools_machines", "market", "set"),
        _g("machines", "tools_machines", "market", "unit"),
        _g("electronics", "tools_machines", "market", "unit"),
        _g("medicine", "tools_machines", "market", "package"),
        # Consumer — market
        _g("clothing", "consumer", "market", "garment"),
        _g("furniture", "consumer", "market", "item"),
        _g("household_goods", "consumer", "market", "item"),
        _g("books", "consumer", "market", "volume"),
        # Housing & energy — essentials
        _g("housing", "housing_energy", "essential", "room_month"),
        _g("electricity", "housing_energy", "essential", "kwh"),
        _g("heating_fuel", "housing_energy", "essential", "liter"),
        _g("water", "housing_energy", "essential", "m3"),
        _g("transport", "housing_energy", "market", "trip"),
        # Services — essential (healthcare), rest market
        _g("healthcare", "services", "essential", "visit"),
        _g("education", "services", "market", "course_month"),
        _g("childcare", "services", "market", "day"),
        _g("maintenance", "services", "market", "job"),
    ]
)


@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    inputs: dict[str, int]  # good_id -> qty
    labor_hours: int
    energy: int  # kwh
    outputs: dict[str, int]  # good_id -> qty

    def to_dict(self) -> dict:
        return {
            "recipe_id": self.recipe_id,
            "inputs": self.inputs,
            "labor_hours": self.labor_hours,
            "energy": self.energy,
            "outputs": self.outputs,
        }


def _r(recipe_id, inputs, labor_hours, energy, outputs) -> Recipe:
    return Recipe(recipe_id=recipe_id, inputs=inputs, labor_hours=labor_hours, energy=energy, outputs=outputs)


RECIPES: dict[str, Recipe] = {r.recipe_id: r for r in [
    # Food processing
    _r("grain_to_flour", {"grain": 10}, 2, 1, {"flour": 9}),
    _r("flour_to_bread", {"flour": 5}, 3, 2, {"bread": 20}),
    _r("canning", {"vegetables": 8, "fruit": 4}, 4, 2, {"canned_food": 12}),
    _r("cheesemaking", {"milk": 40}, 5, 2, {"cheese": 8}),
    _r("meal_service", {"vegetables": 3, "meat": 2, "bread": 2}, 6, 1, {"meals": 10}),
    # Materials processing
    _r("sawmill", {"timber": 5}, 8, 4, {"lumber": 4}),
    _r("brickmaking", {"sand": 3, "water": 2}, 10, 6, {"bricks": 100}),
    _r("steelmaking", {"iron_ore": 5, "coal": 3}, 24, 20, {"steel": 4}),
    _r("glassmaking", {"sand": 4}, 12, 10, {"glass": 6}),
    _r("fabric_weaving", {"grain": 2, "water": 3}, 15, 4, {"fabric": 6}),
    # Tools & machines
    _r("hand_tools_craft", {"steel": 2, "lumber": 1}, 20, 5, {"hand_tools": 5}),
    _r("machine_building", {"steel": 10, "electronics": 4, "glass": 2}, 60, 30, {"machines": 1}),
    _r("electronics_assembly", {"steel": 1, "glass": 2, "coal": 1}, 30, 15, {"electronics": 3}),
    # Consumer goods
    _r("clothing_sewing", {"fabric": 10}, 12, 3, {"clothing": 8}),
    _r("furniture_craft", {"lumber": 3, "fabric": 2, "steel": 1}, 25, 5, {"furniture": 2}),
    _r("household_goods_craft", {"steel": 1, "glass": 1, "fabric": 1}, 10, 4, {"household_goods": 3}),
    _r("book_printing", {"fabric": 1, "water": 1}, 8, 2, {"books": 10}),
    # Energy & infrastructure
    _r("electricity_coal", {"coal": 4}, 10, 0, {"electricity": 100}),
    # Agriculture (primary — outputs from land + water + labor)
    _r("grain_farming", {"water": 5}, 40, 3, {"grain": 100}),
    _r("vegetable_farming", {"water": 6}, 50, 3, {"vegetables": 80}),
    _r("orchard", {"water": 4}, 35, 2, {"fruit": 60}),
    _r("fishing", {}, 30, 8, {"fish": 50}),
    _r("livestock", {"grain": 20, "water": 10}, 60, 4, {"meat": 18, "milk": 18, "eggs": 18}),
    # 2026-09-02 3rd pass REVERTED: labor 45 raised grain appetite
    # (20/run x more runs) and regressed the gate (meat 4, milk 7).
    # The 60h cadence with cast margin is the honest fix.
    # 2026-09-02 2nd pass: gate run shows demand ~28.3/tick per good vs ~26
    # produced (93%) — a structural deficit breeding 3-7 tick streaks on the
    # rotation. Per-run outputs raised to ~31/tick (110% of demand).
    # 2026-09-02: joint-output demand gap. Dairy demand (~27/tick) is a
    # fraction of the old joint output (50 milk + 40 eggs per run), so
    # one of two livestock coops sat bankrupt on 41,560 unsold milk +
    # 34,026 eggs and produced NO meat, starving the essential meat
    # chain (worst streak 12 in the seed-42 gate). Balanced to the
    # economy-wide dairy demand; meat throughput roughly doubles.
    # Recipes snapshot into state at genesis: existing saves replay
    # byte-identically (replay safety preserved).
    # Extraction
    _r("logging", {"hand_tools": 1}, 30, 5, {"timber": 10}),
    _r("quarrying", {"hand_tools": 1}, 40, 8, {"stone": 12}),
    _r("iron_mining", {"hand_tools": 1, "machines": 1}, 50, 20, {"iron_ore": 20}),
    _r("coal_mining", {"hand_tools": 1, "machines": 1}, 55, 22, {"coal": 24}),
    _r("sand_extraction", {"hand_tools": 1}, 20, 4, {"sand": 15}),
    # Services (labor + energy -> service)
    _r("healthcare_service", {}, 8, 1, {"healthcare": 4}),
    _r("education_service", {}, 8, 1, {"education": 1}),
    _r("childcare_service", {}, 8, 1, {"childcare": 8}),
    _r("maintenance_service", {"hand_tools": 1}, 6, 1, {"maintenance": 1}),
    _r("transport_service", {"electricity": 10}, 5, 0, {"transport": 20}),
    _r("housing_service", {"lumber": 2, "bricks": 50, "steel": 1}, 100, 15, {"housing": 2}),
    _r("water_service", {"electricity": 5}, 15, 0, {"water": 40}),
]}

# Note: medicine and heating_fuel have no starter recipe yet — production
# coverage is a Phase 3 planning concern, catalog integrity is unaffected.

# Integer cost baselines (credits per unit) — seeds for "production at cost"
# accounting. Each production run recomputes and overwrites the baselines of
# the goods it produces (last-production-cost accounting).
# Extended catalog (Stage 3: competition & real capital). These recipes
# activate ONLY when the ruleset param `extended_catalog` is true — old
# worlds replay byte-identically (recipes hash into state).
#
# Economics notes:
# - machine_building_batch: 8 machines/run at ~1/4 the book unit cost of
#   one-off machine_building (scale). Affordable replacement is what makes
#   market-bought capital viable (coal revenue ~360cr/run could never
#   cover a 2160cr machine every run).
# - steelmaking_batch: economies of scale (4.5 labor-h/steel vs 6).
# - wind_farm: renewable electricity, labor-only cost — diversifies the
#   power sector and gives electricity real competition.
EXTENDED_RECIPES: dict[str, Recipe] = {r.recipe_id: r for r in [
    _r("machine_building_batch", {"steel": 20, "electronics": 6, "glass": 4}, 120, 60, {"machines": 8}),
    _r("steelmaking_batch", {"iron_ore": 20, "coal": 12}, 90, 80, {"steel": 20}),
    _r("wind_farm", {}, 25, 0, {"electricity": 100}),
    # Stage 4 breadth: goods with no recipe + the bootstrap tool
    _r("heating_fuel_refining", {"coal": 2, "water": 1}, 8, 4, {"heating_fuel": 10}),
    _r("herbal_medicine", {"fruit": 5, "water": 2}, 10, 1, {"medicine": 3}),
    # Labor-only toolmaking: society can bootstrap its first tools from
    # bare labor when no endowments exist. Low yield on purpose — it is
    # a bridge, not a competitor to the steel-based chain.
    _r("primitive_toolmaking", {}, 25, 0, {"hand_tools": 1}),
    # Cold-start extraction bridges (Stage 4): machine mining deadlocks
    # from zero endowment (machines need steel, steel needs ore, ore
    # needs machines). These labor-only variants break the loop; their
    # unit economics are deliberately ~5x worse than capital production
    # so they retire naturally once real capital circulates.
    _r("primitive_iron_mining", {}, 80, 0, {"iron_ore": 6}),
    _r("primitive_coal_mining", {}, 80, 0, {"coal": 6}),
    _r("primitive_logging", {}, 40, 0, {"timber": 6}),
    _r("primitive_quarrying", {}, 50, 0, {"stone": 6}),
    _r("primitive_sand_extraction", {}, 30, 0, {"sand": 8}),
]}


DEFAULT_BASELINES: dict[str, int] = {
    "grain": 3,
    "vegetables": 4,
    "fruit": 4,
    "fish": 5,
    "meat": 8,
    "eggs": 2,
    "milk": 3,
    "flour": 5,
    "bread": 3,
    "canned_food": 6,
    "cheese": 12,
    "meals": 8,
    "timber": 15,
    "stone": 12,
    "iron_ore": 20,
    "coal": 15,
    "sand": 8,
    "lumber": 25,
    "bricks": 2,
    "steel": 80,
    "glass": 20,
    "fabric": 12,
    "hand_tools": 60,
    "machines": 1500,
    "electronics": 300,
    "medicine": 100,
    "clothing": 25,
    "furniture": 150,
    "household_goods": 50,
    "books": 15,
    "housing": 800,
    "electricity": 2,
    "heating_fuel": 5,
    "water": 2,
    "transport": 4,
    "healthcare": 60,
    "education": 100,
    "childcare": 8,
    "maintenance": 30,
}


def validate_catalog() -> list[str]:
    """Integrity check: returns list of problems (empty = healthy)."""
    problems: list[str] = []
    for recipe in RECIPES.values():
        for good in list(recipe.inputs.keys()) + list(recipe.outputs.keys()):
            if good not in GOODS:
                problems.append(f"recipe {recipe.recipe_id} references unknown good {good!r}")
        if recipe.labor_hours < 0 or recipe.energy < 0:
            problems.append(f"recipe {recipe.recipe_id} has negative labor/energy")
        for qty in list(recipe.inputs.values()) + list(recipe.outputs.values()):
            if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
                problems.append(f"recipe {recipe.recipe_id} has non-positive-integer quantity")
    for good_id, good in GOODS.items():
        if good["triage"] not in ("market", "essential", "emergency"):
            problems.append(f"good {good_id} has invalid triage {good['triage']!r}")
    return problems
