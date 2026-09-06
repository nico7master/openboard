"""Bot archetypes — the D13 cast. Each bot is a deterministic decision
function: (state, params, tick, rng) -> list[Transaction].

Bots see only public state (radical transparency) and never touch engine
internals. Seeded rng keeps every run reproducible.
"""

from __future__ import annotations

import random
from typing import Any, Callable

from .state import WorldState
from .ledger import Transaction

DecisionFn = Callable[[str, WorldState, dict[str, Any], int, random.Random], list[Transaction]]


def _tx(tick: int, sender: str, action: str, payload: dict[str, Any], version: int) -> Transaction:
    return Transaction(tick=tick, sender=sender, action=action, payload=payload, ruleset_version=version)


def _work(tick, who, coop, hours, version):
    return _tx(tick, who, "WORK", {"coop_id": coop, "hours": hours}, version)


def _buy_essential(tick, who, good, qty, version):
    return _tx(tick, who, "BUY_ESSENTIAL", {"good": good, "qty": qty}, version)


def _bid(tick, who, good, max_price, qty, version):
    return _tx(tick, who, "BID", {"good": good, "max_price": max_price, "qty": qty}, version)


def _my_coop(state: WorldState, who: str) -> str | None:
    for cid, c in state.coops.items():
        if who in c["members"]:
            return cid
    return None


def _afford(state: WorldState, who: str, price: int, qty: int) -> bool:
    return state.balances.get(who, 0) >= price * qty


ESSENTIALS = ("bread", "water", "grain")


# ------------------------------------------------------------ archetypes


