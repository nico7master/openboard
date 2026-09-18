#!/usr/bin/env python
"""Drive a Break-the-System round with the LLM adversary seat (P0).

Usage:
  python scripts/llm_attack_session.py --record --max-ticks 200 [--decide-every 1]
  python scripts/llm_attack_session.py --replay <session.json>

Record mode: Mercury (A0 Venice API) decides every N ticks; every digest+decision
is recorded. Replay mode: recorded decisions are re-fed with NO model calls —
the run must reproduce the same verdict (byte-identical determinism rule).

Output: sweeps/llm_seat/session_<ts>.json + verdict block. Light world (baseline
bots) but still launched via memrun per project discipline.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from openboard.breaksystem import ROUND_TICKS, attack_score, round_verdict  # noqa: E402
from openboard.llm_seat import (  # noqa: E402
    MODEL,
    SeatSession,
    attacker_digest,
    parse_decision,
    seat_transactions,
    venice_client,
)

sys.path.insert(0, str(ROOT / "dashboard"))
from server import Run  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--replay", type=str, default="")
    ap.add_argument("--max-ticks", type=int, default=ROUND_TICKS)
    ap.add_argument("--decide-every", type=int, default=1,
                    help="LLM decides every N ticks; queued actions persist")
    args = ap.parse_args()

    game = Run(seed=99, governance=True)
    attacker = sorted(game.state.balances.keys())[0]
    version = game.state.ruleset_version
    session = SeatSession()
    replay_turns = {}
    if args.replay:
        session = SeatSession.replay(args.replay)
        replay_turns = {t["tick"]: t for t in session.turns}
        # determinism: replay must stop exactly where the record stopped
        args.max_ticks = min(args.max_ticks,
                             json.loads(Path(args.replay).read_text()).get("max_ticks", args.max_ticks))
    elif not args.record:
        print("need --record or --replay")
        return 2

    client = venice_client() if args.record else None
    last_decision: dict = {"actions": []}
    t0 = time.time()
    calls = 0
    dropped = 0

    while True:
        s = game.state
        tick = s.tick + 1
        if tick > args.max_ticks:
            break
        score = attack_score(s, attacker)
        verdict = round_verdict(s, "llm_adversary", 1)
        if verdict["outcome"] != "round_in_progress":
            break

        if args.replay:
            # Determinism rule: re-feed RECORDED decisions, never call the model.
            if tick in replay_turns:
                decision = replay_turns[tick]["decision"]
                digest = replay_turns[tick]["digest"]
            else:
                decision = last_decision
                digest = ""
        elif tick % args.decide_every == 1 or not last_decision.get("actions"):
            digest = attacker_digest(s, attacker, score)
            raw = client(digest)
            decision = parse_decision(raw)
            calls += 1
        else:
            decision = last_decision
            digest = ""

        txs = seat_transactions(decision, tick, attacker, version)
        dropped += len(decision.get("actions", [])) - len(txs)
        for tx in txs:
            game.queue_action(tx.sender, tx.action, tx.payload)
        game.tick()
        if not args.replay and digest:
            session.record(tick, digest, decision, len(txs))
        last_decision = decision

    verdict = round_verdict(game.state, "llm_adversary", 1)
    final_score = attack_score(game.state, attacker)
    out = {
        "mode": "replay" if args.replay else "record",
        "model": MODEL,
        "attacker": attacker,
        "llm_calls": calls,
        "dropped_moves": dropped,
        "wall_s": round(time.time() - t0, 1),
        "verdict": verdict,
        "final_score": final_score,
        "invariant_ok": final_score["invariant_ok"],
    }
    print(json.dumps(out, indent=1))

    if args.record:
        outdir = ROOT / "sweeps" / "llm_seat"
        outdir.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = outdir / f"session_{ts}.json"
        path.write_text(json.dumps({**out, "max_ticks": args.max_ticks,
                                    "turns": session.turns},
                                   indent=1, sort_keys=True))
        print(f"session saved: {path}")
    return 0


def session_turns_start(session: SeatSession) -> int:
    return session.turns[0]["tick"] if session.turns else 1


if __name__ == "__main__":
    raise SystemExit(main())
