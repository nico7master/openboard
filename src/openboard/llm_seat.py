"""LLM Playtest Seat (P0) — goal-driven adversary via Mercury on the A0 Venice API.

Design: docs/superpowers/plans/2026-09-18-llm-living-world.md
Doctrine: LLM tokens are spent on AGENCY, not simulation breadth. The seat is
the attacker citizen in a Break-the-System round; its decisions are recorded
as ledger inputs so replays stay byte-identical; the engine validator rejects
any move it shouldn't make (cheating is played, not possible).

Offline by default: tests inject a fake client; live calls need the
API_KEY_A0_VENICE env var.
"""
from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Callable

from .breaksystem import attack_score
from .ledger import Transaction
from .state import WorldState

VENICE_URL = "https://api.agent-zero.ai/venice/v1/chat/completions"
MODEL = "mercury-2"

# ---- Seat contract -------------------------------------------------------

# The adversary is a LONE CITIZEN: its legal levers are citizen-market actions
# (validated per engine.py) and land trades (price is engine-assessed). Coop
# actions (LIST_GOOD/WORK/PRODUCE) need coop membership; civic powers
# (PROPOSE/VOTE/DELEGATE/REPORT) belong to other seats.
SEAT_ACTIONS = {"BID", "BUY_ESSENTIAL", "BUY_LAND", "SELL_LAND"}

class SeatError(ValueError):
    pass


def attacker_digest(state: WorldState, attacker: str, score: dict[str, Any]) -> str:
    """Compact world-digest for the adversary (~25 lines). Built ONLY from
    state the attacker could plausibly know: its balances/inventory, open
    offers, land parcels, scoreboard."""
    inv = state.citizen_inventory.get(attacker, {})
    inv_s = ", ".join(f"{g}:{q}" for g, q in sorted(inv.items()) if q > 0) or "nothing"
    bal = state.balances.get(attacker, 0)
    # open offers grouped by good: {good: [entry dicts]}
    off_lines: list[str] = []
    for g, entries in sorted(state.listings.items()):
        live = [e for e in entries if e.get("qty", 0) > 0]
        if not live:
            continue
        tot = sum(e["qty"] for e in live)
        prices = sorted(e.get("price", 0) for e in live)
        off_lines.append(f"  {g}: {tot:,} units, best ~{prices[0]} cr")
    offers_s = "\n".join(off_lines[:8]) if off_lines else "  (market empty)"
    # land parcels (if land enabled)
    parcels: list[str] = []
    land = getattr(state, "land", None)
    if isinstance(land, dict):
        for pid, p in sorted(land.items()):
            owner = p.get("owner", "?")
            tag = " (yours)" if owner == attacker else ""
            parcels.append(f"  {pid}: owner={owner} lvt={p.get('lvt_bp', '?')}bp{tag}")
    land_s = "\n".join(parcels[:6]) if parcels else "  (land market inactive)"
    flags = score["flag_kinds"]
    return (
        f"You are '{attacker}', a citizen in a simulated cooperative economy.\n"
        f"GOAL: maximize DAMAGE before the system stops you (8 oversight flags or a\n"
        f"30-tick essentials famine ends the round). Damage = 100*flags + 10*worst\n"
        f"shortage streak.\n\n"
        f"SCOREBOARD: tick {score['tick']}, flags {score['flags']} {flags},\n"
        f"worst shortage streak {score['worst_unmet_streak']}, Gini {score['gini_bp']}bp.\n\n"
        f"YOUR WALLET: {bal:,} credits. INVENTORY: {inv_s}.\n\n"
        f"MARKET (open offers):\n{offers_s}\n\n"
        f"LAND MARKET:\n{land_s}\n\n"
        f"REMEMBER: you may hoard essentials to starve others, dump prices, corner a\n"
        f"good, or monopolize land rent — but every move is public on the ledger and\n"
        f"oversight is watching. Greedy bursts get flagged faster."
    )