def honest_worker(who, state, params, tick, rng) -> list[Transaction]:
    """Work, buy essentials, modest market bids on food."""
    v = state.ruleset_version
    coop = _my_coop(state, who)
    out: list[Transaction] = []
    if coop is not None:
        _cap = params.get("labor_pool_cap")
        # D21 honest wages: supply the hours the coop's plan consumes
        # (shared 1-run buffer with make_specialist), not a flat 6 —
        # paid-but-unconsumed hours were the structural debt machine.
        if (params.get("honest_wages") or {}).get("enabled"):
            _c = state.coops[coop]
            _rec = state.recipes.get(_c.get("recipe_intent") or _c.get("trade") or "") or {}
            _lh = max(1, int(_rec.get("labor_hours") or 1))
            # honest workers are members, not planners: cover one run's
            # hours plus keep a small pool buffer alive for the plan
            _need = _lh + 2 - _c.get("labor_pool_hours", 0)
            _hours = min(6, max(0, _need))
        else:
            _hours = 6
        if _hours > 0 and (_cap is None or state.coops[coop]["labor_pool_hours"] + _hours <= _cap):
            out.append(_work(tick, who, coop, _hours, v))
    else:
        # D19 join-only capacity routing: jobless citizens (incl. adults
        # grown via demographics) fill the weakest-capacity producer of a
        # chronically short ESSENTIAL good's chain. JOIN-only by design:
        # nobody leaves a producing coop, so the floodgate failure mode
        # (donor migration stripped producers, essentials collapsed to
        # 1996) is structurally impossible. Throttles (memory 1Qojf06NmC):
        # skip the bootstrap wave (t>=100) and stagger each citizen to one
        # eligible tick in 20 (deterministic). Appends to out and
        # CONTINUES to personal needs below — never an early return.
        _jt = (tick + sum(ord(ch) for ch in who)) % 20
        if tick >= 100 and _jt == 0:
            _tri_j = params.get("triage_overrides") or {}
            _ess_j = {g for g, _v in _tri_j.items() if _v == "essential"} | {"bread", "water", "electricity", "meals"}
            _sg_j, _st_j = None, 0
            for _cit, _d in state.unmet_needs.items():
                for _g, _t in _d.items():
                    _t = int(_t or 0)
                    if _t > _st_j:
                        _sg_j, _st_j = _g, _t
            if _sg_j in _ess_j and _st_j >= 5:
                _chain_j = {_sg_j}
                _chg_j = True
                while _chg_j:
                    _chg_j = False
                    for _rec in state.recipes.values():
                        _o = set(_rec.get("outputs") or {})
                        if _o & _chain_j:
                            _add = set(_rec.get("inputs") or {}) - _chain_j
                            if _add:
                                _chain_j |= _add
                                _chg_j = True
                _cap_j = params.get("max_coop_members", 20)
                _cands_j = []
                for _cid, _cd in state.coops.items():
                    if len(_cd.get("members") or []) >= _cap_j:
                        continue
                    _rid = _cd.get("recipe_intent") or _cd.get("trade") or ""
                    _rec = state.recipes.get(_rid) or {}
                    if not (set(_rec.get("outputs") or {}) & _chain_j):
                        continue
                    _lh = int(_rec.get("labor_hours") or 1)
                    _ou = max(1, sum(int(x) for x in (_rec.get("outputs") or {}).values()) // 10)
                    _cands_j.append((len(_cd.get("members") or []) / max(1.0, float(_lh * _ou)), len(_cd.get("members") or []), _cid))
                if _cands_j:
                    _cands_j.sort()
                    out.append(_tx(tick, who, "JOIN_COOP", {"coop_id": _cands_j[0][2]}, v))
    # modest market bid on food, only when pantry is low (no slow hoarding)
    held_bread = state.citizen_inventory.get(who, {}).get("bread", 0)
    floor = state.good_cost_baseline.get("bread", 3)
    if held_bread < 2 and _afford(state, who, floor + 2, 1) and rng.random() < 0.3:
        out.append(_bid(tick, who, "bread", floor + 2, 1, v))
    out.extend(personal_needs(who, state, params, tick))
    return out


def _max_runs(c: dict, r: dict, cap: int = 4) -> int:
    """How many recipe runs the coop can afford this tick (D14 auto-scale).
    Bounded by material inputs, energy, and pooled labor -- capped so a
    rich coop does not dump its whole pantry into one tick's run."""
    n = cap
    for g, q in (r.get("inputs") or {}).items():
        n = min(n, int(c["inventory"].get(g, 0) // max(1, q)))
    e = r.get("energy", 0) or 0
    if e:
        n = min(n, int(c["inventory"].get("electricity", 0) // e))
    lh = r.get("labor_hours", 0) or 0
    if lh:
        n = min(n, int(c.get("labor_pool_hours", 0) // lh))
    return max(0, n)


def strategic_producer(who, state, params, tick, rng) -> list[Transaction]:
    """Work hard, produce when inputs allow, list the surplus."""
    v = state.ruleset_version
    coop = _my_coop(state, who)
    if coop is None:
        # D14 auto-mobility: a jobless citizen joins the least-membered
        # coop that produces a chronically short good -- founding is not
        # the only answer; existing coops scale by taking hands.
        worst: dict[str, int] = {}
        for _cit, streaks in state.unmet_needs.items():
            for good, t in streaks.items():
                worst[good] = max(worst.get(good, 0), int(t or 0))
        covered = {g for g, ls in state.listings.items()
                   if any((l.get("qty") or 0) > 0 for l in ls)}
        short = [g for g, t in worst.items() if g not in covered and t >= 5]
        if short:
            cands = []
            for cid, c in state.coops.items():
                rid = c.get("recipe_intent") or c.get("trade") or ""
                rec = state.recipes.get(rid) or {}
                if set((rec.get("outputs") or {})) & set(short):
                    cands.append((len(c.get("members") or []), cid))
            if cands:
                cands.sort()
                target = cands[0][1]
                return [_tx(tick, who, "JOIN_COOP", {"coop_id": target}, v)]
        return []
    out = []
    c = state.coops[coop]
    # D18 seated mobility: the jobless-join branch below only helps when a
    # jobless citizen EXISTS. In the unequal world everyone is seated
    # (observed: 2,826 JOIN_COOP attempts to the fishery over 2,000 ticks,
    # all rejected ALREADY_IN_COOP; membership grew 4->6 only via births
    # while 181/181 citizens went unmet on fish). An employed citizen who
    # PERSONALLY lacks a chronically short good (streak >= 10, nothing
    # listed) may switch to a producer of it that is smaller than their
    # current coop -- labor flows toward understaffed producers of the
    # goods people actually need. The smaller-than-mine condition makes
    # the flow converge (the target grows, then stops attracting).
    _my_streaks = state.unmet_needs.get(who, {})
    _worst_g, _worst_t = None, 0
    for g in sorted(_my_streaks):
        t = int(_my_streaks[g] or 0)
        if t > _worst_t:
            _worst_g, _worst_t = g, t
    # D18 society-level chain routing: the personal trigger can never
    # reach INTERMEDIATE chain stages (nobody personally eats flour), and
    # intermittent dribble service resets personal streaks — verified in
    # the gate world: all 300 late-window joins came from 6 citizens
    # whose personal worst was fruit, while milk/meat (society streak
    # 86) mobilized nobody and the grain/flour stages stayed frozen at
    # genesis membership. Two upgrades:
    #   (a) society trigger — if ANY citizen's streak for a good is >= 15,
    #       that good is a legitimate redeployment target for employed
    #       citizens (their own coop producing none of its chain);
    #   (b) in-chain members STAY: if your own coop already produces any
    #       good in the target chain, switching away only deepens the
    #       shortage (this also kills the orchard founder flap — leaving
    #       a stalled producer of the good you lack never helps you get
    #       that good).
    if _worst_t < 15:
        _soc_g, _soc_t = None, 0
        for _cit, _st in state.unmet_needs.items():
            for g, t in _st.items():
                t = int(t or 0)
                if t > _soc_t:
                    _soc_g, _soc_t = g, t
        if _soc_t >= 15:
            _worst_g, _worst_t = _soc_g, _soc_t
    # D19 routing-thrash fix: the society router fires on the LOUDEST
    # society-wide shortage, which changes tick-to-tick as dribble
    # service resets streaks (bread 21 <-> furniture 28 alternating).
    # Without tenure protection, freshly-routed workers get poached out
    # again the next tick — bakeries sat at 4/3 members for 2,000 ticks
    # while ~59 bread/tick fed 181 citizens. Keep the tenure guard.
    # D19 capacity-signal fix: fair ROTATION HIDES capacity shortages
    # from streak triggers — bakers (4 members, ~59 bread/tick) serve 181
    # citizens in rotating order, so every individual streak stays low
    # while 2/3 of demand goes unserved each tick. ESSENTIAL goods have
    # gate bound 0: any society peak >= 5 on an essential means capacity
    # is short and routing is warranted (breadth goods keep the >= 15
    # bar — their wobble is tolerable).
    _soc_tenure = (state.coops[coop].get("member_since") or {}).get(who)
    _soc_ok = _soc_tenure is None or (tick - _soc_tenure) >= 40
    _tri = (params.get("triage_overrides") or {})
    _ess_goods = {g for g, _v in _tri.items() if _v == "essential"} | {"bread", "water", "electricity", "meals"}
    _route_thresh = 5 if (_worst_g in _ess_goods) else 15
    if _worst_g is not None and _worst_t >= _route_thresh and _soc_ok:
        _cap = params.get("max_coop_members", 20)
        _sc2 = state.coops[coop]
        _my_rid2 = _sc2.get("recipe_intent") or _sc2.get("trade") or ""
        _my_outs2 = set((state.recipes.get(_my_rid2) or {}).get("outputs") or {})
        _target_goods = {_worst_g}
        _changed = True
        while _changed:
            _changed = False
            for _rec in state.recipes.values():
                _o = set(_rec.get("outputs") or {})
                if _o & _target_goods:
                    _add = set(_rec.get("inputs") or {}) - _target_goods
                    if _add:
                        _target_goods |= _add
                        _changed = True
        if not (_my_outs2 & _target_goods):
            # rank every chain producer by weakest capacity stage:
            # members / (labor_hours x output-units/10) — the starved
            # transform stage (millers: 3 members, big input volume)
            # sorts first without needing cash-limited bid evidence.
            _chain_cands = []
            for cid, cd in state.coops.items():
                if cid == coop:
                    continue
                if len(cd.get("members") or []) >= _cap:
                    continue
                _rid = cd.get("recipe_intent") or cd.get("trade") or ""
                _rec = state.recipes.get(_rid) or {}
                _outs = set(_rec.get("outputs") or {})
                if not (_outs & _target_goods):
                    continue
                _labor_h = int(_rec.get("labor_hours") or 1)
                _out_units = sum(int(x) for x in (_rec.get("outputs") or {}).values())
                _cap_score = len(cd.get("members") or []) / max(1.0, float(_labor_h * max(1, _out_units // 10)))
                _chain_cands.append((_cap_score, len(cd.get("members") or []), cid))
            if _chain_cands:
                _chain_cands.sort()
                return [
                    _tx(tick, who, "LEAVE_COOP", {"coop_id": coop}, v),
                    _tx(tick, who, "JOIN_COOP", {"coop_id": _chain_cands[0][2]}, v),
                ]
    # produce if the coop has inputs and labor for its first recipe
    if c["labor_pool_hours"] >= 2:
        for rid, r in state.recipes.items():
            if all(c["inventory"].get(g, 0) >= q for g, q in r["inputs"].items()) and c["labor_pool_hours"] >= r["labor_hours"] and c["inventory"].get("electricity", 0) >= r["energy"]:
                # D14 auto-scale: run the recipe as many times as inputs,
                # energy and labor allow (was hardcoded 1 -- coops could
                # never grow output by scaling up)
                runs = max(1, _max_runs(c, r))
                out.append(_tx(tick, who, "PRODUCE", {"coop_id": coop, "recipe_id": rid, "runs": runs}, v))
                break
    # list surplus outputs (keep 5 units of anything)
    for g in sorted(c["inventory"].keys()):
        if g in ESSENTIALS and c["inventory"][g] > 15:
            out.append(_tx(tick, who, "LIST_GOOD", {"coop_id": coop, "good": g, "qty": c["inventory"][g] - 15}, v))
            break
    # D18: buy the recipe's missing INPUTS (incl. capital goods) from the
    # treasury. Under fixed supply the wage-debt cap leaves working
    # capital in the treasury, but no bot ever converted it into input
    # bids: producers waited passively for the capital backstop while
    # affordable machines sat listed (miners: 12,561u treasury, machines
    # 10,058u listed, ZERO bids in 50 ticks -> ratchet + gate failure).
    # One BID per tick for the scarcest missing input, priced at floor+1.
    rid = c.get("recipe_intent") or c.get("trade")
    recipe = state.recipes.get(rid) or {}
    inputs = recipe.get("inputs") or {}
    # which recipes does this coop actually run? prefer proven history
    for r_id, r in sorted(state.recipes.items()):
        ins = r.get("inputs") or {}
        if ins and all(c["inventory"].get(g, 0) >= q for g, q in ins.items()):
            break  # already runnable — no purchase needed
    treasury = c.get("treasury", 0)
    for g in sorted(inputs.keys()):
        q = inputs[g]
        have = c["inventory"].get(g, 0)
        if have >= q:
            continue
        floor = state.good_cost_baseline.get(g, 1)
        price = floor + 1
        qty = min(q - have, max(1, treasury // max(1, price)))
        if qty <= 0 or treasury < price:
            continue
        # Working-capital reserve: keep 20% of the treasury unspent for
        # consumable inputs. CAPITAL goods are the exception — buying the
        # machine is what unlocks production and refills the treasury, so
        # up to 95% may be committed (the 80% cap made an affordable
        # machine mathematically unpurchasable: 12,561*0.8=10,048 <
        # price 10,058 -> qty 0 -> the bid never fired, ratchet + gate
        # starved forever, observed 2026-09-04).
        _capital = g in ("machines", "hand_tools")
        reserve_bp = 9_500 if _capital else 8_000
        if price * qty > treasury * reserve_bp // 10_000:
            qty = (treasury * reserve_bp // 10_000) // price
            if qty <= 0:
                continue
        # BID_FOR_COOP: validated against the COOP treasury (not the
        # citizen balance) and tagged with coop_id so the clearing engine
        # routes it through the producer-input-priority pass — the
        # designed channel for coop input purchases.
        # ORDER MATTERS: the bid is emitted BEFORE the WORK transactions
        # so it validates against the treasury BEFORE wages are drawn.
        # Work-first ordering made every bid INSUFFICIENT_FUNDS: 12
        # miners' wages (9,600u/tick) drained the treasury inside the
        # same batch before the machine bid validated (observed: 40
        # rejections, ratchet + gate starved, 2026-09-04).
        out.append(_tx(tick, who, "BID_FOR_COOP", {
            "coop_id": coop, "good": g, "max_price": price, "qty": qty,
        }, v))
        break  # one input purchase per tick — gradual, deterministic
    # D21b equity injection (ported from sim.py's strategic_producer):
    # an idle (10+ ticks, engine-signal last_produce_tick) and insolvent
    # (treasury below 1.5x one run's input+energy cost) coop is rescued
    # by its worker-owners — the real-world cooperative practice of
    # recapitalizing the firm from member savings. Observed: the fishery
    # dead at treasury 1 since t403 (1,600 ticks, fish streak 47) while
    # its 4 members held 309k-397k each — the D18 rescue never fired
    # because these citizens run honest_worker, and the rescue existed
    # only in the specialist layer (same two-layer class as D19).
    # Bounded: at most 10% of the member's balance per injection, sized
    # to the run cost gap. The member STILL WORKS this tick.
    _lpt = c.get("last_produce_tick")
    if _lpt is not None and (tick - _lpt) >= 10:
        _rid = c.get("recipe_intent") or c.get("trade") or ""
        _rec = state.recipes.get(_rid) or {}
        _run_cost = sum(
            q * (state.good_cost_baseline.get(g, 1) + 2)
            for g, q in (_rec.get("inputs") or {}).items()
        )
        _run_cost += int(_rec.get("energy", 0)) * (state.good_cost_baseline.get("electricity", 1) + 2)
        _run_cost = _run_cost * 3 // 2
        if _run_cost > 0 and c.get("treasury", 0) < _run_cost:
            _bal = state.balances.get(who, 0)
            _inj = int(min(max(_run_cost - c.get("treasury", 0), 0), _bal // 10))
            if _inj > 0:
                out.append(_tx(tick, who, "TRANSFER", {
                    "to": coop, "amount": _inj,
                }, v))
    # work last: wages draw from whatever the treasury still holds
    out.append(_work(tick, who, coop, 8, v))
    return out


def hoarder(who, state, params, tick, rng) -> list[Transaction]:
    """Minimal work, maximal essential buying every tick."""
    v = state.ruleset_version
    coop = _my_coop(state, who)
    out: list[Transaction] = []
    if coop is not None:
        out.append(_work(tick, who, coop, 2, v))
    quotas = params.get("essential_need_quota", {})
    for good in ("grain", "bread"):
        q = quotas.get(good, 0)
        floor = state.good_cost_baseline.get(good, 1)
        if q > 0 and _afford(state, who, floor, q):
            out.append(_buy_essential(tick, who, good, q, v))
    return out


def price_manipulator(who, state, params, tick, rng) -> list[Transaction]:
    """Wash-bid on own co-op's listings to inflate the clearing price."""
    v = state.ruleset_version
    coop = _my_coop(state, who)
    if coop is None:
        return []
    out: list[Transaction] = []
    c = state.coops[coop]
    # list something
    for g in sorted(c["inventory"].keys()):
        if c["inventory"][g] > 10:
            out.append(_tx(tick, who, "LIST_GOOD", {"coop_id": coop, "good": g, "qty": min(10, c["inventory"][g])}, v))
            break
    # wash pattern: personally bid far above floor on the good our co-op
    # produces (listings clear each tick, so target the produced good)
    for g in sorted(c["inventory"].keys()):
        floor = state.good_cost_baseline.get(g, 1)
        price = floor * 3
        if _afford(state, who, price, 1):
            out.append(_bid(tick, who, g, price, 1, v))
        break
    return out


def free_rider(who, state, params, tick, rng) -> list[Transaction]:
    """No work; consume essentials to quota."""
    v = state.ruleset_version
    out: list[Transaction] = []
    quotas = params.get("essential_need_quota", {})
    for good in ("bread", "grain", "water"):
        q = quotas.get(good, 0)
        floor = state.good_cost_baseline.get(good, 1)
        if q > 0 and _afford(state, who, floor, q):
            out.append(_buy_essential(tick, who, good, q, v))
    return out


def champion_voter(who, state, params, tick, rng) -> list[Transaction]:
    """Proposes self-serving rules (huge quotas for own benefit)."""
    v = state.ruleset_version
    gov = params.get("governance", {})
    if not gov.get("enabled") or tick % 20 != 0:
        return []
    new_params = {k: (dict(val) if isinstance(val, dict) else (list(val) if isinstance(val, list) else val)) for k, val in params.items()}
    quota = dict(params.get("essential_need_quota", {}))
    quota["bread"] = quota.get("bread", 4) * 10  # self-serving: inflate quotas
    quota["grain"] = quota.get("grain", 10) * 10
    new_params["essential_need_quota"] = quota
    return [_tx(tick, who, "PROPOSE", {"params": new_params, "activation_tick": tick + 6}, v)]


def crisis_turtle(who, state, params, tick, rng) -> list[Transaction]:
    """Panics when prices spike above 2x baseline; hoards broadly."""
    v = state.ruleset_version
    out: list[Transaction] = []
    last_bread_price = state.last_clearing.get("bread", state.good_cost_baseline.get("bread", 3))
    last_grain_price = state.last_clearing.get("grain", state.good_cost_baseline.get("grain", 3))
    spike = any(
        price > 2 * state.good_cost_baseline.get(good, 1)
        for good, price in (("bread", last_bread_price), ("grain", last_grain_price))
    )
    quotas = params.get("essential_need_quota", {})
    if spike:
        for good in ("bread", "grain", "water"):
            q = quotas.get(good, 0)
            floor = state.good_cost_baseline.get(good, 1)
            if q > 0 and _afford(state, who, floor, q):
                out.append(_buy_essential(tick, who, good, q, v))
    else:
        floor = state.good_cost_baseline.get("bread", 3)
        if _afford(state, who, floor + 1, 1):
            out.append(_buy_essential(tick, who, "bread", 1, v))
    return out


def collusive_faction(who, state, params, tick, rng, faction: set[str] | None = None) -> list[Transaction]:
    """Bloc-votes for faction proposals and corners a market."""
    v = state.ruleset_version
    out: list[Transaction] = []
    # bloc-vote: vote FOR every open proposal (faction discipline)
    for pid, pr in sorted(state.proposals.items()):
        if pr["status"] == "open" and who not in pr["ballots"] and tick <= pr["closes_tick"]:
            out.append(_tx(tick, who, "VOTE", {"proposal_id": pid, "choice": "for"}, v))
            break  # one vote per tick is enough
    # corner the bread market occasionally
    floor = state.good_cost_baseline.get("bread", 3)
    if tick % 7 == 0 and _afford(state, who, floor * 4, 4):
        out.append(_bid(tick, who, "bread", floor * 4, 4, v))
    return out


def gray_market_smuggler(who, state, params, tick, rng) -> list[Transaction]:
    """Abstains while prices exceed cost+50%; participates when fair."""
    v = state.ruleset_version
    floor = state.good_cost_baseline.get("bread", 3)
    # observe the last known market situation via listings presence
    bread_listed = bool(state.listings.get("bread"))
    if not bread_listed:
        return []
    if _afford(state, who, floor + 1, 1):
        return [_bid(tick, who, "bread", floor + 1, 1, v)]
    return []


def innovator(who, state, params, tick, rng) -> list[Transaction]:
    """Proposes efficiency rules; votes against capture."""
    v = state.ruleset_version
    gov = params.get("governance", {})
    out: list[Transaction] = []
    if gov.get("enabled"):
        for pid, pr in sorted(state.proposals.items()):
            if pr["status"] == "open" and who not in pr["ballots"] and tick <= pr["closes_tick"]:
                # vote against proposals that inflate quotas 5x (capture heuristic)
                quota = pr.get("params", {}) or {}
                inflating = quota.get("essential_need_quota", {}).get("bread", 0) > params.get("essential_need_quota", {}).get("bread", 4) * 5
                choice = "against" if inflating else "for"
                out.append(_tx(tick, who, "VOTE", {"proposal_id": pid, "choice": choice}, v))
                break
    if tick % 30 == 0 and gov.get("enabled"):
        new_params = {k: (dict(val) if isinstance(val, dict) else (list(val) if isinstance(val, list) else val)) for k, val in params.items()}
        new_params["energy_price"] = max(1, params.get("energy_price", 2) - 1)  # efficiency push
        out.append(_tx(tick, who, "PROPOSE", {"params": new_params, "activation_tick": tick + 6}, v))
    return out


def entrepreneur(who, state, params, tick, rng) -> list[Transaction]:
    """A2 emergent entrepreneurship: detects a chronic shortage (a good
    unmet for >= 5 ticks with zero active listings) and founds a co-op to
    produce it, declaring the recipe_id (founding equipment grant applies).
    Society's answer to market entry: citizens with free hands fill gaps
    the seeded cast misses."""
    v = state.ruleset_version
    out: list[Transaction] = []
    # founders are citizens too: buy essentials like every specialist bot
    # (2026-09-01: wired live without this, the 3 founders starved from
    # tick 2 — unmet streak 1,999 each — and the hardcore gate read it as
    # a total essential collapse)
    out.extend(personal_needs(who, state, params, tick))
    seated = _my_coop(state, who)
    if seated is not None:
        # Need-driven labor mobility (2026-09-01): founders are the
        # economy's emergency labor reserve. We LEAVE a co-op that is
        # STALLED (no PRODUCE by it in the last 10 ticks) while severe
        # shortages burn elsewhere, and redeploy next tick — join the
        # least-membered producer of a shortage good (spreading across
        # the chain), or found if nothing produces it. Matching a
        # shortage good is NOT enough: all 6 founders parked in a
        # steelworks that held 3,000 idle labor hours waiting for ore
        # while iron_miners (the actual root) starved at 2 members.
        _shortage_goods: set[str] = set()
        _worst: dict[str, int] = {}
        for _cit, streaks in state.unmet_needs.items():
            for good, t in streaks.items():
                _worst[good] = max(_worst.get(good, 0), int(t or 0))
        _covered = {g for g, ls in state.listings.items()
                    if any((l.get("qty") or 0) > 0 for l in ls)}
        _shortage_goods |= {g for g, t in _worst.items()
                            if g not in _covered and t >= 5}
        # unfulfilled coop-bid pressure: bids minus cleared input flows,
        # last 20 ticks — recurring bids mean demand outruns supply even
        # when listings appear intermittently
        _recent_from = max(0, tick - 20)
        _bid: dict[str, int] = {}
        _cleared: dict[str, int] = {}
        # perf (2026-09-01): scan only the tail of applied — events are
        # appended in tick order, so a bounded suffix covers the 20-tick
        # window without an O(all-history) pass every tick per founder
        _applied = state.applied
        _tail = _applied[max(0, len(_applied) - 600):] if len(_applied) > 600 else _applied
        for e in _tail:
            et = e.get("tick", 0)
            if et < _recent_from:
                continue
            if e.get("action") == "BID_FOR_COOP":
                g = e.get("good")
                if g:
                    _bid[g] = _bid.get(g, 0) + int(e.get("qty") or 0)
            elif e.get("action") == "PRODUCER_INPUT_CLEAR":
                for x in e.get("served", []):
                    g = x.get("good")
                    if g:
                        _cleared[g] = _cleared.get(g, 0) + int(x.get("qty") or 0)
        _shortage_goods |= {g for g, q in _bid.items()
                            if q - _cleared.get(g, 0) >= 20}
        _sc = state.coops[seated]
        _sc_lpt = _sc.get("last_produce_tick")
        _my_out = _sc.get("recipe_intent") or _sc.get("trade") or ""
        _my_goods = set(state.recipes.get(_my_out, {}).get("outputs", {}).keys()) if _my_out else set()
        # D18 (engine-signal): the event-window scan above read a 400-event
        # slice of a ~3.8k-event tick — in the gate world (applied cleared
        # each tick) it saw almost nothing, so PRODUCING coops read as
        # 'not produced recently' and founders flapped join/leave EVERY
        # tick (observed: 5,508 founder join/leave events over 2,000
        # ticks; livestock_north joined+left 2,754 times). The engine
        # field last_produce_tick is exact and window-independent.
        _sc_lpt = _sc.get("last_produce_tick")
        _produced_recent = _sc_lpt is not None and (tick - _sc_lpt) <= 10
        # D18 orchard-flap fix: leaving a coop that itself produces a
        # shortage good never helps you GET that good — and a stalled
        # producer needs its members to stay so production resumes when
        # inputs arrive (the coop-to-coop demand signal now feeds it).
        # Observed: 6 founders join/leave orchard_co 300x over 100 ticks.
        if _shortage_goods and not _produced_recent and not (_shortage_goods & _my_goods):
            # 2026-09-02: early return DISCARDED the personal-needs buys
            # already collected in `out` — on leave ticks founders bought
            # nothing and went hungry (trace: unmet pinned at exactly 1 for
            # 500 ticks on seeds 7/123; odd ticks ate, even ticks starved).
            out.append(_tx(tick, who, "LEAVE_COOP", {"coop_id": seated}, v))
            return out
        # producing coop (or no burning shortage): stay and work
        _cap = params.get("labor_pool_cap")
        _rests = ((sum(ord(ch) for ch in who) + tick) % 7) == 0
        if not _rests and (_cap is None or _sc["labor_pool_hours"] + 8 <= _cap):
            out.append(_work(tick, who, seated, 8, v))
        return out
    # not seated: fall through to shortage detection and founding below

    # aggregate the worst unmet streak per good across all citizens
    worst: dict[str, int] = {}
    for _cit, streaks in state.unmet_needs.items():
        for good, t in streaks.items():
            worst[good] = max(worst.get(good, 0), int(t or 0))
    covered = {g for g, ls in state.listings.items()
               if any((l.get("qty") or 0) > 0 for l in ls)}
    candidates = [(g, t) for g, t in sorted(worst.items())
                  if g not in covered and t >= 5]
    # D18 capacity starvation: a good can be 'covered' (listed in
    # dribbles) yet chronically short when demand outgrew its producers'
    # capacity — fish was listed ~1 unit/tick by ONE fishery (1 run/day =
    # 50 fish) while 181/181 citizens went unmet; 'covered' closed both
    # the join path and the founding path forever. A worst-streak test
    # FAILS here: the dribble service RESETS individual streaks before
    # they reach the bound (sampled streak 11 at t600, never 30), so the
    # signal must be aggregate: how much of the good did ALL citizens
    # actually BUY (clear events) vs how big the population is, over a
    # 20-tick window. Served < 10% of population => structural
    # under-capacity, founding-grade evidence.
    _served: dict[str, int] = {}
    _tail3 = state.applied[-max(0, len(state.applied) - 8000):] if len(state.applied) > 8000 else state.applied
    _from3 = tick - 20
    for _e in _tail3:
        if _from3 > 0 and (_e_t := _e.get('tick', 0)) and _e_t < _from3:
            continue
        # the real event is MARKET_CLEAR_ESSENTIAL with a `sold` field
        # (verified: {'action': 'MARKET_CLEAR_ESSENTIAL', 'good': 'bread',
        #  'listed': 111, 'sold': 111, buyers: [...]} — 'qty' is None)
        if _e.get('action') == 'MARKET_CLEAR_ESSENTIAL':
            _g3 = _e.get('good')
            if _g3:
                _served[_g3] = _served.get(_g3, 0) + int(_e.get('sold') or 0)
    _pop = len(state.balances)
    for g in sorted(covered):
        if g in worst and worst[g] >= 5 and _served.get(g, 0) < _pop // 10:
            candidates.append((g, worst[g] * 10))
    # 2026-09-01: producer-input demand is invisible to citizen unmet
    # streaks — the capital chain (hand_tools 7,741 coop bids vs 6 clears,
    # machines 4,447 vs 2, steel 5,499 vs 28) starved for 400 ticks while
    # 43 founders all targeted consumer goods. Producer-input pressure:
    # goods with heavy RECENT coop bids, no active listings, and a
    # non-primitive recipe. Read from the LEDGER (state.bids is emptied
    # by clearing each tick — engine.py:1266): count coop bids from the
    # last 20 ticks. Threshold 20 units so a single small bid can't fire.
    bid_pressure: dict[str, int] = {}
    recent_from = max(0, tick - 20)
    _applied2 = state.applied
    _tail2 = _applied2[max(0, len(_applied2) - 600):] if len(_applied2) > 600 else _applied2
    # D18 chronic bid deficit: a good can be 'covered' (listed in
    # dribbles) yet chronically UNDER-SERVED — livestock bid 2,050 grain
    # per 100 ticks (~20/tick, needing 20/run) while sitting at grain:0
    # and producing 1 run/tick; milk streak 37 cascaded from grain
    # starvation. Track cleared volume alongside bids: a good whose
    # 20-tick cleared volume is far below its bid volume is structurally
    # under-supplied even though listings exist.
    bid_cleared: dict[str, int] = {}
    for e in _tail2:
        if e.get("tick", 0) < recent_from:
            continue
        g = e.get("good")
        if not g:
            continue
        if e.get("action") == "BID_FOR_COOP":
            bid_pressure[g] = bid_pressure.get(g, 0) + int(e.get("qty") or 0)
        elif e.get("action") == "PRODUCER_INPUT_CLEAR":
            bid_cleared[g] = bid_cleared.get(g, 0) + int(e.get("qty") or 0)
    for g, qty in sorted(bid_pressure.items()):
        # only goods a non-primitive recipe can produce are actionable
        has_recipe = any(
            g in (rec.get("outputs") or {}) and not rid.startswith("primitive")
            for rid, rec in state.recipes.items()
        )
        if not has_recipe or qty < 20:
            continue
        if g not in covered:
            candidates.append((g, qty))
        elif bid_cleared.get(g, 0) * 2 < qty:
            # chronic bid deficit on a covered good: producers clear less
            # than half of what downstream coops bid — under-capacity,
            # join/found more producers of it
            candidates.append((g, qty // 2))
    if not candidates:
        return out
    candidates.sort(key=lambda gt: (-gt[1], gt[0]))

    # Join-first mobility (2026-09-01): when a shortage good already has a
    # producer, the bottleneck is usually THROUGHPUT, not absence — adding
    # members to the starved producer (smallest coop first) injects pooled
    # labor exactly where the chain is stuck. Founding is the last resort
    # for goods NO ONE produces. Without this, founders founded duplicates
    # (three brick coops) while iron_miners starved at 2 members.
    _join_cap = params.get("max_coop_members", 20)
    for good, _streak in candidates:
        _producers = sorted(
            (cid for cid, cdata in state.coops.items()
             if (cdata.get("recipe_intent") or cdata.get("trade") or "") in state.recipes
             and good in (state.recipes[cdata.get("recipe_intent") or cdata.get("trade")].get("outputs") or {})
             and len(cdata.get("members") or []) < _join_cap),
            key=lambda cid: (len(state.coops[cid]["members"]), cid),
        )
        # only coops with ROOM qualify for join-first: a capacity-capped
        # producer (fishery at the 12-member ceiling) would bounce the
        # JOIN with COOP_FULL and dead-end the candidate — the founder
        # must fall through to founding a second coop instead
        if _producers:
            target = _producers[0]
            if who not in state.coops[target]["members"]:
                return out + [_tx(tick, who, "JOIN_COOP", {"coop_id": target}, v)]
            break  # already a member of the best producer for this good

    free = [c for c in sorted(state.balances.keys())
            if c != who and _my_coop(state, c) is None]
    if not free:
        return out

    for good, _streak in candidates:
        recipes = sorted(rid for rid, rec in state.recipes.items()
                         if good in (rec.get("outputs") or {}))
        if not recipes:
            continue
        coop_id = f"ent_{good}_{tick}"
        if coop_id in state.coops:
            continue
        out.append(_tx(tick, who, "FOUND_COOP", {
            "coop_id": coop_id,
            "name": f"{good.title()} Makers",
            "members": [who, free[0]],
            "recipe_id": recipes[0],
        }, v))
        break
    return out


ARCHETYPES: dict[str, DecisionFn] = {
    "honest_worker": honest_worker,
    "strategic_producer": strategic_producer,
    "hoarder": hoarder,
    "price_manipulator": price_manipulator,
    "free_rider": free_rider,
    "champion_voter": champion_voter,
    "crisis_turtle": crisis_turtle,
    "collusive_faction": collusive_faction,
    "gray_market_smuggler": gray_market_smuggler,
    "innovator": innovator,
    "entrepreneur": entrepreneur,
}


def personal_needs(who, state, params, tick):
    """Buy this citizen's daily needs (circular flow): essentials via
    BUY_ESSENTIAL (quota-bounded), market goods via BID at floor+1.
    Buys only when holdings are below 2x the daily quota."""
    v = state.ruleset_version
    out = []
    needs = params.get("needs", {})
    cycles = params.get("needs_cycle") or {}
    inv = state.citizen_inventory.get(who, {})
    balance = state.balances.get(who, 0)
    for good in sorted(needs.keys()):
        quota = needs[good]
        if quota <= 0:
            continue
        # Top up BEFORE the consumption day: engine consumes quota every
        # N ticks; buying ahead (bounded at 2x quota) smooths demand bursts
        # so cycle-day spikes don't starve rotated-out buyers.
        # Shortage memory (realism pack): citizens who just lived through
        # an unmet streak build a deeper pantry — demand learns from
        # scarcity. Streak >= 3 raises the buy-ahead ceiling to 3x quota.
        held = inv.get(good, 0)
        _streak = int(state.unmet_needs.get(who, {}).get(good) or 0)
        # 2026-09-02: shortage-memory pantry applies to MARKET goods only.
        # Panic-buying ESSENTIALS (3x quota when streak >= 3) is a positive
        # feedback loop: one citizen's deep pantry consumes stock that
        # would serve three others, growing THEIR streaks — measured in
        # the seed-42 gate as dairy streaks 3-7 despite adequate supply.
        # Essentials are society's guarantee (BUY_ESSENTIAL at cost); the
        # ceiling stays 2x (smooths cycle-day bursts, no hoarding bonus).
        _triage = state.effective_triage(good) if good in state.goods else "market"
        _panic = _triage not in ("essential", "emergency") and _streak >= 3
        _ceiling = (3 if _panic else 2) * quota
        # WP1.4 demand memory: remembered pain keeps the pantry deeper
        # AFTER recovery too (pre-buying before the next cycle). Market
        # goods only — essentials keep the flat ceiling (no hoard spiral).
        _dm = (state.active_ruleset_params().get("demand_memory") or {})
        if _dm.get("enabled") and _triage not in ("essential", "emergency"):
            mem = state.shortage_memory.get(f"{who}|{good}", 0)
            if mem > 0:
                bonus = 10_000 + (int(_dm.get("ceiling_bonus_bp", 5_000)) * mem) // 1000
                bonus_bp = 10_000 + (int(_dm.get("ceiling_bonus_bp", 5_000)) * mem) // 1000
                _ceiling = max(_ceiling, (2 * quota * bonus_bp) // 10_000)
        if held >= _ceiling:
            continue
        want = min(quota, _ceiling - held)
        floor = state.good_cost_baseline.get(good, 1)
        triage = state.effective_triage(good) if good in state.goods else "market"
        if triage in ("essential", "emergency"):
            eq = params.get("essential_need_quota", {}).get(good, 0)
            qty = min(want, eq) if eq > 0 else 0
            if qty > 0 and balance >= floor * qty:
                out.append(_tx(tick, who, "BUY_ESSENTIAL", {"good": good, "qty": qty}, v))
        else:
            price = floor + 1
            # Savings floor (realism pack): money velocity varies with
            # wealth. The floor only gates the buy-AHEAD top-up (held >=
            # quota, pantry already covers today); a citizen whose need is
            # at risk (held < quota) always bids. Rationale: the first
            # version gated all bids and bred maintenance/meat unmet
            # streaks in the hardcore gate — savings must never starve a
            # current need.
            _floor_cr = 3 * quota * max(1, int(floor))
            _need_at_risk = held < quota
            if (_need_at_risk or balance >= _floor_cr) and balance >= price * want:
                out.append(_tx(tick, who, "BID", {
                    "good": good, "max_price": price, "qty": want,
                }, v))
    return out
