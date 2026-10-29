"""Build and persist the two TF-IDF indexes (fact-checks and headlines) under INDEX_DIR."""

import hashlib
import json
import sqlite3
from pathlib import Path

from verity import db
from verity.config import get_settings
from verity.retrieval.index import TfidfIndex

FACTCHECK_INDEX = "factchecks.idx"
HEADLINE_INDEX = "headlines.idx"
INDEX_META = "index_meta.json"


def index_version(conn: sqlite3.Connection) -> str:
    """SHA-256 over the sorted (url, claim_text) of fact-checks and (url, title) of headlines."""
    h = hashlib.sha256()
    for url, text in sorted((r.url, r.claim_text) for r in db.list_factchecks(conn)):
        h.update(f"F\x1f{url}\x1f{text}\x1e".encode())
    for url, title in sorted((r.url, r.title) for r in db.list_headlines(conn)):
        h.update(f"H\x1f{url}\x1f{title}\x1e".encode())
    return h.hexdigest()


def build_indexes(conn: sqlite3.Connection, index_dir: Path | None = None) -> tuple[int, int]:
    """Rebuild both indexes deterministically from the database. Returns (n_fc, n_headlines)."""
    out = index_dir or get_settings().index_dir
    fc = TfidfIndex.build([(r.id, r.claim_text) for r in db.list_factchecks(conn)])
    hl = TfidfIndex.build([(r.id, r.title) for r in db.list_headlines(conn)])
    fc.save(out / FACTCHECK_INDEX)
    hl.save(out / HEADLINE_INDEX)
    meta = {"index_version": index_version(conn), "factchecks": len(fc), "headlines": len(hl)}
    (out / INDEX_META).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return len(fc), len(hl)


def main() -> int:
    with db.session() as conn:
        db.init_db(conn)
        n_fc, n_hl = build_indexes(conn)
    print(f"built indexes: {n_fc} fact-checks, {n_hl} headlines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
