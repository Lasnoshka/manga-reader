from typing import List, Optional

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_INSECURE_JWT_PATTERNS = (
    "test-secret",
    "change-me",
    "changeme",
    "your-secret",
    "default",
    "example",
    "placeholder",
)


class Settings(BaseSettings):
    PROJECT_NAME: str = "Manga Reader API"
    DEBUG: bool = False

    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = Field(..., min_length=1)
    POSTGRES_PASSWORD: str = Field(..., min_length=1)
    POSTGRES_DB: str = Field(..., min_length=1)

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: str = ""
    CACHE_TTL_SECONDS: int = 300
    POPULAR_TTL_SECONDS: int = 900

    JWT_SECRET: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    DATABASE_URL: str = ""

    CORS_ORIGINS: List[str] = Field(default_factory=list)
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = Field(default_factory=lambda: ["*"])
    CORS_ALLOW_HEADERS: List[str] = Field(default_factory=lambda: ["*"])

    LOG_FORMAT: str = Field(default="json", pattern="^(json|text)$")

    MAX_REQUEST_BODY_BYTES: int = 1 * 1024 * 1024
    ALLOWED_CONTENT_TYPES: List[str] = Field(
        default_factory=lambda: [
            "application/json",
            "application/x-www-form-urlencoded",
            "multipart/form-data",
        ]
    )

    @field_validator(
        "CORS_ORIGINS",
        "CORS_ALLOW_METHODS",
        "CORS_ALLOW_HEADERS",
        "ALLOWED_CONTENT_TYPES",
        mode="before",
    )
    @classmethod
    def split_csv(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: Optional[str], info) -> str:
        if isinstance(v, str) and v:
            return v
        values = info.data
        return (
            f"postgresql+asyncpg://{values.get('POSTGRES_USER')}:"
            f"{values.get('POSTGRES_PASSWORD')}@"
            f"{values.get('POSTGRES_HOST')}:"
            f"{values.get('POSTGRES_PORT')}/"
            f"{values.get('POSTGRES_DB')}"
        )

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_url(cls, v: Optional[str], info) -> str:
        if isinstance(v, str) and v:
            return v
        values = info.data
        password = values.get("REDIS_PASSWORD")
        password_part = f":{password}@" if password else ""
        return (
            f"redis://{password_part}"
            f"{values.get('REDIS_HOST')}:"
            f"{values.get('REDIS_PORT')}/"
            f"{values.get('REDIS_DB')}"
        )

    @model_validator(mode="after")
    def _reject_insecure_secrets_in_production(self):
        if self.DEBUG:
            return self

        secret_lower = self.JWT_SECRET.lower()
        for pattern in _INSECURE_JWT_PATTERNS:
            if pattern in secret_lower:
                raise ValueError(
                    f"JWT_SECRET appears to use an insecure placeholder ({pattern!r}); "
                    "set a strong random value before running with DEBUG=False"
                )
        if len(set(self.JWT_SECRET)) < 8:
            raise ValueError(
                "JWT_SECRET has very low entropy (fewer than 8 unique characters); "
                "use a strong random value"
            )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


settings = Settings()