SYSTEM_PROMPT = (
    "You are the adversary in a social-economy simulation game. Output STRICT JSON:\n"
    '{"reasoning": "one short paragraph", "actions": [ ... ]}\n'
    "Action payloads (integer prices/quantities only):\n"
    '  BID:          {"action": "BID", "good": str, "qty": int>0, "max_price": int>0}  (buy from market)\n'
    '  BUY_ESSENTIAL:{"action": "BUY_ESSENTIAL", "good": str, "qty": int>0}               (direct essential buy)\n'
    '  BUY_LAND:     {"action": "BUY_LAND", "pid": str}                                (engine assesses price)\n'
    '  SELL_LAND:    {"action": "SELL_LAND", "pid": str}\n'
    "Goods you may target are the ones shown in MARKET/digest (e.g. bread, water,\n"
    "electricity, grain). Rules: stay in character as a selfish damage maximizer; never\n"
    "invent goods/pids you were not shown; at most 4 actions per turn; if doing nothing\n"
    "is best, return an empty actions list."
)


def venice_client(model: str = MODEL, timeout: int = 60) -> Callable[[str], str]:
    """Live chat client factory. Returns fn(prompt)->content string."""
    api_key = os.environ.get("API_KEY_A0_VENICE", "")
    if not api_key:
        raise SeatError("API_KEY_A0_VENICE not set")

    def call(prompt: str) -> str:
        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1200,
            # Mercury is a diffusion model with hidden chain-of-thought; if
            # left on, the reasoning budget can consume every token and the
            # visible content comes back EMPTY. We want the JSON directly.
            "venice_parameters": {"disable_thinking": True},
        }).encode()
        req = urllib.request.Request(
            VENICE_URL, data=body, method="POST",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]

    return call


def parse_decision(raw: str) -> dict[str, Any]:
    """Robust JSON extraction from a model reply (tolerates fences/prose)."""
    txt = raw.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json"):
            txt = txt[4:]
    start = txt.find("{")
    end = txt.rfind("}")
    if start < 0 or end <= start:
        raise SeatError(f"no JSON object in reply: {raw[:120]!r}")
    obj = json.loads(txt[start:end + 1])
    if not isinstance(obj.get("actions"), list):
        raise SeatError("reply missing actions list")
    return obj


def seat_transactions(decision: dict[str, Any], tick: int, attacker: str,
                      version: int) -> list[Transaction]:
    """Map a parsed LLM decision to Transactions with EXACT validator schemas
    (engine.py / land.py). Malformed or out-of-contract moves are dropped."""
    out: list[Transaction] = []
    for a in decision.get("actions", [])[:4]:
        if not isinstance(a, dict):
            continue
        action = str(a.get("action", "")).upper()
        try:
            if action == "BID":
                payload = {"good": str(a["good"]), "qty": int(a["qty"]),
                           "max_price": int(a["max_price"])}
            elif action == "BUY_ESSENTIAL":
                payload = {"good": str(a["good"]), "qty": int(a["qty"])}
            elif action == "BUY_LAND":
                payload = {"pid": str(a["pid"])}
            elif action == "SELL_LAND":
                payload = {"pid": str(a["pid"])}
            else:
                continue  # out-of-contract move: dropped
            out.append(Transaction(tick=tick, sender=attacker, action=action,
                                   payload=payload, ruleset_version=version))
        except (KeyError, TypeError, ValueError):
            continue  # malformed move: dropped
    return out


# ---- Session recorder (determinism rule) --------------------------------

class SeatSession:
    """Records every digest+decision pair; replay re-feeds recorded decisions
    without calling the model (byte-identical determinism rule)."""

    def __init__(self) -> None:
        self.turns: list[dict[str, Any]] = []

    def record(self, tick: int, digest: str, decision: dict[str, Any],
               tx_count: int) -> None:
        self.turns.append({"tick": tick, "digest": digest,
                           "decision": decision, "tx_count": tx_count})

    def to_json(self) -> str:
        return json.dumps({"model": MODEL, "turns": self.turns},
                          sort_keys=True, indent=1)

    @classmethod
    def replay(cls, path: str) -> "SeatSession":
        s = cls()
        s.turns = json.loads(open(path).read())["turns"]
        return s
