"""Audit 2026-09-20 package P-GAME: regression pins for the game-layer
findings C1/C2/C3/C4/C5/C6/C7/C8/C9/C10/C11/C16. All offline; no live LLM."""
import importlib.util
import json
import threading
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "dashboard_server_audit_game", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
)
server = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(server)

from openboard.breaksystem import FLAG_DAMAGE_CAP, attack_score, round_verdict, worst_unmet_streak  # noqa: E402
from openboard import breaksystem as bs_mod  # noqa: E402
from openboard.state import genesis_state  # noqa: E402


# ---------------------------------------------------------------- C1
def test_c1_no_post_round_farming(tmp_path, monkeypatch):
    """The full farm: play a real round to completion, then post-round acts
    are refused and the leaderboard holds EXACTLY ONE entry for the player."""
    monkeypatch.setattr(server, "LEADERBOARD_PATH", tmp_path / "lb.json")
    with server.app.test_client() as c:
        st = c.post("/api/attack/start",
                    json={"playbook": "wage_mint", "player": "farm1"}).get_json()
        assert st["ok"] is True
        final = None
        for _ in range(210):
            r = c.post("/api/attack/act", json={"player": "farm1"}).get_json()
            assert r["ok"] is True
            if r["over"]:
                final = r
                break
        assert final is not None, "round should end within 210 ticks"
        # post-round act refused; the final verdict stays readable
        r2 = c.post("/api/attack/act", json={"player": "farm1"}).get_json()
        assert r2["ok"] is False and r2["over"] is True
        assert "round over" in r2["error"]
        assert r2["verdict"]["playbook"] == "wage_mint"
        # exactly one leaderboard entry despite 100+ refused attempts possible
        board = server._leaderboard_load()
        assert sum(1 for e in board if e["player"] == "farm1") == 1


# ---------------------------------------------------------------- C2
def test_c2_per_player_games_do_not_collide():
    """A second visitor's start no longer overwrites the first's live round."""
    with server.app.test_client() as c:
        sa = c.post("/api/attack/start", json={"playbook": "hoarder", "player": "alice"}).get_json()
        sb = c.post("/api/attack/start", json={"playbook": "wage_mint", "player": "bob"}).get_json()
        assert sa["ok"] and sb["ok"]
        ga = server.app.attack_games["alice"]["game"]
        gb = server.app.attack_games["bob"]["game"]
        assert ga is not gb
        b_tick = gb.state.tick  # constructor runs the founding tick (1)
        act = c.post("/api/attack/act", json={"player": "alice"}).get_json()
        assert act["ok"] is True
        assert gb.state.tick == b_tick     # bob's world untouched by alice's act
        assert act["tick"] == ga.state.tick > b_tick


# ---------------------------------------------------------------- C3
def test_c3_playbook_pinned_per_round():
    """Mid-round playbook switching is refused by pinning: the round's
    playbook acts and is credited, whatever the request body claims."""
    with server.app.test_client() as c:
        c.post("/api/attack/start", json={"playbook": "hoarder", "player": "pinner"})
        act = c.post("/api/attack/act",
                     json={"playbook": "wage_mint", "player": "pinner"}).get_json()
        assert act["ok"] is True
        assert act["playbook"] == "hoarder"        # pinned
        assert act["verdict"]["playbook"] == "hoarder"


# ---------------------------------------------------------------- C4+C5
def _mini_state():
    return genesis_state({"a": 500, "b": 500, "c": 500})


def test_c4_unmet_damage_is_delta_over_baseline():
    """Background starvation before the round is the baseline; only the
    attacker's delta counts toward damage and the stop condition."""
    st = _mini_state()
    st.unmet_needs.setdefault("a", {})
    st.unmet_needs["a"]["bread"] = 12  # pre-existing harm (worst streak 12)
    base = worst_unmet_streak(st)
    v = round_verdict(st, "hoarder", start_tick=0, baseline_streak=base)
    assert v["streak_caused"] == 0 and v["damage"] == 0
    assert v["outcome"] == "round_in_progress"
    st.unmet_needs["a"]["bread"] = 25  # attacker worsened it by 13
    v2 = round_verdict(st, "hoarder", start_tick=0, baseline_streak=base)
    assert v2["streak_caused"] == 13
    assert v2["damage"] == 13 * 10


def test_c5_flag_damage_capped():
    """Flag-storm farming is dead: flag damage caps at FLAG_DAMAGE_CAP."""
    st = _mini_state()
    for i in range(FLAG_DAMAGE_CAP + 15):
        st.flags.append({"tick": 1, "kind": "HOARD", "target": "a"})
    v = round_verdict(st, "hoarder", start_tick=0, baseline_streak=0)
    assert v["flags_caused"] == FLAG_DAMAGE_CAP + 15
    assert v["damage"] == FLAG_DAMAGE_CAP * 100  # capped, not (cap+15)*100


