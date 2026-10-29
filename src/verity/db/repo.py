"""All SQLite access. Standard-library sqlite3, parameterised queries only."""

import json
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import Literal, ParamSpec, TypeVar, cast

from verity.config import get_settings
from verity.db.models import (
    DomainRow,
    FactCheckRow,
    FeedbackRow,
    HeadlineRow,
    HealthCounts,
    RumourRow,
)
from verity.errors import DataError
from verity.schemas import Language, Rating, UserLabel, VerdictLabel

P = ParamSpec("P")
R = TypeVar("R")

_SCHEMA = Path(__file__).with_name("schema.sql")
_FP_MASK = (1 << 64) - 1


def _wrap(fn: Callable[P, R]) -> Callable[P, R]:
    """Convert driver errors into DataError."""

    @wraps(fn)
    def inner(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except sqlite3.Error as exc:
            raise DataError(f"database error in {fn.__name__}: {exc}", code="db_error") from exc

    return inner


@_wrap
def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else get_settings().db_path
    if str(path) != ":memory:":
        path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def session(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection, commit on success, roll back on error, always close."""
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


@_wrap
def init_db(conn: sqlite3.Connection) -> None:
    """Create all tables. Idempotent."""
    conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
    conn.commit()


# ----- factchecks -----
@_wrap
def add_factcheck(
    conn: sqlite3.Connection,
    claim_text: str,
    rating: Rating,
    publisher: str,
    url: str,
    date: str | None = None,
    lang: str | None = None,
) -> bool:
    """Insert a fact-check; returns False if (url, claim_text) already exists."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO factchecks (claim_text, rating, publisher, url, date, lang) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (claim_text, rating, publisher, url, date, lang),
    )
    return cur.rowcount == 1


def _factcheck(r: sqlite3.Row) -> FactCheckRow:
    return FactCheckRow.model_validate(dict(r))


@_wrap
def list_factchecks(conn: sqlite3.Connection) -> list[FactCheckRow]:
    return [_factcheck(r) for r in conn.execute("SELECT * FROM factchecks ORDER BY id")]


@_wrap
def get_factcheck(conn: sqlite3.Connection, factcheck_id: int) -> FactCheckRow | None:
    r = conn.execute("SELECT * FROM factchecks WHERE id = ?", (factcheck_id,)).fetchone()
    return _factcheck(r) if r is not None else None


@_wrap
def count_factchecks(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM factchecks").fetchone()[0])


# ----- headlines -----
@_wrap
def add_headline(
    conn: sqlite3.Connection, title: str, domain: str, url: str, date: str | None = None
) -> bool:
    """Insert a headline; returns False if the url already exists."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO headlines (title, domain, url, date) VALUES (?, ?, ?, ?)",
        (title, domain, url, date),
    )
    return cur.rowcount == 1


@_wrap
def list_headlines(conn: sqlite3.Connection) -> list[HeadlineRow]:
    return [
        HeadlineRow.model_validate(dict(r))
        for r in conn.execute("SELECT * FROM headlines ORDER BY id")
    ]


@_wrap
def get_headline(conn: sqlite3.Connection, headline_id: int) -> HeadlineRow | None:
    r = conn.execute("SELECT * FROM headlines WHERE id = ?", (headline_id,)).fetchone()
    return HeadlineRow.model_validate(dict(r)) if r is not None else None


@_wrap
def count_headlines(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM headlines").fetchone()[0])


# ----- domains -----
@_wrap
def add_domain(conn: sqlite3.Connection, domain: str, cls: Literal["trusted", "low"]) -> bool:
    """Insert or update a domain's class; returns True if a new row was created."""
    exists = conn.execute("SELECT 1 FROM domains WHERE domain = ?", (domain,)).fetchone()
    conn.execute(
        "INSERT INTO domains (domain, class) VALUES (?, ?) "
        "ON CONFLICT(domain) DO UPDATE SET class = excluded.class",
        (domain, cls),
    )
    return exists is None


@_wrap
def list_domains(conn: sqlite3.Connection) -> list[DomainRow]:
    return [
        DomainRow(domain=r["domain"], cls=r["class"])
        for r in conn.execute("SELECT domain, class FROM domains ORDER BY domain")
    ]


@_wrap
def get_domain(conn: sqlite3.Connection, domain: str) -> DomainRow | None:
    r = conn.execute("SELECT domain, class FROM domains WHERE domain = ?", (domain,)).fetchone()
    return DomainRow(domain=r["domain"], cls=r["class"]) if r is not None else None


@_wrap
def count_domains(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM domains").fetchone()[0])


# ----- feedback -----
@_wrap
def add_feedback(
    conn: sqlite3.Connection,
    message_hash: str,
    verdict: VerdictLabel,
    user_label: UserLabel,
    timestamp: str,
) -> int:
    cur = conn.execute(
        "INSERT INTO feedback (message_hash, verdict, user_label, timestamp) VALUES (?, ?, ?, ?)",
        (message_hash, verdict, user_label, timestamp),
    )
    return int(cur.lastrowid or 0)


@_wrap
def list_feedback(conn: sqlite3.Connection) -> list[FeedbackRow]:
    return [
        FeedbackRow.model_validate(dict(r))
        for r in conn.execute("SELECT * FROM feedback ORDER BY id")
    ]


# ----- rumours (D2) -----
def _rumour(r: sqlite3.Row) -> RumourRow:
    return RumourRow(
        family_id=r["family_id"],
        fingerprint=int(r["fingerprint"], 16),
        keywords=cast(list[str], json.loads(r["keywords"])),
        language=cast(Language, r["language"]),
        linked_factcheck_id=r["linked_factcheck_id"],
        first_seen=r["first_seen"],
        last_seen=r["last_seen"],
        last_verdict=cast(VerdictLabel | None, r["last_verdict"]),
    )


@_wrap
def add_family(
    conn: sqlite3.Connection,
    family_id: str,
    fingerprint: int,
    keywords: list[str],
    language: Language,
    linked_factcheck_id: int | None,
    seen_at: str,
    last_verdict: VerdictLabel | None = None,
) -> bool:
    """Insert a family; returns False if family_id already exists."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO rumours (family_id, fingerprint, keywords, language, "
        "linked_factcheck_id, first_seen, last_seen, last_verdict) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            family_id,
            f"{fingerprint & _FP_MASK:016x}",
            json.dumps(keywords),
            language,
            linked_factcheck_id,
            seen_at,
            seen_at,
            last_verdict,
        ),
    )
    return cur.rowcount == 1


@_wrap
def get_family(conn: sqlite3.Connection, family_id: str) -> RumourRow | None:
    r = conn.execute("SELECT * FROM rumours WHERE family_id = ?", (family_id,)).fetchone()
    return _rumour(r) if r is not None else None


@_wrap
def get_family_by_factcheck(conn: sqlite3.Connection, factcheck_id: int) -> RumourRow | None:
    r = conn.execute(
        "SELECT * FROM rumours WHERE linked_factcheck_id = ? ORDER BY family_id LIMIT 1",
        (factcheck_id,),
    ).fetchone()
    return _rumour(r) if r is not None else None


@_wrap
def list_fingerprints(conn: sqlite3.Connection) -> list[tuple[str, int]]:
    """(family_id, fingerprint) for every family, ordered by family_id."""
    return [
        (r["family_id"], int(r["fingerprint"], 16))
        for r in conn.execute("SELECT family_id, fingerprint FROM rumours ORDER BY family_id")
    ]


@_wrap
def list_families(conn: sqlite3.Connection) -> list[RumourRow]:
    return [_rumour(r) for r in conn.execute("SELECT * FROM rumours ORDER BY family_id")]


@_wrap
def update_family(
    conn: sqlite3.Connection,
    family_id: str,
    last_seen: str,
    last_verdict: VerdictLabel,
    keywords: list[str] | None = None,
) -> None:
    if keywords is None:
        conn.execute(
            "UPDATE rumours SET last_seen = ?, last_verdict = ? WHERE family_id = ?",
            (last_seen, last_verdict, family_id),
        )
    else:
        conn.execute(
            "UPDATE rumours SET last_seen = ?, last_verdict = ?, keywords = ? WHERE family_id = ?",
            (last_seen, last_verdict, json.dumps(keywords), family_id),
        )


# ----- rumour_hits (D5) -----
@_wrap
def add_hit(conn: sqlite3.Connection, family_id: str, hour: str, message_hash: str) -> bool:
    """Record one check; a duplicate (family_id, hour, message_hash) is ignored."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO rumour_hits (family_id, hour, message_hash) VALUES (?, ?, ?)",
        (family_id, hour, message_hash),
    )
    return cur.rowcount == 1


@_wrap
def count_hits(
    conn: sqlite3.Connection,
    family_id: str,
    start_hour: str | None = None,
    end_hour: str | None = None,
) -> int:
    """Hits with start_hour <= hour < end_hour (either bound optional)."""
    sql = "SELECT COUNT(*) FROM rumour_hits WHERE family_id = ?"
    args: list[str] = [family_id]
    if start_hour is not None:
        sql += " AND hour >= ?"
        args.append(start_hour)
    if end_hour is not None:
        sql += " AND hour < ?"
        args.append(end_hour)
    return int(conn.execute(sql, args).fetchone()[0])


# ----- health -----
@_wrap
def health_counts(conn: sqlite3.Connection) -> HealthCounts:
    """Table sizes; last_refresh is the newest fact-check/headline date stored, else None."""
    newest = conn.execute(
        "SELECT MAX(d) FROM (SELECT MAX(date) AS d FROM factchecks "
        "UNION ALL SELECT MAX(date) FROM headlines)"
    ).fetchone()[0]
    return HealthCounts(
        factchecks=count_factchecks(conn),
        headlines=count_headlines(conn),
        domains=count_domains(conn),
        last_refresh=newest,
    )
