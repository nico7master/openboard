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
SPECIALISTS = {
    "farmer": make_specialist("grain_farming", "grain", {"water": 5}, stock_target=100),
    "miller": make_specialist("grain_to_flour", "flour", {"grain": 10}, stock_target=100),
    "baker": make_specialist("flour_to_bread", "bread", {"flour": 5}, stock_target=100),
    "miner": make_specialist("coal_mining", "coal", {}, stock_target=120),
    "power_worker": make_specialist("electricity_coal", "electricity", {"coal": 4}, stock_target=250),
    "water_worker": make_specialist("water_service", "water", {"electricity": 5}, stock_target=250),
}

BASELINE_BOTS: list[tuple[str, Any, str]] = [
    # (name, decision fn, coop)
    ("farmer_a", SPECIALISTS["farmer"], "farmers"),
    ("farmer_b", SPECIALISTS["farmer"], "farmers"),
    ("miller_a", SPECIALISTS["miller"], "millers"),
    ("miller_b", SPECIALISTS["miller"], "millers"),
    ("baker_a", SPECIALISTS["baker"], "bakers"),
    ("baker_b", SPECIALISTS["baker"], "bakers"),
    ("miner_a", SPECIALISTS["miner"], "miners"),
    ("miner_b", SPECIALISTS["miner"], "miners"),
    ("power_a", SPECIALISTS["power_worker"], "power_plant"),
    ("power_b", SPECIALISTS["power_worker"], "power_plant"),
    ("water_a", SPECIALISTS["water_worker"], "water_works"),
    ("water_b", SPECIALISTS["water_worker"], "water_works"),
    ("worker_a", ARCHETYPES["honest_worker"], "farmers"),
    ("worker_b", ARCHETYPES["honest_worker"], "farmers"),
]

BASELINE_COOPS = [
    {"coop_id": "farmers", "members": ["farmer_a", "farmer_b", "worker_a", "worker_b"]},
    {"coop_id": "millers", "members": ["miller_a", "miller_b"]},
    {"coop_id": "bakers", "members": ["baker_a", "baker_b"]},
    {"coop_id": "miners", "members": ["miner_a", "miner_b"]},
    {"coop_id": "power_plant", "members": ["power_a", "power_b"]},
    {"coop_id": "water_works", "members": ["water_a", "water_b"]},
]

# Input-buying coops need starting treasuries to bootstrap their chains.
BASELINE_TREASURIES = {"millers": 600, "bakers": 600, "power_plant": 600, "water_works": 600}


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
    "farmer_a": "libertarian",
    "miner_a": "libertarian",
    "power_b": "libertarian",
    "water_b": "libertarian",
    "miller_a": "pragmatist",
    "miller_b": "pragmatist",
    "power_a": "pragmatist",
    "water_a": "pragmatist",
    "baker_b": "pragmatist",
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

        # tick 1: founding
        founding = [
            Transaction(tick=1, sender=plan["members"][0], action="FOUND_COOP",
                        payload={"coop_id": plan["coop_id"], "name": plan["coop_id"],
                                 "members": plan["members"]}, ruleset_version=1)
            for plan in BASELINE_COOPS
        ]
        self._apply_batch(1, founding)
        for coop, amount in BASELINE_TREASURIES.items():
            self._inject({"after_tick": 1, "op": "treasury", "coop": coop, "amount": amount})
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
        money = sum(s.balances.values()) + s.surplus_pool + treasuries + s.capital_fund
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
        params["triage_overrides"] = {}
        # Circular flow (2026-08-21): citizens need goods daily, surplus
        # returns to society. Both votable rule params like everything else.
        params["needs"] = {"bread": 1, "water": 1, "electricity": 1}
        params["surplus_spending"] = {
            "dividend_share_bp": 5_000,       # 50% of spendable pool
            "services_share_bp": 5_000,        # 50% funds essential refunds
            "min_pool_buffer": 500,            # never spend below this
            "max_dividend_per_tick": 200,      # anti-flood cap
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
        # Public capital maintenance until the toolsmith chain exists:
        # worn tools/machines replaced, cost retired from the pool (A3).
        params["capital_refresh"] = {"interval_ticks": 25, "hand_tools": 50, "machines": 5}
        # Patronage: co-op surplus above an operating buffer flows back to
        # worker-members. The buffer (1,600) also reserves rent capacity:
        # capital rent is charged from the treasury at use time, so a drained
        # treasury would underpay society (observed: miners captured ~1,100/machine).
        params["coop_distribution"] = {"buffer": 1_600, "share_bp": 5_000}
        # Utilities bridge: coal_mining consumes hand_tools/machines per
        # run and no toolsmith coop exists yet (capital goods = next
        # milestone). Larger votable endowment keeps utilities alive.
        params["bootstrap_endowment"] = {
            "water": 200, "electricity": 500,
            "hand_tools": 100, "machines": 25,
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
            "money_total": citizens_money + treasury_money + s.surplus_pool,
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
