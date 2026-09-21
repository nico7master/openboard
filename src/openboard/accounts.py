"""B1: multiplayer foundation — accounts + concurrency.

An account binds one login to one citizen. Passwords are salted PBKDF2
hashes (never stored raw); sessions are random tokens. Accounts are a
dashboard-layer concern: the engine only ever sees the citizen name.
Concurrency: the Run lock already serializes action queuing and ticking,
so two humans acting in the same tick is a tested norm, not an exception.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import threading
from typing import Any


def _new_salt() -> str:
    return secrets.token_hex(8)


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()


class Accounts:
    """In-memory account store; thread-safe (own lock)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._creds: dict[str, tuple[str, str]] = {}  # account -> (salt, hash)
        self._tokens: dict[str, str] = {}             # token -> account
        self._citizen_of: dict[str, str] = {}            # account -> citizen

    def register(self, name: str, password: str, citizen: str) -> str | None:
        """Create an account bound to a citizen; returns a session token.
        Fails (None) on duplicate account or weak password."""
        if not name or not password or len(password) < 4:
            return None
        with self._lock:
            if name in self._creds:
                return None
            if any(c == citizen for c in self._citizen_of.values()):
                return None  # one citizen, one seat
            salt = _new_salt()
            self._creds[name] = (salt, _hash_password(password, salt))
            self._citizen_of[name] = citizen
            token = secrets.token_hex(16)
            self._tokens[token] = name
            return token

    def login(self, name: str, password: str) -> str | None:
        with self._lock:
            cred = self._creds.get(name)
            if cred is None:
                return None
            salt, digest = cred
            if not hmac.compare_digest(_hash_password(password, salt), digest):
                return None
            token = secrets.token_hex(16)
            self._tokens[token] = name
            return token

    def citizen_for_token(self, token: str) -> str | None:
        with self._lock:
            account = self._tokens.get(token)
            return self._citizen_of.get(account) if account else None

    def citizen_is_bound(self, citizen: str) -> bool:
        """Audit C10/E4: True when this citizen has an account. Account-bound
        seats may only be acted for with their own session token."""
        with self._lock:
            return citizen in self._citizen_of.values()

    def bound_citizens(self) -> set[str]:
        """Citizens currently bound to any account. The dashboard uses this
        to re-apply seat claims after a world reset (accounts outlive
        worlds; a claimed seat stays human-driven)."""
        with self._lock:
            return set(self._citizen_of.values())

    def logout(self, token: str) -> None:
        with self._lock:
            self._tokens.pop(token, None)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._creds)
