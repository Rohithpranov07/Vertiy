"""Insert SIMULATED Radar data (synthetic, not measured usage) and print the ranked table.

Four families with (previous 24 h, last 24 h) counts of 0/12, 3/40, 25/28 and 10/2 must
rank 13.00, 10.25, 1.12, 0.27. Uses a separate database by default, never the real one.
"""

import argparse
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from verity import db
from verity.rumour import radar
from verity.rumour.family import hour_bucket

# SIMULATED: (family name, previous 24 h, last 24 h, keywords)
SIMULATED = [
    ("F3 scheme money claim", 0, 12, ["scheme", "money", "account"]),
    ("F1 miracle cure forward", 3, 40, ["miracle", "cure", "drink"]),
    ("F2 recharge scam", 25, 28, ["recharge", "free", "offer"]),
    ("F4 old hoax", 10, 2, ["hoax", "bank", "holiday"]),
]


def populate(conn: sqlite3.Connection, now: datetime) -> dict[str, str]:
    names: dict[str, str] = {}
    for idx, (name, prev, last, kws) in enumerate(SIMULATED, start=1):
        fid = f"sim-F{idx}"
        names[fid] = name
        db.add_family(
            conn, fid, 0x1000 * idx, kws, "en", None, "2026-10-01T00:00:00Z", "unverified"
        )
        for n in range(last):  # spread over the last 24 hourly buckets (hours 0..23 ago)
            db.add_hit(
                conn, fid, hour_bucket(now - timedelta(hours=n % 24)), f"SIMULATED-{fid}-a{n}"
            )
        for n in range(prev):  # hours 24..47 ago
            db.add_hit(
                conn, fid, hour_bucket(now - timedelta(hours=24 + n % 24)), f"SIMULATED-{fid}-b{n}"
            )
    return names


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=Path("data/simulated_radar.db"))
    args = ap.parse_args(argv)
    now = datetime.now(UTC)
    with db.session(args.db) as conn:
        db.init_db(conn)
        names = populate(conn, now)
        print("SIMULATED data (not measured usage) in", args.db)
        print(f"{'rank':<5}{'family':<28}{'previous':>9}{'last 24h':>9}{'surge':>8}")
        for rank, item in enumerate(radar.top(conn, 24, 10, now), start=1):
            print(
                f"{rank:<5}{names[item.family_id]:<28}{item.previous:>9}{item.recent:>9}"
                f"{item.surge:>8.2f}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
