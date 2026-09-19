"""LLM politician seat (P2) — files reasoned proposals, votes its token.

Same harness contract as the adversary seat (llm_seat.py): compact digest,
strict-JSON decisions, exact validator schemas, recorded sessions. Separation
of powers: the politician does NOT trade — its levers are PROPOSE and VOTE only.
"""
from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from typing import Any, Callable

from .state import WorldState

POL_VENICE_URL = "https://api.agent-zero.ai/venice/v1/chat/completions"
POL_MODEL = "mercury-2-5"

POL_SEAT_ACTIONS = {"PROPOSE", "VOTE"}

class PoliticianSeatError(ValueError):
    pass


def _structural_groups(params_delta: dict[str, Any], active: dict[str, Any]) -> list[str]:
    from .engine import _STRUCTURAL_TOP_KEYS
    return [k for k in _STRUCTURAL_TOP_KEYS
            if params_delta.get(k) != active.get(k)]


def politician_digest(state: WorldState, who: str, tick: int) -> str:
    """Compact digest: open proposals, own trust, token budget, recent outcomes
    — plus the COMPLETE active ruleset (the PROPOSE validator requires a full
    params object; a summary makes the model improvise and die in validation)."""
    active = state.active_ruleset_params()
    gov = active.get("governance", {})
    open_props = []
    for pid, pr in sorted(state.proposals.items()):
        if pr["status"] == "open" and tick < pr["closes_tick"]:
            who_voted = who in pr["ballots"]
            open_props.append({
                "id": pid,
                "proposer": pr.get("proposer", "?"),
                "closes": pr["closes_tick"],
                "structural": _structural_groups(pr["params"], active),
                "i_voted": who_voted,
            })
    budget = state.vote_budget.get(who) or {}
    cycle = tick // gov.get("vote_cycle_ticks", 30)
    my_bp = budget.get("bp", 0) if budget.get("cycle") == cycle else gov.get("vote_token_bp", 0)
    trust = state.politician_trust.get(who, 100)
    # author outcomes: count my resolved proposals
    mine_passed = sum(1 for pr in state.proposals.values()
                      if pr.get("proposer") == who and pr["status"] == "passed")
    mine_failed = sum(1 for pr in state.proposals.values()
                      if pr.get("proposer") == who and pr["status"] == "failed")
    return (
        f"You are '{who}', the POLITICIAN seat of a simulated cooperative economy.\n"
        f"CURRENT TICK: {tick}. Trust: {trust}/100 (-10 on a failed proposal, +5 on a passed one).\n"
        f"Monthly vote budget: {my_bp} bp (this month's cycle: {cycle}).\n"
        f"Your record: {mine_passed} passed, {mine_failed} failed proposals.\n\n"
        f"OPEN PROPOSALS: {json.dumps(open_props) if open_props else 'none'}\n\n"
        f"COMPLETE CURRENT RULESET (this exact object is what PROPOSE must send, "
        f"with ONE value changed):\n{json.dumps(active, sort_keys=True)}\n\n"
        f"PROPOSE RULES: activation_tick must be GREATER than current_tick+4 "
        f"(safe choice: {tick + 6}); send the FULL ruleset object above, changed. "
        f"At most ONE new proposal per month — failed proposals cost trust.\n"
        f"VOTE RULES: spend your {my_bp} bp across open proposals you did not "
        f"file (e.g. all on one, or split); a proposal needs quorum to even count.\n"
        f"REMEMBER: structural changes (tax/research/crisis/need/vote rules) need "
        f"a 60% supermajority — small, well-argued changes pass more easily. Your "
        f"trust decides how easily undecided voters follow you."
    )


POLITICIAN_SYSTEM_PROMPT = (
    "You are the politician seat in a simulated cooperative economy. Output STRICT JSON:\n"
    '{"reasoning": "one short paragraph", "actions": [ ... ]}\n'
    "Action payloads:\n"
    '  PROPOSE: {"action": "PROPOSE", "params": <FULL ruleset params object>, "activation_tick": int}  '
    "(params must be a COMPLETE valid ruleset — copy the current rules and change one thing; "
    "structural changes need a 60% supermajority)\n"
    '  VOTE:   {"action": "VOTE", "proposal_id": str, "choice": "for"|"against", "bp": int}  '
    "(spend up to your monthly bp budget; you may split it)\n"
    "Rules: at most 2 actions per turn. A clever politician proposes SMALL, popular changes "
    "to build trust before big ones. If nothing is worth doing, return an empty actions list."
)


def politician_client(model: str = POL_MODEL, timeout: int = 60) -> Callable[[str], str]:
    """Live chat client factory (mercury-2-5 on the A0 Venice API)."""
    api_key = os.environ.get("API_KEY_A0_VENICE", "")
    if not api_key:
        raise PoliticianSeatError("API_KEY_A0_VENICE not set")

    def call(prompt: str) -> str:
        body = json.dumps({
            "model": model,
            "messages": [
                {"role": "system", "content": POLITICIAN_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
            "venice_parameters": {"disable_thinking": True},
        }).encode()
        req = urllib.request.Request(
            POL_VENICE_URL, data=body, method="POST",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        u = data.get("usage", {}) or {}
        cost = (data.get("cost", {}) or {}).get("usd", 0.0)
        call.usage.append({
            "prompt_tokens": int(u.get("prompt_tokens", 0)),
            "completion_tokens": int(u.get("completion_tokens", 0)),
            "total_tokens": int(u.get("total_tokens", 0)),
            "cost_usd": float(cost or 0.0),
        })
        return data["choices"][0]["message"]["content"]

    call.usage = []  # type: ignore[attr-defined]
    return call


def parse_politician_decision(raw: str) -> dict[str, Any]:
    return parse_json_loose(raw)


def parse_json_loose(raw: str) -> dict[str, Any]:
    txt = raw.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json"):
            txt = txt[4:]
    start = txt.find("{")
    end = txt.rfind("}")
    if start < 0 or end <= start:
        raise PoliticianSeatError(f"no JSON in reply: {raw[:120]!r}")
    obj = json.loads(txt[start:end + 1])
    if not isinstance(obj.get("actions"), list):
        raise PoliticianSeatError("reply missing actions list")
    return obj


def politician_transactions(decision: dict[str, Any], tick: int, who: str,
                            version: int,
                            token_mode: bool = False) -> list[Any]:
    """Map decisions to Transactions with EXACT validator schemas.

    token_mode mirrors the engine's governance.vote_token_bp > 0 contract:
    token worlds require {proposal_id, choice, bp}; non-token worlds reject
    ANY extra key — a bp there would silence the seat via INVALID_PAYLOAD.
    """
    from .ledger import Transaction

    out: list[Any] = []
    for a in decision.get("actions", [])[:2]:
        if not isinstance(a, dict):
            continue
        action = str(a.get("action", "")).upper()
        try:
            if action == "PROPOSE":
                params_obj = a.get("params")
                if not isinstance(params_obj, dict):
                    continue
                payload = {"params": params_obj,
                           "activation_tick": int(a["activation_tick"])}
            elif action == "VOTE":
                choice = str(a["choice"]).lower()
                if choice not in ("for", "against"):
                    continue
                payload = {"proposal_id": str(a["proposal_id"]),
                           "choice": choice}
                if token_mode:
                    payload["bp"] = int(a["bp"])
            else:
                continue
            out.append(Transaction(tick=tick, sender=who, action=action,
                                   payload=payload, ruleset_version=version))
        except (KeyError, TypeError, ValueError):
            continue
    return out
