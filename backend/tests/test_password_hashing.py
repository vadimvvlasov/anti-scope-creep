"""Password hashing must fit a 512 MB container (Lightsail nano) under concurrent requests."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from argon2 import PasswordHasher

import app.auth as auth
from app.auth import HASH_CONCURRENCY, hash_password, verify_password

# argon2-cffi's default profile: 64 MiB per hash. Eight at once killed the nano container.
LEGACY_HASHER = PasswordHasher(memory_cost=65536, time_cost=3, parallelism=4)


def test_new_hashes_use_the_owasp_argon2id_profile():
    assert hash_password("password123").startswith("$argon2id$v=19$m=19456,t=2,p=1$")


def test_hashes_made_with_the_old_profile_still_verify():
    legacy = LEGACY_HASHER.hash("password123")
    assert verify_password(legacy, "password123")
    assert not verify_password(legacy, "wrong-password")


def test_concurrent_hashing_is_capped(monkeypatch):
    active = 0
    peak = 0
    lock = threading.Lock()

    class SlowHasher:
        def hash(self, password: str) -> str:
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
            time.sleep(0.05)
            with lock:
                active -= 1
            return "hash"

    monkeypatch.setattr(auth, "_hasher", SlowHasher())
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(hash_password, ["p"] * 8))

    assert peak == HASH_CONCURRENCY


def test_login_upgrades_a_legacy_hash(harness):
    harness.register(email="old@example.com")
    user = harness.store.get_user_by_email("old@example.com")
    harness.store.update_password_hash(user.id, LEGACY_HASHER.hash("password123"))

    response = harness.client.post(
        "/auth/login", json={"email": "old@example.com", "password": "password123"}
    )

    assert response.status_code == 200
    upgraded = harness.store.get_user_by_email("old@example.com").password_hash
    assert upgraded.startswith("$argon2id$v=19$m=19456,t=2,p=1$")
    assert verify_password(upgraded, "password123")
