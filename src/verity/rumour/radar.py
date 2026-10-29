"""Rumour Radar (D5): which Unverified rumour families are surging. Triage, never truth.

Read-only: it never changes a verdict or writes anything. It exposes keywords and a
linked fact-check URL only; no message text exists to show.
"""

import sqlite3
from datetime import UTC, datetime, timedelta

from verity import db
from verity.config import get_settings
from verity.schemas import RadarItem


def _bucket(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H")


def top(
    conn: sqlite3.Connection,
    window_hours: int | None = None,
    limit: int | None = None,
    now: datetime | None = None,
) -> list[RadarItem]:
    s = get_settings()
    window = window_hours or s.radar_window_hours
    cap = limit or s.radar_limit
    current = (now or datetime.now(UTC)).astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    # hour buckets are UTC; "last window" includes the current hour
    recent_start = _bucket(current - timedelta(hours=window - 1))
    previous_start = _bucket(current - timedelta(hours=2 * window - 1))
    end = _bucket(current + timedelta(hours=1))

    items: list[RadarItem] = []
    for fam in db.list_families(conn):
        if fam.last_verdict != "unverified":
            continue
        if db.count_hits(conn, fam.family_id) < s.radar_min_count:
            continue
        recent = db.count_hits(conn, fam.family_id, recent_start, end)
        previous = db.count_hits(conn, fam.family_id, previous_start, recent_start)
        linked = (
            db.get_factcheck(conn, fam.linked_factcheck_id)
            if fam.linked_factcheck_id is not None
            else None
        )
        items.append(
            RadarItem(
                family_id=fam.family_id,
                keywords=fam.keywords,
                recent=recent,
                previous=previous,
                surge=(recent + 1) / (previous + 1),
                linked_url=linked.url if linked else None,
            )
        )
    items.sort(key=lambda i: (-i.surge, -i.recent, i.family_id))
    return items[:cap]
