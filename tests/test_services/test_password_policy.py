import pytest

from app.core.password_policy import (
    ensure_password_differs_from_username,
    validate_password_strength,
)


@pytest.mark.parametrize(
    "weak",
    ["password", "password123", "12345678", "qwerty123", "Letmein", "ADMIN123"],
)
def test_common_passwords_rejected(weak):
    with pytest.raises(ValueError, match="too common"):
        validate_password_strength(weak)


def test_low_unique_chars_rejected():
    with pytest.raises(ValueError, match="unique characters"):
        validate_password_strength("aaaaaaaa")


def test_strong_password_accepted():
    assert validate_password_strength("tr0ub4dor&3") == "tr0ub4dor&3"


def test_password_equal_to_username_rejected():
    with pytest.raises(ValueError, match="match the username"):
        ensure_password_differs_from_username("Alice123", "alice123")


def test_password_differs_from_username_ok():
    ensure_password_differs_from_username("tr0ub4dor&3", "alice")
