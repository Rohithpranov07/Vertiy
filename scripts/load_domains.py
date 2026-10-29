"""Load data/domains.csv (domain,class,rationale) into the domains table.

Only classes `trusted` and `low` are accepted. The list is human-approved.
"""

import argparse
import csv
import sqlite3
from pathlib import Path
from typing import Literal, cast

from verity import db
from verity.errors import DataError

DATA = Path(__file__).resolve().parents[1] / "data"
CLASSES = ("trusted", "low")


def normalise(domain: str) -> str:
    d = domain.strip().lower()
    return d[4:] if d.startswith("www.") else d


def load_domains(conn: sqlite3.Connection, path: Path) -> int:
    """Returns the number of NEW rows added. Rejects unknown classes before writing anything."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None or [f.strip() for f in reader.fieldnames][:2] != [
            "domain",
            "class",
        ]:
            raise DataError("domains.csv header must start with domain,class", code="bad_domains")
        rows = list(reader)
    parsed: list[tuple[str, Literal["trusted", "low"]]] = []
    for i, row in enumerate(rows, start=2):
        domain, cls = normalise(row["domain"] or ""), (row["class"] or "").strip().lower()
        if not domain:
            raise DataError(f"line {i}: empty domain", code="bad_domains")
        if cls not in CLASSES:
            raise DataError(f"line {i}: class {cls!r} must be trusted or low", code="bad_domains")
        parsed.append((domain, cast(Literal["trusted", "low"], cls)))
    return sum(1 for domain, cls in parsed if db.add_domain(conn, domain, cls))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=DATA / "domains.csv")
    args = ap.parse_args(argv)
    with db.session() as conn:
        db.init_db(conn)
        added = load_domains(conn, args.csv)
        print(f"domains: {added} new, {db.count_domains(conn)} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
