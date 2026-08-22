#!/usr/bin/env python3
"""Stage 3 patch: expand server.py cast/coops/params. Idempotent."""
from pathlib import Path

p = Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
s = p.read_text()
changed = []

# 1) specialists
old = '''SPECIALISTS = {
    "farmer": make_specialist("grain_farming", "grain", {"water": 5}, stock_target=100),
    "miller": make_specialist("grain_to_flour", "flour", {"grain": 10}, stock_target=100),
    "baker": make_specialist("flour_to_bread", "bread", {"flour": 5}, stock_target=100),
    "miner": make_specialist("coal_mining", "coal", {}, stock_target=120),
    "power_worker": make_specialist("electricity_coal", "electricity", {"coal": 4}, stock_target=250),
    "water_worker": make_specialist("water_service", "water", {"electricity": 5}, stock_target=250),
}'''
new = '''SPECIALISTS = {
    "farmer": make_specialist("grain_farming", "grain", {"water": 5}, stock_target=100),
    "miller": make_specialist("grain_to_flour", "flour", {"grain": 10}, stock_target=100),
    "baker": make_specialist("flour_to_bread", "bread", {"flour": 5}, stock_target=100),
    "miner": make_specialist("coal_mining", "coal", {}, stock_target=120),
    "power_worker": make_specialist("electricity_coal", "electricity", {"coal": 4}, stock_target=250),
    "water_worker": make_specialist("water_service", "water", {"electricity": 5}, stock_target=250),
    # Stage 3: toolsmith chain (recipes live in the extended catalog)
    "logger": make_specialist("logging", "timber", {}, stock_target=40),
    "sawyer": make_specialist("sawmill", "lumber", {"timber": 5}, stock_target=40),
    "iron_miner": make_specialist("iron_mining", "iron_ore", {}, stock_target=60),
    "steelworker": make_specialist("steelmaking_batch", "steel", {"iron_ore": 20, "coal": 12}, stock_target=60),
    "sand_worker": make_specialist("sand_extraction", "sand", {}, stock_target=60),
    "glassmaker": make_specialist("glassmaking", "glass", {"sand": 4}, stock_target=40),
    "electronics_worker": make_specialist("electronics_assembly", "electronics", {"steel": 1, "glass": 2, "coal": 1}, stock_target=30),
    "toolmaker": make_specialist("hand_tools_craft", "hand_tools", {"steel": 2, "lumber": 1}, stock_target=60),
    "machinist": make_specialist("machine_building_batch", "machines", {"steel": 20, "electronics": 6, "glass": 4}, stock_target=25),
    # Competition: second power producer
    "wind_worker": make_specialist("wind_farm", "electricity", {}, stock_target=250),
}'''
if old in s:
    s = s.replace(old, new, 1); changed.append("specialists")
elif "wind_worker" in s:
    changed.append("specialists (already)")
else:
    raise SystemExit("specialists anchor not found")

# 2) cast
old = '''    ("worker_a", ARCHETYPES["honest_worker"], "farmers"),
    ("worker_b", ARCHETYPES["honest_worker"], "farmers"),
]'''
new = '''    ("worker_a", ARCHETYPES["honest_worker"], "farmers"),
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
    ("farmer_c", SPECIALISTS["farmer"], "farmers_north"),
    ("farmer_d", SPECIALISTS["farmer"], "farmers_north"),
    ("baker_c", SPECIALISTS["baker"], "city_bakers"),
    ("baker_d", SPECIALISTS["baker"], "city_bakers"),
]'''
if old in s:
    s = s.replace(old, new, 1); changed.append("cast")
elif "farmer_c" in s:
    changed.append("cast (already)")
else:
    raise SystemExit("cast anchor not found")

# 3) coops
old = '''    {"coop_id": "water_works", "members": ["water_a", "water_b"]},
]'''
new = '''    {"coop_id": "water_works", "members": ["water_a", "water_b"]},
    {"coop_id": "loggers", "members": ["logger_a", "logger_b"]},
    {"coop_id": "sawmill_co", "members": ["sawyer_a", "sawyer_b"]},
    {"coop_id": "iron_miners", "members": ["iron_a", "iron_b"]},
    {"coop_id": "steelworks", "members": ["steel_a", "steel_b"]},
    {"coop_id": "sand_co", "members": ["sand_a", "sand_b"]},
    {"coop_id": "glassworks", "members": ["glass_a", "glass_b"]},
    {"coop_id": "electronics_co", "members": ["elec_a", "elec_b"]},
    {"coop_id": "toolworks", "members": ["tool_a", "tool_b"]},
    {"coop_id": "machine_works", "members": ["mach_a", "mach_b"]},
    {"coop_id": "wind_farm", "members": ["wind_a", "wind_b"]},
    {"coop_id": "farmers_north", "members": ["farmer_c", "farmer_d"]},
    {"coop_id": "city_bakers", "members": ["baker_c", "baker_d"]},
]'''
if old in s:
    s = s.replace(old, new, 1); changed.append("coops")
