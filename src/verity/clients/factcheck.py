"""Google Fact Check Tools API client (claims.search, v1alpha1).

Verified against the official reference in the build session:
  GET https://factchecktools.googleapis.com/v1alpha1/claims:search
  params: query, languageCode, reviewPublisherSiteFilter, maxAgeDays, pageSize,
          pageToken, offset;  response: {claims: [Claim], nextPageToken}
  Claim{text, claimant, claimDate, claimReview[]};
  ClaimReview{publisher{name, site}, url, title, reviewDate, textualRating, languageCode}
  Auth: API key, sent in the ``x-goog-api-key`` header (not in the URL).
"""

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import BaseModel, ConfigDict, ValidationError

from verity.clients.http import request_with_retry
from verity.config import Settings, get_settings
from verity.errors import ExternalServiceError
from verity.schemas import RedactedText

BASE_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


class _Ext(BaseModel):
    # External payloads may gain fields; ignore unknown ones but validate the rest.
    model_config = ConfigDict(extra="ignore")


class Publisher(_Ext):
    name: str | None = None
    site: str | None = None


class ClaimReview(_Ext):
    publisher: Publisher | None = None
    url: str | None = None
    title: str | None = None
    reviewDate: str | None = None
    textualRating: str | None = None
    languageCode: str | None = None


class Claim(_Ext):
    text: str | None = None
    claimant: str | None = None
    claimDate: str | None = None
    claimReview: list[ClaimReview] = []


class ClaimSearchPage(_Ext):
    claims: list[Claim] = []
    nextPageToken: str | None = None


class FactCheckClient:
    def __init__(
        self,
        api_key: str,
        *,
        settings: Settings | None = None,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise ExternalServiceError("FACTCHECK_API_KEY is not set", code="factcheck_no_key")
        self._key = api_key
        self._s = settings or get_settings()
        self._http = http or httpx.Client(timeout=self._s.http_timeout_s)
        self._sleep = sleep

    def search(
        self,
        query: RedactedText,
        language_code: str | None = None,
        page_token: str | None = None,
    ) -> ClaimSearchPage:
        params: dict[str, str | int] = {
            "query": str(query),
            "pageSize": self._s.factcheck_page_size,
        }
        if language_code:
            params["languageCode"] = language_code
        if page_token:
            params["pageToken"] = page_token
        resp = request_with_retry(
            self._http,
            "GET",
            BASE_URL,
            max_retries=self._s.http_max_retries,
            backoff_s=self._s.http_backoff_s,
            sleep=self._sleep,
            params=params,
            headers={"x-goog-api-key": self._key},
            service="factcheck",
        )
        try:
            return ClaimSearchPage.model_validate_json(resp.content)
        except ValidationError as exc:
            raise ExternalServiceError(
                "fact-check API returned an unexpected response shape", code="factcheck_bad_shape"
            ) from exc

    def search_all(self, query: RedactedText, language_code: str | None = None) -> list[Claim]:
        """Follow pagination up to ``factcheck_max_pages`` pages."""
        claims: list[Claim] = []
        token: str | None = None
        for _ in range(self._s.factcheck_max_pages):
            page = self.search(query, language_code, token)
            claims.extend(page.claims)
            token = page.nextPageToken or None
            if token is None:
                break
        return claims


STATUS_FILE = "ingest_status.json"


def write_ingest_status(ok: bool, detail: str = "", directory: Path | None = None) -> None:
    """Record whether the last fact-check ingestion worked (read by /health)."""
    base = directory or get_settings().index_dir
    base.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {"ok": ok, "detail": detail, "at": stamp}
    (base / STATUS_FILE).write_text(json.dumps(payload) + "\n", encoding="utf-8")


def read_ingest_status(directory: Path | None = None) -> bool | None:
    """True/False for the last ingestion result, None if it never ran."""
    path = (directory or get_settings().index_dir) / STATUS_FILE
    if not path.exists():
        return None
    return bool(json.loads(path.read_text(encoding="utf-8")).get("ok"))
