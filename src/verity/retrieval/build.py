"""Build and persist the two TF-IDF indexes (fact-checks and headlines) under INDEX_DIR."""

import sqlite3
from pathlib import Path

from verity import db
from verity.config import get_settings
from verity.retrieval.index import TfidfIndex

FACTCHECK_INDEX = "factchecks.idx"
HEADLINE_INDEX = "headlines.idx"


def build_indexes(conn: sqlite3.Connection, index_dir: Path | None = None) -> tuple[int, int]:
    """Rebuild both indexes deterministically from the database. Returns (n_fc, n_headlines)."""
    out = index_dir or get_settings().index_dir
    fc = TfidfIndex.build([(r.id, r.claim_text) for r in db.list_factchecks(conn)])
    hl = TfidfIndex.build([(r.id, r.title) for r in db.list_headlines(conn)])
    fc.save(out / FACTCHECK_INDEX)
    hl.save(out / HEADLINE_INDEX)
    return len(fc), len(hl)


def main() -> int:
    with db.session() as conn:
        db.init_db(conn)
        n_fc, n_hl = build_indexes(conn)
    print(f"built indexes: {n_fc} fact-checks, {n_hl} headlines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
