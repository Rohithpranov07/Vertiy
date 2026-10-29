"""Translation clients. Every function accepts ONLY RedactedText.

``hosted`` speaks the LibreTranslate-compatible API, verified against its docs:
  POST {TRANSLATION_BASE}/translate  form fields q, source, target, [format], [api_key]
  200 -> {"translatedText": str, ...};  errors -> {"error": str} with 400/403/429/500.
``indictrans2`` (local AI4Bharat model) is NOT wired up in this build; selecting it
degrades to translation_ok=False rather than guessing at its API.
"""

import time
from collections.abc import Callable
from typing import Protocol

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from verity.clients.http import request_with_retry
from verity.config import Settings, get_settings
from verity.errors import ExternalServiceError
from verity.schemas import Language, RedactedText


class Translator(Protocol):
    def translate(self, text: RedactedText, source: Language) -> str: ...


class _Response(BaseModel):
    model_config = ConfigDict(extra="ignore")
    translatedText: str


class HostedTranslator:
    def __init__(
        self,
        base: str,
        api_key: str = "",
        *,
        settings: Settings | None = None,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not base:
            raise ExternalServiceError("TRANSLATION_BASE is not set", code="translation_no_base")
        self._url = base.rstrip("/") + "/translate"
        self._key = api_key
        self._s = settings or get_settings()
        self._http = http or httpx.Client(timeout=self._s.http_timeout_s)
        self._sleep = sleep

    def translate(self, text: RedactedText, source: Language) -> str:
        form = {"q": str(text), "source": source, "target": "en", "format": "text"}
        if self._key:
            form["api_key"] = self._key
        resp = request_with_retry(
            self._http,
            "POST",
            self._url,
            max_retries=self._s.http_max_retries,
            backoff_s=self._s.http_backoff_s,
            sleep=self._sleep,
            form=form,
            service="translation",
        )
        try:
            return _Response.model_validate_json(resp.content).translatedText
        except ValidationError as exc:
            raise ExternalServiceError(
                "translation API returned an unexpected response", code="translation_bad_shape"
            ) from exc


class UnavailableTranslator:
    def __init__(self, provider: str) -> None:
        self._provider = provider

    def translate(self, text: RedactedText, source: Language) -> str:
        raise ExternalServiceError(
            f"translation provider {self._provider!r} is not available in this build",
            code="translation_provider_unavailable",
        )


def get_translator(settings: Settings | None = None) -> Translator | None:
    """None when TRANSLATION_PROVIDER=none."""
    s = settings or get_settings()
    if s.translation_provider == "none":
        return None
    if s.translation_provider == "hosted":
        return HostedTranslator(s.translation_base, s.translation_api_key, settings=s)
    return UnavailableTranslator(s.translation_provider)
