"""Source-credibility cue: domain lookup in the curated list (no link -> unknown)."""

import sqlite3
from collections.abc import Callable
from urllib.parse import urlparse

from verity import db
from verity.schemas import ClaimRecord, LookalikeFlag, SourceCredState

# domain -> 'trusted' | 'low' | None (not listed)
DomainLookup = Callable[[str], str | None]


def normalise_domain(link: str) -> str:
    """Host of a link (scheme optional), lower-cased, without a leading www."""
    raw = link.strip()
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    host = (parsed.hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def db_lookup(conn: sqlite3.Connection) -> DomainLookup:
    def lookup(domain: str) -> str | None:
        row = db.get_domain(conn, domain)
        return row.cls if row is not None else None

    return lookup


def classify_domain(domain: str, lookup: DomainLookup) -> str | None:
    """Class of the domain or of its nearest listed parent domain."""
    parts = domain.split(".")
    for i in range(max(len(parts) - 1, 1)):
        found = lookup(".".join(parts[i:]))
        if found is not None:
            return found
    return None


def source_cred(
    claim: ClaimRecord,
    url: str | None,
    flags: list[LookalikeFlag],
    lookup: DomainLookup,
) -> SourceCredState:
    """A lookalike link forces low. Otherwise: any low -> low; any trusted -> trusted;
    else unknown. A shortener hides its target, so it contributes unknown."""
    if any(f.kind == "lookalike" for f in flags):
        return "low"
    hidden = {f.domain for f in flags if f.kind == "shortener"}
    links = list(claim.links) + ([url] if url else [])
    classes = {
        classify_domain(d, lookup)
        for d in (normalise_domain(link) for link in links)
        if d and d not in hidden
    }
    if "low" in classes:
        return "low"
    if "trusted" in classes:
        return "trusted"
    return "unknown"