# ---------------------------------------------------------------- C6
def test_c6_real_invariant_check_with_baseline():
    """With a round baseline, the advertised money check is REAL (a broken
    total is reported), not the always-self-consistent fallback."""
    st = _mini_state()
    base = attack_score(st)["money_total"]
    st.surplus_pool += 500  # mint money out of thin air (no mint event)
    sc = attack_score(st, baseline=base)
    assert sc["invariant_ok"] is False
    assert "money invariant" in sc["invariant_violation"]


# ---------------------------------------------------------------- C7
def test_c7_pending_actions_survive_save_restore():
    """Queued human actions are ledger inputs — they persist and restore."""
    run = server.Run(seed=7, governance=False)
    run.queue_action(sorted(run.state.balances.keys())[0], "WORK",
                     {"coop_id": sorted(run.state.coops.keys())[0]})
    save = run.to_save()
    assert len(save["pending"]) == 1
    run2 = server.Run.from_save(save)
    assert len(run2.pending) == 1
    assert run2.pending[0].action == "WORK"
    assert run2.pending[0].sender == run.pending[0].sender


# ---------------------------------------------------------------- C8
def test_c8_autosave_failure_surfaces(tmp_path, monkeypatch):
    """Autosave never fatal, never silent: failure returns False, appends a
    surfaced warning; success clears through and returns True."""
    monkeypatch.setattr(server, "AUTOSAVE_PATH", tmp_path / "ok.json")
    assert server._autosave_once() is True
    monkeypatch.setattr(server, "AUTOSAVE_PATH", Path("/proc/nope/dir/x.json"))
    n = len(server.AUTOSAVE_WARN)
    assert server._autosave_once() is False
    assert len(server.AUTOSAVE_WARN) == n + 1


# ---------------------------------------------------------------- C9
def test_c9_leaderboard_atomic_under_concurrency(tmp_path, monkeypatch):
    """Concurrent finishes cannot wipe each other's entries."""
    monkeypatch.setattr(server, "LEADERBOARD_PATH", tmp_path / "lb.json")
    errs = []

    def worker(i):
        try:
            server._leaderboard_record(f"p{i}", {
                "playbook": "hoarder", "damage": 100 + i, "flags_caused": 1,
                "worst_unmet_streak": 0, "ticks_played": 5,
                "outcome": "stopped_by_system"})
        except Exception as e:  # pragma: no cover
            errs.append(e)

    ts = [threading.Thread(target=worker, args=(i,)) for i in range(12)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert not errs
    board = server._leaderboard_load()
    assert len(board) == 12  # every entry survived the race


# ---------------------------------------------------------------- C10
def test_c10_bound_citizen_needs_token():
    """An account-bound citizen can only be acted for with its own token;
    anonymous citizens stay open for local single-machine play."""
    with server.app.test_client() as c:
        run = server.RUN
        free = sorted(run.state.balances.keys())[0]
        run.bots.pop(free, None)  # a claimed seat is no longer bot-driven
        reg = c.post("/api/account/register",
                     json={"name": "acct_c10", "password": "hunter2",
                           "citizen": free}).get_json()
        assert reg["ok"] is True
        anon = c.post("/api/action", json={"sender": free, "action": "IDLE",
                                           "payload": {}}).get_json()
        assert anon["ok"] is False and anon["error"].startswith("this citizen has an account")
        wrong = c.post("/api/action", headers={"X-Auth-Token": "badtoken"},
                       json={"sender": free, "action": "IDLE", "payload": {}}).get_json()
        assert wrong["ok"] is False
        good = c.post("/api/action", headers={"X-Auth-Token": reg["token"]},
                      json={"sender": free, "action": "IDLE", "payload": {}}).get_json()
        assert good["ok"] is True
        other = next(name for name in sorted(run.state.balances.keys())
                     if name != free)  # any un-bound citizen (bot citizens ok)
        unb = c.post("/api/action", json={"sender": other, "action": "IDLE",
                                          "payload": {}}).get_json()
        assert unb["ok"] is True  # un-bound citizens remain locally playable


# ---------------------------------------------------------------- C11
def test_c11_llm_stop_restores_bot_twin():
    """Stopping the seat puts the displaced bot twin back — no headless citizen."""
    run = server.Run(seed=3, governance=False)
    who = sorted(run.state.balances.keys())[0]
    twin = {"fn": run.bots[who]["fn"], "coop": None, "arch": "honest_worker"}
    run.bots.pop(who)
    server._LLM_TWIN.clear()
    server._LLM_TWIN.update({"game": run, "who": who, "entry": dict(twin)})
    assert server._llm_restore_twin() is True
    assert run.bots[who]["arch"] == "honest_worker"
    # a world that moved on (citizen gone) restores nothing, safely
    run.bots.pop(who)
    run.state.balances.pop(who)
    server._LLM_TWIN["who"] = who
    assert server._llm_restore_twin() is False
    server._LLM_TWIN.clear()


# ---------------------------------------------------------------- C16
def test_c16_no_duplicate_gini_key():
    """The duplicate dict key in attack_score is gone (source-level pin)."""
    src = Path(bs_mod.__file__).read_text()
    line = '        "gini_bp": gini(list(state.balances.values())),  # int, Gini x 10,000\n'
    assert src.count(line) == 1
