"""Ingest trusted-outlet headlines from data/feeds.txt into `headlines`.

Only feeds whose domain is `trusted` in `domains` are accepted; items whose own link
is not on a trusted domain are skipped. Idempotent; one failing feed never aborts the run.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from verity import db
from verity.clients.feeds import FeedClient, domain_of
from verity.errors import VerityError
from verity.privacy import as_redacted, redact

DATA = Path(__file__).resolve().parents[1] / "data"


def is_trusted(conn: sqlite3.Connection, domain: str) -> bool:
    """True if the domain or any parent domain is listed as trusted."""
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        row = db.get_domain(conn, ".".join(parts[i:]))
        if row is not None:
            return row.cls == "trusted"
    return False


def read_feeds(path: Path) -> list[str]:
    return [
        ln.strip()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]


def ingest_feeds(conn: sqlite3.Connection, client: FeedClient, urls: list[str]) -> dict[str, str]:
    """Returns {feed_url: outcome} where outcome is 'added=N skipped=M' or an error."""
    report: dict[str, str] = {}
    for url in urls:
        fdomain = domain_of(url)
        if not is_trusted(conn, fdomain):
            report[url] = f"REFUSED: {fdomain or 'unknown'} is not a trusted domain"
            continue
        try:
            items = client.fetch(as_redacted(redact(url)))
        except VerityError as exc:
            report[url] = f"ERROR: {exc.code}"
            continue
        added = skipped = 0
        for item in items:
            idomain = domain_of(item.url)
            if not is_trusted(conn, idomain):
                skipped += 1
            elif db.add_headline(conn, item.title, idomain, item.url, item.date):
                added += 1
        report[url] = f"added={added} skipped={skipped} items={len(items)}"
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--feeds", type=Path, default=DATA / "feeds.txt")
    args = ap.parse_args(argv)
    urls = read_feeds(args.feeds)
    if not urls:
        print(f"no feeds in {args.feeds}", file=sys.stderr)
        return 1
    with db.session() as conn:
        db.init_db(conn)
        for url, outcome in ingest_feeds(conn, FeedClient(), urls).items():
            print(f"{url}: {outcome}")
        print(f"headlines total: {db.count_headlines(conn)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
