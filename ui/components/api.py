"""HTTP client for the VERITY API. The UI computes nothing; it only calls these."""

import os

import httpx
from pydantic import ValidationError

from verity.schemas import (
    Ack,
    CheckRequest,
    FeedbackRequest,
    HealthResponse,
    RadarItem,
    UserLabel,
    VerdictLabel,
    VerdictRecord,
)

TIMEOUT_S = 30.0  # first request loads models; later ones are far faster


class ApiError(Exception):
    def __init__(self, message: str, code: str = "api_error") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def api_base() -> str:
    return os.environ.get("API_BASE", "http://localhost:8000").rstrip("/")


def _call(method: str, path: str, **kwargs: object) -> httpx.Response:
    try:
        resp = httpx.request(method, api_base() + path, timeout=TIMEOUT_S, **kwargs)  # type: ignore[arg-type]
    except httpx.HTTPError as exc:
        raise ApiError(
            f"Could not reach the VERITY service at {api_base()} ({type(exc).__name__}). "
            "Is it running (make api)?",
            "unreachable",
        ) from exc
    if resp.status_code >= 400:
        try:
            err = resp.json()["error"]
            raise ApiError(str(err["message"]), str(err["code"]))
        except (ValueError, KeyError, TypeError) as exc:
            raise ApiError(f"The service returned HTTP {resp.status_code}.", "http_error") from exc
    return resp


def post_check(text: str, url: str | None) -> VerdictRecord:
    req = CheckRequest(text=text, url=url or None)
    resp = _call("POST", "/check", json=req.model_dump())
    try:
        return VerdictRecord.model_validate_json(resp.content)
    except ValidationError as exc:
        raise ApiError("The service returned an unexpected response.", "bad_response") from exc


def post_feedback(message_hash: str, verdict: VerdictLabel, user_label: UserLabel) -> bool:
    req = FeedbackRequest(message_hash=message_hash, verdict=verdict, user_label=user_label)
    return Ack.model_validate_json(_call("POST", "/feedback", json=req.model_dump()).content).ok


def get_health() -> HealthResponse:
    return HealthResponse.model_validate_json(_call("GET", "/health").content)


def get_radar(window_hours: int | None = None, limit: int | None = None) -> list[RadarItem]:
    params: dict[str, int] = {}
    if window_hours is not None:
        params["window_hours"] = window_hours
    if limit is not None:
        params["limit"] = limit
    resp = _call("GET", "/radar", params=params)
    return [RadarItem.model_validate(item) for item in resp.json()]
