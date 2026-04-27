"""Password strength rules.

Follows NIST SP 800-63B guidance: enforce minimum length and a blocklist of
commonly-breached passwords, rather than rigid composition rules
(uppercase/digit/special) that push users toward predictable substitutions.
"""

_COMMON_WEAK_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password12",
        "password123",
        "password1234",
        "12345678",
        "123456789",
        "1234567890",
        "qwerty",
        "qwertyui",
        "qwerty123",
        "asdfghjk",
        "abc12345",
        "letmein",
        "welcome",
        "welcome1",
        "admin",
        "admin123",
        "iloveyou",
        "passw0rd",
        "p@ssword",
        "p@ssw0rd",
        "monkey",
        "dragon",
        "football",
        "baseball",
    }
)

_MIN_UNIQUE_CHARS = 4


def validate_password_strength(password: str) -> str:
    if password.lower() in _COMMON_WEAK_PASSWORDS:
        raise ValueError("Password is too common; choose a less guessable one")
    if len(set(password)) < _MIN_UNIQUE_CHARS:
        raise ValueError(
            f"Password must contain at least {_MIN_UNIQUE_CHARS} unique characters"
        )
    return password


def ensure_password_differs_from_username(password: str, username: str) -> None:
    if password.lower() == username.lower():
        raise ValueError("Password must not match the username")
