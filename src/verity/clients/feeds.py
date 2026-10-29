"""Trusted-outlet RSS 2.0 / Atom feed client (httpx + stdlib XML; no extra dependency)."""

import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict

from verity.clients.http import request_with_retry
from verity.config import Settings, get_settings
from verity.errors import ExternalServiceError
from verity.schemas import RedactedText

ATOM = "{http://www.w3.org/2005/Atom}"


class FeedItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    url: str
    date: str | None


def domain_of(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _rfc822_to_iso(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value.strip()).isoformat()
    except (TypeError, ValueError):
        return value.strip()


def parse_feed(content: bytes) -> list[FeedItem]:
    """Parse RSS 2.0 or Atom. Feeds declaring a DOCTYPE/ENTITY are refused (XML bombs)."""
    head = content[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in content.upper():
        raise ExternalServiceError("feed declares a DTD/entity; refused", code="feed_unsafe")
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        raise ExternalServiceError("feed is not valid XML", code="feed_bad_xml") from exc
    items: list[FeedItem] = []
    for item in root.iter("item"):  # RSS 2.0
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if title and link:
            items.append(
                FeedItem(title=title, url=link, date=_rfc822_to_iso(item.findtext("pubDate")))
            )
    for entry in root.iter(f"{ATOM}entry"):  # Atom
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        link_el = entry.find(f"{ATOM}link")
        link = (link_el.get("href") if link_el is not None else "") or ""
        date = entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")
        if title and link:
            items.append(FeedItem(title=title, url=link.strip(), date=date))
    return items


class FeedClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._s = settings or get_settings()
        self._http = http or httpx.Client(timeout=self._s.http_timeout_s, follow_redirects=True)
        self._sleep = sleep

    def fetch(self, url: RedactedText) -> list[FeedItem]:
        resp = request_with_retry(
            self._http,
            "GET",
            str(url),
            max_retries=self._s.http_max_retries,
            backoff_s=self._s.http_backoff_s,
            sleep=self._sleep,
            service="feed",
        )
        return parse_feed(resp.content)
