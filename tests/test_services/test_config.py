import pytest
from pydantic import ValidationError

from app.config import Settings


_VALID_BASE = dict(
    POSTGRES_USER="u",
    POSTGRES_PASSWORD="p",
    POSTGRES_DB="d",
)


def test_settings_rejects_insecure_jwt_in_production():
    with pytest.raises(ValidationError, match="insecure placeholder"):
        Settings(
            DEBUG=False,
            JWT_SECRET="test-secret-" + "x" * 32,
            **_VALID_BASE,
        )


def test_settings_rejects_low_entropy_jwt_in_production():
    with pytest.raises(ValidationError, match="low entropy"):
        Settings(
            DEBUG=False,
            JWT_SECRET="a" * 64,
            **_VALID_BASE,
        )


def test_settings_allows_insecure_jwt_when_debug():
    settings = Settings(
        DEBUG=True,
        JWT_SECRET="test-secret-" + "x" * 32,
        **_VALID_BASE,
    )
    assert settings.DEBUG is True


def test_settings_accepts_strong_jwt_in_production():
    settings = Settings(
        DEBUG=False,
        JWT_SECRET="kJ9#mP2$nQ8&rT4!wY7@xZ1%vB6^cF3*hL5+gN0=dM",
        **_VALID_BASE,
    )
    assert settings.DEBUG is False
