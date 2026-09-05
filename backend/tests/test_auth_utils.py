"""Unit tests for the password and token helpers."""

from __future__ import annotations

import pytest

PASSWORD = "correct horse battery"


def test_password_hashing_round_trip() -> None:
    from app.utils.auth import hash_password, verify_password

    stored = hash_password(PASSWORD)
    assert stored != PASSWORD
    assert stored.startswith("$2")
    assert verify_password(PASSWORD, stored)
    assert not verify_password("another password", stored)
    # A value that is not a bcrypt hash must not raise.
    assert not verify_password(PASSWORD, "plain text")


def test_a_password_over_the_bcrypt_limit_is_refused() -> None:
    from app.utils.auth import MAX_PASSWORD_BYTES, hash_password

    with pytest.raises(ValueError):
        hash_password("x" * (MAX_PASSWORD_BYTES + 1))
