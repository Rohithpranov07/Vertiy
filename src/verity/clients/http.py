"""Shared HTTP helper: timeout, retry with exponential backoff, typed errors."""

import time
from collections.abc import Callable

import httpx

from verity.errors import ExternalServiceError

RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


def request_with_retry(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_retries: int,
    backoff_s: float,
    sleep: Callable[[float], None] = time.sleep,
    params: dict[str, str | int] | None = None,
    headers: dict[str, str] | None = None,
    json_body: dict[str, object] | None = None,
    service: str = "external",
) -> httpx.Response:
    """Send a request; retry on timeouts, connection errors, 429 and 5xx.

    Request details (URL params, headers, bodies) are never put into error messages.
    """
    last: str = "no attempt made"
    for attempt in range(max_retries + 1):
        try:
            resp = client.request(method, url, params=params, headers=headers, json=json_body)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last = f"{type(exc).__name__}"
        else:
            if resp.status_code not in RETRY_STATUS:
                if resp.status_code >= 400:
                    raise ExternalServiceError(
                        f"{service} returned HTTP {resp.status_code}", code=f"{service}_http_error"
                    )
                return resp
            last = f"HTTP {resp.status_code}"
        if attempt < max_retries:
            sleep(backoff_s * (2**attempt))
    raise ExternalServiceError(
        f"{service} failed after retries: {last}", code=f"{service}_unavailable"
    )
