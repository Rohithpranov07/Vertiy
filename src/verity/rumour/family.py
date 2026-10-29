"""Rumour families (D2): matching by Hamming distance and recording hits. Never stores text."""

import re
import sqlite3
from collections import Counter
from datetime import UTC, datetime

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from verity import db
from verity.config import get_settings
from verity.rumour.fingerprint import hamming, normalise
from verity.schemas import FamilyInfo, Language, RedactedText, VerdictLabel

_TAG = re.compile(r"\[[A-Z0-9]+\]")
_MIN_KEYWORD_LEN = 3
_MAX_DIGITS_IN_TOKEN = 5  # tokens with six or more digits could be identifiers


def extract_keywords(text: RedactedText) -> list[str]:
    """Up to MAX_KEYWORDS non-stop-word tokens, excluding tags and long digit strings.

    LIMIT: names are not removed by the privacy shield, so a name may appear here.
    """
    cleaned = _TAG.sub(" ", str(text))
    tokens = [
        t
        for t in normalise(cleaned).split()
        if len(t) >= _MIN_KEYWORD_LEN
        and t not in ENGLISH_STOP_WORDS
        and sum(c.isdigit() for c in t) <= _MAX_DIGITS_IN_TOKEN
    ]
    counts = Counter(tokens)
    first = {t: i for i, t in reversed(list(enumerate(tokens)))}
    ranked = sorted(counts, key=lambda t: (-counts[t], -len(t), first[t]))
    return ranked[: get_settings().max_keywords]


def family_id_for(fp: int) -> str:
    return f"fam-{fp:016x}"


def _now(now: datetime | None) -> datetime:
    return (now or datetime.now(UTC)).astimezone(UTC)


def hour_bucket(now: datetime | None = None) -> str:
    return _now(now).strftime("%Y-%m-%dT%H")


def _iso(now: datetime | None) -> str:
    return _now(now).strftime("%Y-%m-%dT%H:%M:%SZ")


def _linked_rating(conn: sqlite3.Connection, factcheck_id: int | None) -> str | None:
    if factcheck_id is None:
        return None
    row = db.get_factcheck(conn, factcheck_id)
    return row.rating if row is not None else None


def match_family(conn: sqlite3.Connection, fp: int) -> FamilyInfo | None:
    """Closest stored family within SIMHASH_MAX_HAMMING (ties: lowest family_id).

    Linear scan over all fingerprints: fine for v1 volumes; an index (e.g. bit-sampling
    LSH) would be needed for very large family counts.
    """
    best: tuple[int, str] | None = None
    for family_id, stored in db.list_fingerprints(conn):
        d = hamming(fp, stored)
        if d <= get_settings().simhash_max_hamming and (best is None or (d, family_id) < best):
            best = (d, family_id)
    if best is None:
        return None
    fam = db.get_family(conn, best[1])
    rating = _linked_rating(conn, fam.linked_factcheck_id) if fam is not None else None
    return FamilyInfo(
        family_id=best[1],
        hamming=best[0],
        linked_rating=rating,  # type: ignore[arg-type]
        source="existing",
    )


def record_hit(
    conn: sqlite3.Connection,
    family: FamilyInfo | None,
    fp: int,
    message_hash: str,
    verdict: VerdictLabel,
    keywords: list[str],
    language: Language,
    now: datetime | None = None,
) -> FamilyInfo:
    """Create the family (if none matched) or update it, and add this check to the hour bucket."""
    stamp = _iso(now)
    if family is None:
        fid = family_id_for(fp)
        db.add_family(
            conn, fid, fp, keywords[: get_settings().max_keywords], language, None, stamp, verdict
        )
        info = FamilyInfo(family_id=fid, hamming=None, linked_rating=None, source="new")
    else:
        db.update_family(conn, family.family_id, stamp, verdict)
        info = family
    db.add_hit(conn, info.family_id, hour_bucket(now), message_hash)
    return info
