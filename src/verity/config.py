"""All tunables and settings (build spec B.1). No magic numbers elsewhere."""

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from verity.errors import DataError

_PROVIDERS = ("indictrans2", "hosted", "none")


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    # External services
    factcheck_api_key: str = ""
    translation_provider: str = "none"
    translation_base: str = ""
    translation_api_key: str = ""

    # Storage
    db_path: Path = Path("./data/verity.db")
    index_dir: Path = Path("./data/index")

    # Tunables (initial values; tuned in T5.4 / T8.3, then frozen)
    verdict_threshold: float = Field(0.75, gt=0.5, le=1.0)
    retrieval_top_k: int = Field(5, ge=1)
    factcheck_match_threshold: float = Field(0.30, ge=0.0, le=1.0)
    headline_match_threshold: float = Field(0.30, ge=0.0, le=1.0)
    tone_threshold: float = Field(0.50, ge=0.0, le=1.0)
    max_message_chars: int = Field(5000, ge=1)
    random_seed: int = 42
    likelihood_weighting_samples: int = Field(5000, ge=1)
    simhash_max_hamming: int = Field(14, ge=0, le=64)
    lookalike_max_edit: int = Field(2, ge=0)
    lookalike_min_len: int = Field(6, ge=1)
    radar_min_count: int = Field(3, ge=1)
    radar_window_hours: int = Field(24, ge=1)

    # Services
    api_base: str = "http://localhost:8000"
    ui_port: int = 8501

    # Derived knobs that the spec leaves to config rather than code
    claim_max_chars: int = Field(300, ge=20)  # fallback claim truncation (T2.2)
    reply_max_chars: int = Field(400, ge=40)  # reply-card length limit (T6.3)
    cpt_equivalent_sample_size: int = Field(10, ge=1)  # pseudo-count weight (T5.2)
    radar_limit: int = Field(10, ge=1)  # default Radar list size
    max_keywords: int = Field(5, ge=1)  # keywords stored per family (D2)

    # External HTTP behaviour (clients)
    http_timeout_s: float = Field(10.0, gt=0)
    http_max_retries: int = Field(3, ge=0)
    http_backoff_s: float = Field(0.5, ge=0)
    factcheck_page_size: int = Field(20, ge=1)
    factcheck_max_pages: int = Field(3, ge=1)


def _clean(value: str) -> str:
    """Drop an inline ``# comment`` (as written in .env.example) and surrounding space."""
    return value.split("#", 1)[0].strip()


_ENV_MAP: dict[str, str] = {
    "FACTCHECK_API_KEY": "factcheck_api_key",
    "TRANSLATION_PROVIDER": "translation_provider",
    "TRANSLATION_BASE": "translation_base",
    "TRANSLATION_API_KEY": "translation_api_key",
    "DB_PATH": "db_path",
    "INDEX_DIR": "index_dir",
    "VERDICT_THRESHOLD": "verdict_threshold",
    "RETRIEVAL_TOP_K": "retrieval_top_k",
    "FACTCHECK_MATCH_THRESHOLD": "factcheck_match_threshold",
    "HEADLINE_MATCH_THRESHOLD": "headline_match_threshold",
    "TONE_THRESHOLD": "tone_threshold",
    "MAX_MESSAGE_CHARS": "max_message_chars",
    "RANDOM_SEED": "random_seed",
    "LIKELIHOOD_WEIGHTING_SAMPLES": "likelihood_weighting_samples",
    "SIMHASH_MAX_HAMMING": "simhash_max_hamming",
    "LOOKALIKE_MAX_EDIT": "lookalike_max_edit",
    "LOOKALIKE_MIN_LEN": "lookalike_min_len",
    "RADAR_MIN_COUNT": "radar_min_count",
    "RADAR_WINDOW_HOURS": "radar_window_hours",
    "HTTP_TIMEOUT_S": "http_timeout_s",
    "HTTP_MAX_RETRIES": "http_max_retries",
    "HTTP_BACKOFF_S": "http_backoff_s",
    "API_BASE": "api_base",
    "UI_PORT": "ui_port",
}


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build validated settings from the environment (or the mapping given)."""
    source = os.environ if env is None else env
    values: dict[str, str] = {}
    for env_name, field in _ENV_MAP.items():
        raw = source.get(env_name)
        if raw is not None and _clean(raw) != "":
            values[field] = _clean(raw)
    try:
        settings = Settings.model_validate(values)
    except ValidationError as exc:
        raise DataError(f"invalid configuration: {exc}", code="invalid_config") from exc
    if settings.translation_provider not in _PROVIDERS:
        raise DataError(f"TRANSLATION_PROVIDER must be one of {_PROVIDERS}", code="invalid_config")
    return settings


def get_settings() -> Settings:
    """Settings from the process environment (cheap; re-read so tests can override)."""
    return load_settings()