elif "machine_works" in s:
    changed.append("coops (already)")
else:
    raise SystemExit("coops anchor not found")

# 4) treasuries + capital bootstrap
old = 'BASELINE_TREASURIES = {"millers": 600, "bakers": 600, "power_plant": 600, "water_works": 600}'
new = '''BASELINE_TREASURIES = {
    "millers": 600, "bakers": 600, "power_plant": 600, "water_works": 600,
    "sawmill_co": 600, "steelworks": 600, "glassworks": 600,
    "electronics_co": 600, "toolworks": 600, "machine_works": 600,
    "city_bakers": 600, "farmers_north": 600,
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
}'''
if old in s:
    s = s.replace(old, new, 1); changed.append("treasuries")
elif "CAPITAL_BOOTSTRAP" in s:
    changed.append("treasuries (already)")
else:
    raise SystemExit("treasuries anchor not found")

# 5) params: extended catalog on, capital_refresh off
old = '''        # Public capital maintenance until the toolsmith chain exists:
        # worn tools/machines replaced, cost retired from the pool (A3).
        params["capital_refresh"] = {"interval_ticks": 25, "hand_tools": 50, "machines": 5}'''
new = '''        # Stage 3: the toolsmith chain replaces the capital_refresh rule.
        # Co-ops buy tools/machines on the market; the rule stays available
        # for adversarial what-if study but is OFF in the baseline.
        params["extended_catalog"] = True'''
if old in s:
    s = s.replace(old, new, 1); changed.append("params-refresh")
elif 'params["extended_catalog"] = True' in s:
    changed.append("params-refresh (already)")
else:
    raise SystemExit("params-refresh anchor not found")

old = '''        params["bootstrap_endowment"] = {
            "water": 200, "electricity": 500,
            "hand_tools": 100, "machines": 25,
        }'''
new = '''        # Utilities-only endowment: capital comes from the market now
        # (targeted seed via CAPITAL_BOOTSTRAP, replacements purchased).
        params["bootstrap_endowment"] = {
            "water": 200, "electricity": 500,
        }'''
if old in s:
    s = s.replace(old, new, 1); changed.append("params-endowment")
elif '"hand_tools": 100' not in s:
    changed.append("params-endowment (already)")
else:
    raise SystemExit("params-endowment anchor not found")

# 6) capital bootstrap application in __init__ (after treasury injections)
old = '''        for coop, amount in BASELINE_TREASURIES.items():
            self._inject({"after_tick": 1, "op": "treasury", "coop": coop, "amount": amount})'''
new = '''        for coop, amount in BASELINE_TREASURIES.items():
            self._inject({"after_tick": 1, "op": "treasury", "coop": coop, "amount": amount})
        # one-time capital seed (recorded injection, replayed on load)
        for coop, goods in CAPITAL_BOOTSTRAP.items():
            self._inject({"after_tick": 1, "op": "capital", "coop": coop, "goods": goods})'''
if old in s:
    s = s.replace(old, new, 1); changed.append("bootstrap-apply")
elif '"op": "capital"' in s:
    changed.append("bootstrap-apply (already)")
else:
    raise SystemExit("bootstrap-apply anchor not found")

# 7) injection op handler
old = '''        elif op == "pantry":'''
new = '''        elif op == "capital":
            inv = self.state.coops[inj["coop"]]["inventory"]
            for good, qty in inj["goods"].items():
                inv[good] = inv.get(good, 0) + qty
        elif op == "pantry":'''
if old in s:
    s = s.replace(old, new, 1); changed.append("injection-op")
elif '"op": "capital"' in s:
    changed.append("injection-op (already)")
else:
    raise SystemExit("injection-op anchor not found")

# 8) politics roles for the full 38-citizen cast
old = '''POLITICAL_ROLES = {
    "worker_a": "egalitarian",
    "worker_b": "egalitarian",
    "baker_a": "egalitarian",
    "farmer_b": "egalitarian",
    "miner_b": "egalitarian",
    "farmer_a": "libertarian",
    "miner_a": "libertarian",
    "power_b": "libertarian",
    "water_b": "libertarian",
    "miller_a": "pragmatist",
    "miller_b": "pragmatist",
    "power_a": "pragmatist",
    "water_a": "pragmatist",
    "baker_b": "pragmatist",
}'''
new = '''POLITICAL_ROLES = {
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
}'''
if old in s:
    s = s.replace(old, new, 1); changed.append("politics-roles")
elif '"iron_a": "libertarian"' in s:
    changed.append("politics-roles (already)")
else:
    raise SystemExit("politics-roles anchor not found")

p.write_text(s)
print("patched:", ", ".join(changed))
