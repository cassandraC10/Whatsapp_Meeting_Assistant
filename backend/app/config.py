from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv


# Load .env for local development. Hosted environments provide variables directly.
load_dotenv()


TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    environment: str
    frontend_origins: tuple[str, ...]
    auth_secret: str
    cloud_enabled: bool
    cloud_required: bool
    database_url: str | None
    gemini_api_key: str | None
    gemini_model: str
    analytics_admin_emails: tuple[str, ...]
    capture_mode: str
    max_body_mb: int
    beta_max_conversations: int | None
    beta_max_recording_minutes: int | None
    beta_max_ai_requests: int | None

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @property
    def staging(self) -> bool:
        return self.environment == "staging"

    @property
    def cloud_database_ready(self) -> bool:
        return self.cloud_enabled and bool(self.database_url)


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().casefold() in TRUE_VALUES


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


def _optional_positive_int(name: str) -> int | None:
    raw = os.getenv(name, "").strip()
    if not raw or raw in {"0", "none", "null", "off"}:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return max(1, value)


def _origins() -> tuple[str, ...]:
    raw = os.getenv("TCA_FRONTEND_URLS", "").strip()
    if raw:
        values = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    else:
        values = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:4173",
            "http://127.0.0.1:4173",
        ]
    return tuple(dict.fromkeys(values))


def _admin_emails() -> tuple[str, ...]:
    raw = os.getenv("TCA_ANALYTICS_ADMIN_EMAILS", "").strip()
    if not raw:
        # Backward compatibility with Feature 9.
        raw = os.getenv("TCA_ANALYTICS_ADMIN_EMAIL", "").strip()
    return tuple(
        dict.fromkeys(
            email.strip().casefold()
            for email in raw.split(",")
            if email.strip()
        )
    )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    environment = os.getenv("TCA_ENV", "development").strip().casefold() or "development"
    if environment not in {"development", "staging", "production"}:
        raise RuntimeError("TCA_ENV must be development, staging, or production.")

    return AppConfig(
        environment=environment,
        frontend_origins=_origins(),
        auth_secret=os.getenv("TCA_AUTH_SECRET", "").strip(),
        cloud_enabled=_bool("TCA_CLOUD_ENABLED"),
        cloud_required=_bool("TCA_CLOUD_REQUIRED"),
        database_url=os.getenv("DATABASE_URL", "").strip() or None,
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip() or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip() or "gemini-3.5-flash",
        analytics_admin_emails=_admin_emails(),
        capture_mode=os.getenv("TCA_CAPTURE_MODE", "local_server").strip().casefold() or "local_server",
        max_body_mb=_positive_int("TCA_MAX_BODY_MB", 25),
        beta_max_conversations=_optional_positive_int("TCA_BETA_MAX_CONVERSATIONS"),
        beta_max_recording_minutes=_optional_positive_int("TCA_BETA_MAX_RECORDING_MINUTES"),
        beta_max_ai_requests=_optional_positive_int("TCA_BETA_MAX_AI_REQUESTS"),
    )


def validate_startup() -> AppConfig:
    config = get_config()

    if config.production:
        if not config.auth_secret or len(config.auth_secret) < 32:
            raise RuntimeError(
                "TCA_AUTH_SECRET must be set to a random value of at least 32 characters in production."
            )

        if not config.cloud_enabled or not config.database_url:
            raise RuntimeError(
                "Production requires TCA_CLOUD_ENABLED=true and DATABASE_URL."
            )

        if not config.cloud_required:
            raise RuntimeError(
                "Production requires TCA_CLOUD_REQUIRED=true so cloud persistence failures are not silently ignored."
            )

        if not config.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required in production.")

        if not config.frontend_origins:
            raise RuntimeError("TCA_FRONTEND_URLS must contain at least one frontend origin in production.")

        if config.capture_mode not in {"local_server", "browser"}:
            raise RuntimeError("TCA_CAPTURE_MODE must be local_server or browser.")

    return config


def is_analytics_admin(email: str) -> bool:
    return email.strip().casefold() in get_config().analytics_admin_emails
