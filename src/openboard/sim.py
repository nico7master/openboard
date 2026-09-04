"""Simulation harness — bot-driven economies (Phase 7, spec §10).

run_simulation() builds a deterministic world from a cast + coop plan,
then lets bots act each tick. Same seed -> identical state hash.
"""

from __future__ import annotations

import random
from typing import Any

from .bots import DecisionFn, _my_coop, _tx, personal_needs
from .engine import apply_tick
from .ledger import Ledger, Transaction
from .metrics import SimMetrics
from .state import WorldState


def make_specialist(
    recipe_id: str,
    output_good: str,
    buys: dict[str, int],
    stock_target: int = 40,
    fallback_recipe_id: str | None = None,
) -> DecisionFn:
    """A producer bot specialized in one recipe: work, buy missing inputs,
    produce only up to a stock target (demand-driven, no infinite piles),
    list the surplus, and personally buy daily needs (circular flow)."""

    def bot(who: str, state: WorldState, params: dict[str, Any], tick: int, rng: random.Random) -> list[Transaction]:
        v = state.ruleset_version
        coop_id = _my_coop(state, who)
        if coop_id is None:
            return []
        c = state.coops[coop_id]
        # D18 seated mobility, engine-signal edition. The previous attempt
        # cascaded because its 'is my coop producing?' test read a 400-event
        # slice of a ~3,800-event tick (always stale -> everyone read as
        # 'not producing' -> the miners coop emptied). Now the decision
        # reads EXACT state fields with two structural guards:
        #   IDLE GUARD: my coop has not produced for 20+ ticks — healthy
        #     producers never leak members, stuck ones do.
        #   TENURE GUARD: I joined my coop 40+ ticks ago — a fresh joiner
        #     cannot chain-switch, which killed the join/leave flap by
        #     construction (founders flapped join/leave EVERY tick).
        _lpt = c.get("last_produce_tick")
        _tenure = (c.get("member_since") or {}).get(who)
        if _lpt is not None and _tenure is not None and (tick - _lpt) >= 20 and (tick - _tenure) >= 40:
            _my_streaks = state.unmet_needs.get(who, {})
            _worst_g, _worst_t = None, 0
            for _g in sorted(_my_streaks):
                _t = int(_my_streaks[_g] or 0)
                if _t > _worst_t:
                    _worst_g, _worst_t = _g, _t
            if _worst_g is not None and _worst_t >= 10:
                _cap_m = params.get("max_coop_members", 12)
                _cands = []
                for _cid, _cd in state.coops.items():
                    if _cid == coop_id or len(_cd.get("members") or []) >= _cap_m:
                        continue
                    _rid = _cd.get("recipe_intent") or _cd.get("trade") or ""
                    _rec = state.recipes.get(_rid) or {}
                    if _worst_g in (_rec.get("outputs") or {}):
                        _cands.append((len(_cd.get("members") or []), _cid))
                if _cands:
                    _cands.sort()
                    return [
                        _tx(tick, who, "LEAVE_COOP", {"coop_id": coop_id}, v),
                        _tx(tick, who, "JOIN_COOP", {"coop_id": _cands[0][1]}, v),
                    ]
        recipe = state.recipes[recipe_id]
        active_id = recipe_id
        recipe = state.recipes[recipe_id]
        active_id = recipe_id
        # D18 member equity injection: an idle (10+ ticks, engine-signal
        # last_produce_tick) and insolvent (treasury below one run's input
        # cost) coop is rescued by its worker-owners — the real-world
        # cooperative practice of recapitalizing the firm from member
        # savings (observed: fishery dead at treasury 1 since t204 while
        # its 4 members held ~58k each and the Society Pool was at zero in
        # the unequal world — no public rescuer existed, so production
        # died for 1,760 ticks and 181 citizens went unmet on fish).
        # Bounded: at most 10% of the member's balance per injection,
        # sized to the next run's input cost (inputs + energy), so the
                # Cold-start fallback (Stage 4): when the declared recipe needs
        # capital (tools/machines) the coop lacks and cannot buy (nothing
        # listed, or nothing affordable), bridge to a labor-only primitive
        # recipe so extraction can begin from bare hands. The bridge
        # retires automatically once capital is held or buyable.
        _primary_recipe_id = active_id  # capital recipe we may fall back FROM
        if fallback_recipe_id and fallback_recipe_id in state.recipes:
            # Bridge trigger (generalized 2026-09-01): engage the primitive
            # bridge when ANY declared recipe input is short AND unbuyable
            # (no live listing we can afford). Originally capital-goods-only,
            # which deadlocked the circular capital chain: toolworks (the
            # sole hand_tools producer) starved on STEEL — a material, not
            # capital — so it never bridged, tools hit zero economy-wide,
            # and every miner pinned to primitive recipes forever. Only
            # specialists with a catalogued fallback_recipe_id can bridge;
            # the exit ramp below keeps bidding the primary's inputs so the
            # bridge retires itself when the market recovers.
            bridge_goods = sorted(recipe["inputs"].keys())
            short = any(c["inventory"].get(g, 0) < recipe["inputs"][g] for g in bridge_goods)
            buyable = True
            for g in bridge_goods:
                ls = [e for e in (state.listings.get(g) or []) if e.get("qty", 0) > 0]
                if not ls:
                    buyable = False
                    break
                if not any(c.get("treasury", 0) >= max(1, e.get("floor", 1)) for e in ls):
                    buyable = False
                    break
            if short and not buyable:
                recipe = state.recipes[fallback_recipe_id]
                active_id = fallback_recipe_id
        out = []
        # D18 member equity injection: an idle (10+ ticks, engine-signal
        # last_produce_tick) and insolvent (treasury below one run's input
        # cost) coop is rescued by its worker-owners — the real-world
        # cooperative practice of recapitalizing the firm from member
        # savings (observed: fishery dead at treasury 1 from t204 while
        # its 4 members held ~58k each and the Society Pool was at zero in
        # the unequal world — no public rescuer existed, so production
        # died for 1,760 ticks and 181 citizens went unmet on fish).
        # Bounded: at most 10% of the member's balance per injection,
        # sized to the next run's input cost. The member STILL WORKS this
        # tick — the injection adds capital, it never replaces labor.
        _lpt_e = c.get("last_produce_tick")
        if _lpt_e is not None and (tick - _lpt_e) >= 10:
            _rid_e = c.get("recipe_intent") or c.get("trade") or ""
            _rec_e = state.recipes.get(_rid_e) or {}
            _run_cost = sum(
                q * (state.good_cost_baseline.get(g, 1) + 2)
                for g, q in (_rec_e.get("inputs") or {}).items()
            )
            _run_cost += int(_rec_e.get("energy", 0)) * (state.good_cost_baseline.get("electricity", 1) + 2)
            _run_cost = _run_cost * 3 // 2
            if _run_cost > 0 and c.get("treasury", 0) < _run_cost:
                _bal = state.balances.get(who, 0)
                _inj = min(max(_run_cost - c.get("treasury", 0), 0), _bal // 10)
                if _inj > 0:
                    out.append(_tx(tick, who, "TRANSFER", {
                        "to": coop_id, "amount": _inj,
                    }, v))
        # Right to work: citizens log hours freely; society mints the wage
        # (D4). Idle-pool wages act as the income floor that funds essential
        # consumption — recycled by wealth tax + dividends, NOT an exploit.
        # The engine-side labor_pool_cap bounds adversarial farming; honest
        # pools never approach it because production consumes them.
        # Rest days (realism pack): nobody works 8h every tick forever.
        # One full rest day in ten, staggered per citizen by a stable
        # name hash — deterministic, no rng draw (replay-safe). Pooled
        # labor absorbs the missing hours via production sizing. Cadence
        # is 1-in-10, not 1-in-7: the serial capital chain
        # (machine_works -> miners) missed its 50-tick recovery window
        # at 1-in-7 (-14% throughput) and the ratchet gate failed.
        _rests = ((sum(ord(ch) for ch in who) + tick) % 10) == 0
        _cap = params.get("labor_pool_cap")
        if not _rests and (_cap is None or c["labor_pool_hours"] + 8 <= _cap):
            out.append(_tx(tick, who, "WORK", {"coop_id": coop_id, "hours": 8}, v))


        listed = sum(
            e["qty"] for e in state.listings.get(output_good, [])
            if e["coop_id"] == coop_id
        )
        stock = c["inventory"].get(output_good, 0) + listed
        # D18 demand-starvation fix: when unsold stock piles up past 2x
        # the produce target, the produce gate (stock < target) stays
        # false forever -> no production -> no income -> wage-debt spiral
        # (observed: miners 262 coal vs target 120, debt 2.2M, machine
        # DELIVERED via escrow but still zero produce). The designed tool
        # is WP1.1 clearance: dump the WHOLE output stock at up to 30%
        # below floor, converting dead inventory into treasury -> debt
        # service -> production resumes when demand absorbs the pile.
        _clr = (params.get("sub_floor_clearance") or {})
        # Distress liquidation: an indebted coop sitting on unsold stock
        # above its produce target dumps the whole output stock at
        # clearance prices — the economy's bankruptcy-liquidation
        # mechanism. Trigger is debt+overstock, not a fixed 2x multiple:
        # the seed-42 window opened with coal at 234 vs 2x-target 240 —
        # 6 units short of the dump trigger, then 50 ticks of ~1.5/tick
        # dribble sales never crossed either gate (dead zone 120<stock<240
        # -> ratchet promise missed, observed 2026-09-04 04:41). With debt
        # outstanding the dump is bounded: once debt clears, normal
        # stock-target behavior resumes — no pathological loop.
        if (
            _clr.get("enabled")
            and stock > stock_target
            and c.get("wage_debt")
            and c["inventory"].get(output_good, 0) > 0
        ):
            out.append(_tx(tick, who, "LIST_GOOD", {
                "coop_id": coop_id, "good": output_good,
                "qty": c["inventory"][output_good], "clearance": True,
            }, v))
        # D18 distress production: an indebted coop keeps producing even
        # through overstock — a bankrupt workshop doesn't halt the line
        # because the warehouse is full; it produces AND liquidates,
        # because sales income is what services the wage debt. Observed:
        # miners liquidated 234->175 coal over the window but clearance
        # income (~dribble) could never outpace the 9,600u/tick wage bill
        # while the produce gate stayed shut -> debt 2.0M, zero produce
        # runs, ratchet promise missed. Minimal runs only: distress
        # production is income-focused, not stock-building.
        _in_debt = bool(c.get("wage_debt"))
        want_produce = stock < stock_target or _in_debt

        # Stage 5 FIX: energy maintenance runs ALWAYS, not only when
        # producing (observed: steelworks froze with full ore/coal and
        # zero electricity — it stopped bidding power once steel stock
        # reached target, then every PRODUCE died NOT_ENOUGH_INPUTS).
        _maint_recipe = state.recipes.get(_primary_recipe_id) if active_id == fallback_recipe_id else recipe
        if (_maint_recipe or {}).get("energy", 0) > 0:
            e_need = _maint_recipe["energy"]
            e_have = c["inventory"].get("electricity", 0)
            e_short = max(0, e_need - e_have)
            # guard against double-bidding: skip only when the
            # input loop below will handle it this tick (want_produce).
            # buys-membership is NOT the right guard: electricity sits
            # in many coops' buys dict, which silently disabled this
            # whole block once stock targets were met.
            # Skip only if the INPUT LOOP will really buy electricity this
            # tick: it iterates recipe["inputs"] — energy is a separate
            # field and never appears there, so defer-to-input-loop was a
            # deadlock (steelworks starved of power forever).
            _input_loop_covers_power = "electricity" in (_maint_recipe.get("inputs") or {})
            if e_short > 0 and not (want_produce and _input_loop_covers_power):
                floors = [e["floor"] for e in state.listings.get("electricity", ()) if e["qty"] > 0]
                # 2026-09-01: bid at floor+2 like every other buyer —
                # bidding the raw floor loses every tie-break to floor+2
                # bidders (observed: livestock priced power at 1 vs floor 2,
                # 1,192 bids, chronically starved -> meat shortage)
                e_price = (min(floors) + 2 if floors else state.good_cost_baseline.get("electricity", 1))
                # D18: buy ahead with a 3-run buffer — a just-in-time bid
                # for exactly one run's energy loses a single auction and
                # the day's PRODUCE dies NOT_ENOUGH_ENERGY (fishery ran
                # 0.29 runs/tick on a 1-run/day capacity). Within-tick
                # ordering means the protected reserve funds this bid;
                # the buffer is bounded by what the reserve can cover.
                e_buffer = e_need * 3
                e_want = max(e_short, min(e_buffer, e_buffer - e_have + e_need))
                e_qty = min(e_want, c.get("treasury", 0) // e_price) if e_price > 0 else e_want
                if e_qty > 0:
                    out.append(_tx(tick, who, "BID_FOR_COOP", {
                        "coop_id": coop_id, "good": "electricity",
                        "max_price": e_price, "qty": e_qty,
                    }, v))

        # buy missing inputs from the market (treasury must afford it),
        # sized to at most one production run beyond the target
        if want_produce:
            out_units = sum(recipe["outputs"].values())
            # D18 joint-output sizing: the gate used to watch only the
            # PRIMARY output (livestock's declared trade is meat) — when
            # meat stock sat at target, runs collapsed to the minimum and
            # the JOINT outputs (milk/eggs) trickled at ~10/tick against
            # 120/tick citizen demand (gate-world probe: 17,539 applied
            # milk buys vs 981 sold in 100 ticks, streak 37 while both
            # livestock coops were healthy and producing). Production
            # sizing must consider EVERY output's market gap: list the
            # worst gap across outputs (inventory + live listings vs
            # target), so unmet joint-output demand drives runs like
            # primary-good demand does.
            runs_wanted = 1
            for _og in sorted(recipe["outputs"].keys()):
                _listed_og = sum(
                    e["qty"] for e in state.listings.get(_og, [])
                    if e["coop_id"] == coop_id
                )
                _stock_og = c["inventory"].get(_og, 0) + _listed_og
                _gap_og = max(0, stock_target - _stock_og)
                _rw = max(1, (_gap_og + out_units - 1) // out_units)
                runs_wanted = max(runs_wanted, _rw)
            runs_wanted = max(runs_wanted, (stock_target - stock + out_units - 1) // out_units)
            for good, want_per_run in sorted(buys.items()):
                have = c["inventory"].get(good, 0)
                need = max(0, runs_wanted * want_per_run - have)
                floor = state.good_cost_baseline.get(good, 1)
                price = floor + 2
                treasury = c.get("treasury", 0)
                # affordability-capped: buy what we can now, more next tick
                # (all-or-nothing froze coops forever when a full top-up
                # cost slightly more than the treasury held)
                qty = min(need, treasury // price) if price > 0 else need
                if qty > 0:
                    out.append(_tx(tick, who, "BID_FOR_COOP", {
                        "coop_id": coop_id, "good": good, "max_price": price, "qty": qty,
                    }, v))
            # also recipe-native inputs when our own stock is short
            for good, want_per_run in sorted(recipe["inputs"].items()):
                if good in buys:
                    continue
                have = c["inventory"].get(good, 0)
                need = max(0, runs_wanted * want_per_run - have)
                floor = state.good_cost_baseline.get(good, 1)
                price = floor + 2
                treasury = c.get("treasury", 0)
                qty = min(need, treasury // price) if price > 0 else need
                if qty > 0:
                    out.append(_tx(tick, who, "BID_FOR_COOP", {
                        "coop_id": coop_id, "good": good, "max_price": price, "qty": qty,
                    }, v))
            # Stage 5 FIX: electricity is consumed per RUN, so the
            # want_produce purchase must be sized by runs_wanted like
            # every other input. This buyer previously lived indented
            # inside the FALLBACK-only branch: coops without a fallback
            # recipe (bakeries!) never bought bulk power and limped at
            # 1-3 runs/tick while citizens starved for bread.
            if recipe.get("energy", 0) > 0:

                have_e = c["inventory"].get("electricity", 0)

                need_e = max(0, runs_wanted * recipe["energy"] - have_e)

                floor_e = state.good_cost_baseline.get("electricity", 1)

                price_e = floor_e + 2

                qty_e = min(need_e, c.get("treasury", 0) // price_e) if price_e > 0 else need_e

                if qty_e > 0:

                    out.append(_tx(tick, who, "BID_FOR_COOP", {

                        "coop_id": coop_id, "good": "electricity",

                        "max_price": price_e, "qty": qty_e,

                    }, v))


        # EXIT RAMP from the labor-only fallback: while bridging on a
        # primitive recipe (zero capital inputs), the maintenance loop
        # sees nothing to maintain and the input loop bids nothing — a
        # one-way ratchet into bare hands (observed: miners pinned at 0
        # machines for 250+ ticks, treasury ~1,700, machines listed 600+
        # times). While on the bridge, ALWAYS bid for the PRIMARY
        # recipe's capital goods; production resumes automatically once
        # held (the fallback retires itself).
        if active_id == fallback_recipe_id:
            _prim = state.recipes.get(_primary_recipe_id)
            if _prim:
                # Stage 5 FIX: while bridging on a primitive recipe, keep
                # bidding for BOTH the capital goods AND the material
                # inputs of the primary recipe (observed: machine_works sat
                # on glass 16 + electronics 26 + zero steel, treasury 944,
                # forever — nothing ever bid steel because the input loop
                # only runs under want_produce of the ACTIVE recipe).
                _cap_short = False
                for cap_good in ("machines", "hand_tools"):
                    cap_need = _prim["inputs"].get(cap_good, 0)
                    cap_have = c["inventory"].get(cap_good, 0)
                    short = max(0, cap_need - cap_have)
                    if short <= 0:
                        continue
                    _cap_short = True
                    floors = [e["floor"] for e in state.listings.get(cap_good, ()) if e["qty"] > 0]
                    cap_price = (min(floors) if floors else state.good_cost_baseline.get(cap_good, 1)) + 2
                    cap_qty = min(short, c.get("treasury", 0) // cap_price) if cap_price > 0 else short
                    if cap_qty > 0:
                        out.append(_tx(tick, who, "BID_FOR_COOP", {
                            "coop_id": coop_id, "good": cap_good,
                            "max_price": cap_price, "qty": cap_qty,
                        }, v))
                # material inputs of the primary recipe (steel, etc.)
                for mat_good, mat_per_run in sorted(_prim["inputs"].items()):
                    if mat_good in ("machines", "hand_tools"):
                        continue
                    mat_have = c["inventory"].get(mat_good, 0)
                    mat_short = max(0, mat_per_run - mat_have)
                    if mat_short <= 0:
                        continue
                    floors = [e["floor"] for e in state.listings.get(mat_good, ()) if e["qty"] > 0]
                    mat_price = (min(floors) if floors else state.good_cost_baseline.get(mat_good, 1)) + 2
                    mat_qty = min(mat_short, c.get("treasury", 0) // mat_price) if mat_price > 0 else mat_short
                    if mat_qty > 0:
                        out.append(_tx(tick, who, "BID_FOR_COOP", {
                            "coop_id": coop_id, "good": mat_good,
                            "max_price": mat_price, "qty": mat_qty,
                        }, v))



        # capital maintenance: keep recipe-required tools/machines in
        # stock ALWAYS, not only when producing. Machines burn during
        # production runs; if replenishment waits for a produce signal,
        # a burned-out coop can never restart (observed: miners stuck at
        # 0 machines forever because coal stock stayed above target).
        for cap_good in ("hand_tools", "machines"):
            cap_need = recipe["inputs"].get(cap_good, 0)
            if cap_need <= 0:
                continue
            # Stage 5 FIX: replenishment must run ALWAYS — previously it
            # skipped whenever want_produce was true, deferring to an input
            # loop that only buys MATERIAL inputs, never capital. Miners on
            # seed 123 burned machines while steadily producing and were
            # structurally forbidden from rebidding until they stopped
            # producing (observed 4->2->1->0 over 2000 ticks with zero
            # re-bids). Duplicate bids vs the same shortfall are harmless:
            # limited supply clears once, duplicates just lose auctions.
            cap_have = c["inventory"].get(cap_good, 0)
            if cap_have < cap_need:
                cap_floor = state.good_cost_baseline.get(cap_good, 1)
                cap_price = cap_floor + 2
                cap_treasury = c.get("treasury", 0)
                cap_qty = min(cap_need - cap_have, cap_treasury // cap_price) if cap_price > 0 else cap_need - cap_have
                if cap_qty > 0:
                    out.append(_tx(tick, who, "BID_FOR_COOP", {
                        "coop_id": coop_id, "good": cap_good,
                        "max_price": cap_price, "qty": cap_qty,
                    }, v))

        # solvency guard: estimate the NEXT run's input cost at bid prices
        # (book baseline + 1). Producing while unable to restock inputs is
        # the insolvency death spiral observed at t~800 (millers at 0).
        # D18 solvency-guard fix: restock cost covers what the coop will
        # actually need to BUY again — consumables burned by the run and
        # any capital shortfall. Demanding cash for capital goods the coop
        # ALREADY HOLDS double-counted them: with machines baseline ~10k
        # the guard demanded ~2x machine price before every coal run, and
        # an indebted-but-solvent coop (treasury oscillating 0<->11k, all
        # inputs on hand) was judged insolvent forever -> zero produce
        # events, wage-debt spiral, ratchet promise missed (observed t320:
        # treasury 11,295, all inputs held, no PRODUCE emitted).
        _restock = 0
        for g, q in recipe["inputs"].items():
            if g == "electricity":
                continue
            _short = max(0, q - c["inventory"].get(g, 0))
            _restock += _short * (state.good_cost_baseline.get(g, 1) + 1)
        next_run_cost = recipe.get("energy", 0) * (state.good_cost_baseline.get("electricity", 2) + 1) + _restock
        # produce when feasible, demand says so, and we can restock after
        if (
            want_produce
            and c["labor_pool_hours"] >= recipe["labor_hours"]
            and c["inventory"].get("electricity", 0) >= recipe["energy"]
            and all(c["inventory"].get(g, 0) >= q for g, q in recipe["inputs"].items())
            and (c.get("treasury", 0) >= next_run_cost or stock < stock_target // 2)
        ):
            # Multi-run production: one run per member per tick throttled
            # coops to len(members) runs regardless of pooled labor —
            # millers idled 19,422 labor hours with 234 grain in stock at
            # 3 runs/tick while the city starved for bread. Runs scale by
            # the stock gap, this member's labor share, and on-hand inputs
            # (divided across members so everyone acts, not just the
            # first mover). Engine applies runs atomically per tx.
            gap_runs = max(1, -(-(stock_target - stock) // out_units))
            if stock >= stock_target and _in_debt:
                gap_runs = 1  # distress production: service the debt, don't pile stock
            members = max(1, len(c["members"]))
            labor_runs = c["labor_pool_hours"] // recipe["labor_hours"]
            energy_runs = (
                c["inventory"].get("electricity", 0) // recipe["energy"]
                if recipe.get("energy", 0) > 0 else None
            )
            input_runs = (
                min(c["inventory"].get(g, 0) // q for g, q in recipe["inputs"].items())
                if recipe["inputs"] else None
            )
            runs = min(gap_runs, labor_runs)
            if energy_runs is not None:
                runs = min(runs, energy_runs)
            if input_runs is not None:
                runs = min(runs, input_runs)
            # 2026-09-01: REMOVED the per-member division (runs // members).
            # It double-throttled: pooled labor already caps runs via
            # labor_runs, so dividing again meant big coops produced ~1
            # run/tick no matter the demand — livestock (8 members) made
            # 15 meat/tick vs 330/tick citizen demand, maintenance (6
            # members) made 1/tick vs 82 needed. Members coordinate via
            # the engine's pooled-labor accounting; the bot need not
            # pre-ration.
            out.append(_tx(tick, who, "PRODUCE", {
                "coop_id": coop_id, "recipe_id": active_id, "runs": runs,
            }, v))

        # list the surplus of our output (keep a buffer of 10).
        # Capital goods (tools/machines) list at ANY stock: their whole
        # purpose is sale, and a fixed buffer deadlocked the toolsmith
        # chain (machine_works held 8 machines, could never list them,
        # buyers starved -> economy-wide capital freeze).
        # list surplus of EVERY output (multi-output recipes like
        # livestock yield meat+milk+eggs — all must reach the market).
        # Insolvent coops list at ZERO buffer: selling existing stock is
        # their only path out of the can't-buy-inputs deadlock.
        insolvent = c.get("treasury", 0) < next_run_cost
        # Stage 5 FIX: while bridging on a labor-only fallback, the ACTIVE
        # recipe's outputs are the primitive's — the primary output (e.g.
        # iron_ore) was never listed, starving the whole capital chain
        # downstream (steelworks bid ore at rising prices for 50+ ticks
        # against EMPTY ore listings). While bridging we cannot produce the
        # primary output anyway (that is why we are bridging), so anything
        # held is pure surplus the market needs: list it at zero buffer.
        _bridge_outputs: dict[str, int] = {}
        if active_id == fallback_recipe_id and _primary_recipe_id != active_id:
            _prim = state.recipes.get(_primary_recipe_id)
            if _prim:
                _bridge_outputs = dict(_prim["outputs"])
        for ogood in sorted({**recipe["outputs"], **_bridge_outputs}.keys()):
            held = c["inventory"].get(ogood, 0)
            # buffer must stay BELOW stock_target: a flat 10 with target 10
            # (teachers/builders) meant produce-to-target and never list —
            # goods produced but unreachable by citizens (observed:
            # education/housing unmet for everyone while held in stock).
            # Stage 5 FIX: a producer must never list the capital it needs
            # to keep producing. machine_works builds machines WITH machines
            # (recipe input) — after selling its whole stock it bridged to
            # the fallback, listed nothing, and the machine market died
            # (probe64: live through t302, zero events in the forced window).
            # Self-reserve: hold back the active recipe's own input need.
            _self_reserve = recipe["inputs"].get(ogood, 0)
            if ogood in ("hand_tools", "machines"):
                buffer = _self_reserve
            elif insolvent or ogood in _bridge_outputs:
                buffer = 0
            else:
                buffer = min(10, max(0, stock_target - 2))
            if held > buffer:
                out.append(_tx(tick, who, "LIST_GOOD", {
                    "coop_id": coop_id, "good": ogood, "qty": held - buffer,
                }, v))

        out.extend(personal_needs(who, state, params, tick))
        return out

    bot.recipe_id = recipe_id  # introspectable declared trade
    return bot




def run_simulation(
    cast: list[tuple[str, DecisionFn]],
    coop_plan: list[dict[str, Any]],
    ticks: int,
    seed: int,
    ruleset_params: dict[str, Any] | None = None,
    seed_treasuries: dict[str, int] | None = None,
) -> tuple[WorldState, Ledger, SimMetrics]:
    """Deterministic bot economy.

    - tick 1: co-ops founded from coop_plan
    - treasuries seeded directly (documented pre-run injection, consistent
      across reruns so determinism and the money invariant account for them)
    - ticks 2..N: every bot decides against live public state; the engine
      applies the batch; metrics record per-tick events
    """
    citizens = {name: 500 for name, _ in cast}
    state = genesis_state_compat(citizens, ruleset_params)
    ledger = Ledger()
    metrics = SimMetrics()

    founding = [
        Transaction(
            tick=1,
            sender=plan["members"][0],
            action="FOUND_COOP",
            payload={"coop_id": plan["coop_id"], "name": plan["coop_id"], "members": plan["members"]},
            ruleset_version=1,
        )
        for plan in coop_plan
    ]
    apply_tick(state, ledger, founding, current_tick=1)

    for coop_id, amount in (seed_treasuries or {}).items():
        state.coops[coop_id]["treasury"] = amount

    for t in range(2, ticks + 1):
        params = state.active_ruleset_params()
        actions: list[Transaction] = []
        for name, fn in sorted(cast, key=lambda c: c[0]):
            bot_rng = random.Random(f"{seed}:{t}:{name}")  # stable across processes
            actions.extend(fn(name, state, params, t, bot_rng))
        pre = len(state.applied)
        apply_tick(state, ledger, actions, current_tick=t)
        metrics.record_tick(state, state.applied[pre:])

    metrics.record_rejections(ledger)
    for pr in state.proposals.values():
        if pr["status"] == "passed":
            metrics.proposals_passed += 1
        elif pr["status"] == "failed":
            metrics.proposals_failed += 1

    return state, ledger, metrics


def genesis_state_compat(citizens: dict[str, int], ruleset_params: dict[str, Any] | None) -> WorldState:
    from .state import genesis_state

    return genesis_state(citizens, ruleset_params=ruleset_params)


def total_money(state: WorldState) -> int:
    treasuries = sum(c.get("treasury", 0) for c in state.coops.values())
    return sum(state.balances.values()) + state.surplus_pool + treasuries
