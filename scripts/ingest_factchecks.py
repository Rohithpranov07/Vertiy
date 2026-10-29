"""Ingest published fact-checks into the local cache.

Usage:
  python -m scripts.ingest_factchecks --queries data/seed_queries.txt
  python -m scripts.ingest_factchecks --offline [--seed data/seed_factchecks.jsonl]

Ratings are normalised via data/rating_map.json (raw string -> refuted|supported).
Unmapped ratings are written to data/unmapped_ratings.txt and the record is skipped.
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict

from verity import db
from verity.clients.factcheck import Claim, FactCheckClient
from verity.config import get_settings
from verity.errors import DataError
from verity.privacy import as_redacted, redact
from verity.schemas import Rating

DATA = Path(__file__).resolve().parents[1] / "data"
RATINGS = ("refuted", "supported")


def load_rating_map(path: Path) -> dict[str, Rating]:
    raw = cast(dict[str, str], json.loads(path.read_text(encoding="utf-8")))
    out: dict[str, Rating] = {}
    for key, val in raw.items():
        if val not in RATINGS:
            raise DataError(f"rating_map value {val!r} for {key!r} is not refuted|supported")
        out[key.strip().lower()] = cast(Rating, val)
    return out


def _log_unmapped(path: Path, ratings: set[str]) -> None:
    if not ratings:
        return
    existing = set(path.read_text(encoding="utf-8").splitlines()) if path.exists() else set()
    path.write_text("\n".join(sorted(existing | ratings)) + "\n", encoding="utf-8")


def ingest_claims(
    conn: sqlite3.Connection,
    claims: list[Claim],
    rating_map: dict[str, Rating],
) -> tuple[int, int, set[str]]:
    """Store mapped reviews. Returns (added, skipped_unmapped_or_invalid, unmapped_strings)."""
    added = skipped = 0
    unmapped: set[str] = set()
    for claim in claims:
        for review in claim.claimReview:
            raw = (review.textualRating or "").strip()
            rating = rating_map.get(raw.lower())
            if not claim.text or not review.url or rating is None:
                skipped += 1
                if raw and raw.lower() not in rating_map:
                    unmapped.add(raw)
                continue
            publisher = (
                (review.publisher.name or review.publisher.site) if review.publisher else None
            )
            if db.add_factcheck(
                conn,
                claim.text,
                rating,
                publisher or "unknown",
                review.url,
                review.reviewDate,
                review.languageCode,
            ):
                added += 1
    return added, skipped, unmapped


class SeedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_text: str
    rating: Literal["refuted", "supported"]
    publisher: str
    url: str
    date: str | None = None
    lang: str | None = None


def ingest_offline(conn: sqlite3.Connection, path: Path) -> tuple[int, int]:
    """Load a JSONL seed file; returns (added, total_lines)."""
    if not path.exists():
        raise DataError(f"seed file not found: {path}", code="seed_missing")
    added = total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        total += 1
        rec = SeedRecord.model_validate_json(line)
        if db.add_factcheck(
            conn, rec.claim_text, rec.rating, rec.publisher, rec.url, rec.date, rec.lang
        ):
            added += 1
    return added, total


def read_queries(path: Path) -> list[str]:
    return [
        q.strip()
        for q in path.read_text(encoding="utf-8").splitlines()
        if q.strip() and not q.startswith("#")
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--queries", type=Path, default=DATA / "seed_queries.txt")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--seed", type=Path, default=DATA / "seed_factchecks.jsonl")
    ap.add_argument("--rating-map", type=Path, default=DATA / "rating_map.json")
    ap.add_argument("--unmapped", type=Path, default=DATA / "unmapped_ratings.txt")
    ap.add_argument("--language", default=None, help="BCP-47 languageCode filter")
    args = ap.parse_args(argv)

    with db.session() as conn:
        db.init_db(conn)
        if args.offline:
            added, total = ingest_offline(conn, args.seed)
            print(f"offline: {added} new of {total} records")
            return 0

        settings = get_settings()
        client = FactCheckClient(settings.factcheck_api_key, settings=settings)
        rating_map = load_rating_map(args.rating_map)
        queries = read_queries(args.queries)
        if not queries:
            print("no queries in", args.queries, file=sys.stderr)
            return 1
        total_added = total_skipped = 0
        all_unmapped: set[str] = set()
        for q in queries:
            safe = as_redacted(redact(q))
            claims = client.search_all(safe, args.language)
            a, s, u = ingest_claims(conn, claims, rating_map)
            print(f"{q!r}: {len(claims)} claims, {a} new, {s} skipped")
            total_added += a
            total_skipped += s
            all_unmapped |= u
        _log_unmapped(args.unmapped, all_unmapped)
        print(
            f"total: {total_added} new, {total_skipped} skipped, "
            f"{len(all_unmapped)} unmapped rating strings -> {args.unmapped}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
