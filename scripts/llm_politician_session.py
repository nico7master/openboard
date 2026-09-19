#!/usr/bin/env python
"""Drive a governance session with the LLM politician seat (P2).

Usage:
  python scripts/llm_politician_session.py --record --max-ticks 100
  python scripts/llm_politician_session.py --replay <session.json>

Record: Mercury (A0 Venice API, mercury-2-5) decides every N ticks — files
reasoned proposals, spends its monthly splitable vote token. Replay:
recorded decisions are re-fed with ZERO model calls; the verdict must be
byte-identical (determinism rule).

World contract (matches the P2 spec): governance ON with persuasion dice,
60% structural tier, trust loop, and the founder's monthly vote token
(vote_token_bp=10000, cycle 30). The seat replaces its bot twin.
Output: sweeps/llm_seat/politician_<ts>.json + full accounting block.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openboard.llm_politician import (  # noqa: E402
    POL_MODEL,
    parse_politician_decision,
    politician_client,
    politician_digest,
    politician_transactions,
)

sys.path.insert(0, str(ROOT / "dashboard"))
from server import Run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--replay", type=str, default="")
    ap.add_argument("--max-ticks", type=int, default=100)
    ap.add_argument("--decide-every", type=int, default=3,
                    help="politician decides every N ticks (vote windows are 3)")
    args = ap.parse_args()

    game = Run(seed=99, governance=True)
    # P2 opt-in flags: persuasion dice + the founder's monthly vote token.
    # Token mode changes the VOTE payload contract (bp REQUIRED, exact keys)
    # — the seat mapping below switches with it. Non-token worlds reject ANY
    # extra key (INVALID_PAYLOAD), which would silently silence the seat.
    _gov = game.state.rulesets[-1]["params"].setdefault("governance", {})
    _gov["persuasion"] = True
    _gov["vote_token_bp"] = 10000
    # Quorum must be reachable by the actual voting cast: only ~20 citizens
    # hold political roles, so the default 50% (90 ballots) kills EVERY
    # proposal — bot or seat — with quorum failure (P2 live lesson).
    # 10% (18 ballots) lets the cast decide while scarcity still gates spam.
    _gov["quorum_bp"] = 1000
    who = sorted(game.state.balances.keys())[0]  # seat citizen (deterministic)
    game.bots.pop(who, None)  # the seat replaces its bot twin (no double votes)
    turns: list[dict] = []
    replay_turns: dict[int, dict] = {}
    if args.replay:
        doc = json.loads(Path(args.replay).read_text())
        turns = doc["turns"]
        replay_turns = {t["tick"]: t for t in turns}
        args.max_ticks = min(args.max_ticks, doc.get("max_ticks", args.max_ticks))
    elif not args.record:
        print("need --record or --replay")
        return 2

    client = politician_client() if args.record else None
    last_decision: dict = {"actions": []}
    malformed = 0
    dropped = 0
    filed_cycle: list[int] = []  # cycles in which the seat already filed
    t0 = time.time()

    while True:
        s = game.state
        tick = s.tick + 1
        if tick > args.max_ticks:
            break

        if args.replay:
            if tick in replay_turns:
                decision = replay_turns[tick]["decision"]
                digest = replay_turns[tick]["digest"]
            else:
                decision = last_decision
                digest = ""
        elif (tick - 1) % args.decide_every == 0 or not last_decision.get("actions"):
            digest = politician_digest(s, who, tick)
            raw = client(digest)
            try:
                decision = parse_politician_decision(raw)
            except Exception:
                decision = {"reasoning": f"MALFORMED_REPLY: {raw[:200]}", "actions": []}
                malformed += 1
        else:
            # re-queue guard: only VOTEs carry over — a re-queued PROPOSE
            # files a duplicate proposal every tick (P2 live lesson: 23
            # actions -> 50 filings, trust spiral to 0)
            decision = {"reasoning": last_decision.get("reasoning", ""),
                        "actions": [a for a in last_decision.get("actions", [])
                                    if str(a.get("action", "")).upper() == "VOTE"]}
            digest = ""

        # mechanical filing cap: ONE proposal per monthly cycle (30 ticks).
        # Prompt discipline failed live (26 filings in 100 ticks, session
        # 052110) — every extra failed filing burns -10 trust.
        cycle = (tick - 1) // 30
        if any(str(a.get("action", "")).upper() == "PROPOSE"
               for a in decision.get("actions", [])):
            if cycle in filed_cycle:
                decision = {"reasoning": decision.get("reasoning", "") +
                            " [one proposal per month — held back]",
                            "actions": [a for a in decision.get("actions", [])
                                        if str(a.get("action", "")).upper() != "PROPOSE"]}
            else:
                filed_cycle.append(cycle)

        # fresh version every tick: a passed proposal bumps it, and a stale
        # version would silently reject every later seat transaction
        version = game.state.ruleset_version
        txs = politician_transactions(decision, tick, who, version, token_mode=True)
        dropped += len(decision.get("actions", [])) - len(txs)
        for tx in txs:
            game.queue_action(tx.sender, tx.action, tx.payload)
        game.tick()
        if not args.replay and digest:
            turns.append({"tick": tick, "digest": digest,
                          "decision": decision, "tx_count": len(txs)})
        last_decision = decision

    # settle any still-open proposals to capture final outcomes
    open_ids = [pid for pid, pr in game.state.proposals.items() if pr["status"] == "open"]
    while open_ids and game.state.tick <= max(
            game.state.proposals[pid]["closes_tick"] for pid in open_ids):
        game.tick()
        open_ids = [pid for pid, pr in game.state.proposals.items()
                    if pr["status"] == "open"]

    usage = getattr(client, "usage", []) if args.record else []
    props = {pid: {"status": pr["status"], "proposer": pr.get("proposer")}
             for pid, pr in game.state.proposals.items()}
    out = {
        "mode": "replay" if args.replay else "record",
        "model": POL_MODEL,
        "seat": who,
        "persuasion": True,
        "vote_token": True,
        "proposals": props,
        "trust": game.state.politician_trust,
        "accounting": {
            "llm_calls": len(usage),
            "malformed_replies": malformed,
            "dropped_moves": dropped,
            "prompt_tokens": sum(u["prompt_tokens"] for u in usage),
            "completion_tokens": sum(u["completion_tokens"] for u in usage),
            "total_tokens": sum(u["total_tokens"] for u in usage),
            "cost_usd": round(sum(u["cost_usd"] for u in usage), 6),
        },
        "wall_s": round(time.time() - t0, 1),
        "final_tick": game.state.tick,
        "invariant_ok": all(b >= 0 for b in game.state.balances.values()),
        "max_ticks": args.max_ticks,
    }
    print(json.dumps(out, indent=1))
    if args.record:
        outdir = ROOT / "sweeps" / "llm_seat"
        outdir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = outdir / f"politician_{ts}.json"
        path.write_text(json.dumps({**out, "turns": turns}, indent=1, sort_keys=True))
        print(f"session saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
