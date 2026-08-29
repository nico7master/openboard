"""B1: accounts + concurrency — register/login/logout with salted PBKDF2,
one citizen one seat, weak/wrong passwords rejected, and two humans
queueing actions for the same tick from two threads."""
import importlib.util
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "dashboard"))

from openboard.accounts import Accounts


def test_register_login_roundtrip():
    a = Accounts()
    tok = a.register("alice", "hunter2x", "c0")
    assert tok
    assert a.citizen_for_token(tok) == "c0"
    tok2 = a.login("alice", "hunter2x")
    assert tok2 and a.citizen_for_token(tok2) == "c0"


def test_wrong_password_rejected():
    a = Accounts()
    a.register("bob", "goodpass1", "c1")
    assert a.login("bob", "badpass") is None


def test_duplicate_account_and_citizen_rejected():
    a = Accounts()
    assert a.register("carol", "pass1234", "c2")
    assert a.register("carol", "other123", "c2") is None  # same account
    assert a.register("dave", "pass1234", "c2") is None   # one citizen, one seat


def test_weak_password_rejected():
    a = Accounts()
    assert a.register("eve", "abc", "c3") is None


def test_logout_kills_token():
    a = Accounts()
    tok = a.register("frank", "pass1234", "c4")
    a.logout(tok)
    assert a.citizen_for_token(tok) is None


def test_two_humans_same_tick_concurrent():
    """Multiplayer core: two humans act in the same tick from two threads;
    both actions queue for the same tick and the invariant holds."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "ds_conc", Path(__file__).resolve().parents[1] / "dashboard" / "server.py"
    )
    server = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(server)

    from openboard.breaksystem import invariants_ok

    r = server.Run(seed=42)
    old, server.RUN = server.RUN, r
    try:
        accts = Accounts()
        citizens = sorted(r.state.balances.keys())[:2]
        t1 = accts.register("h1", "pass1234", citizens[0])
        t2 = accts.register("h2", "pass1234", citizens[1])
        assert t1 and t2

        who1, who2 = accts.citizen_for_token(t1), accts.citizen_for_token(t2)
        results: list[str] = []

        def act(who):
            r.queue_action(who, "PROPOSE",
                           {"params": dict(r.state.active_ruleset_params()),
                            "activation_tick": r.state.tick + 5})
            results.append("done")

        threads = [threading.Thread(target=act, args=(who1,)),
                   threading.Thread(target=act, args=(who2,))]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert len(results) == 2
        assert len({tx.tick for tx in r.pending}) == 1  # same next tick
        r.tick()
        assert invariants_ok(r.state) is None
    finally:
        server.RUN = old
