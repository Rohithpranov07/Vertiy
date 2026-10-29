"""Seed one rumour family per cached fact-check (with linked_factcheck_id). Idempotent."""

import sqlite3
import sys

from verity import db
from verity.privacy import as_redacted, redact
from verity.rumour import extract_keywords, fingerprint
from verity.rumour.family import family_id_for
from verity.schemas import Language

LANGS: set[str] = {"en", "ta", "hi"}


def _language(code: str | None) -> Language:
    base = (code or "en").split("-")[0].lower()
    return base if base in LANGS else "en"  # type: ignore[return-value]


def seed_families(conn: sqlite3.Connection) -> tuple[int, int]:
    """Returns (new_families, total_factchecks)."""
    rows = db.list_factchecks(conn)
    added = 0
    for row in rows:
        safe = as_redacted(redact(row.claim_text))
        fp = fingerprint(safe)
        if db.add_family(
            conn,
            family_id_for(fp),
            fp,
            extract_keywords(safe),
            _language(row.lang),
            row.id,
            row.date or "1970-01-01T00:00:00Z",
        ):
            added += 1
    return added, len(rows)


def main() -> int:
    with db.session() as conn:
        db.init_db(conn)
        added, total = seed_families(conn)
        print(f"families: {added} new from {total} fact-checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
