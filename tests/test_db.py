import sqlite3
from pathlib import Path

import pytest

from verity import db
from verity.errors import DataError

# SYNTHETIC FIXTURE: every value below is made up for tests.


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    return c


def test_init_idempotent(conn: sqlite3.Connection) -> None:
    db.init_db(conn)
    db.init_db(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"factchecks", "headlines", "domains", "feedback", "rumours", "rumour_hits"} <= tables


def test_factchecks_roundtrip_and_dedupe(conn: sqlite3.Connection) -> None:
    assert db.add_factcheck(conn, "claim a", "refuted", "pub", "http://x/1", "2026-01-01", "en")
    assert not db.add_factcheck(conn, "claim a", "refuted", "pub", "http://x/1")
    rows = db.list_factchecks(conn)
    assert len(rows) == 1 and rows[0].rating == "refuted"
    assert db.get_factcheck(conn, rows[0].id) == rows[0]
    assert db.get_factcheck(conn, 999) is None
    assert db.count_factchecks(conn) == 1


def test_headlines_dedupe_on_url(conn: sqlite3.Connection) -> None:
    assert db.add_headline(conn, "t1", "news.example", "http://n/1", "2026-02-01")
    assert not db.add_headline(conn, "other title", "news.example", "http://n/1")
    assert db.count_headlines(conn) == 1 and db.list_headlines(conn)[0].title == "t1"


def test_domains(conn: sqlite3.Connection) -> None:
    assert db.add_domain(conn, "good.example", "trusted")
    assert not db.add_domain(conn, "good.example", "low")  # update, not new
    got = db.get_domain(conn, "good.example")
    assert got is not None and got.cls == "low"
    with pytest.raises(DataError):
        db.add_domain(conn, "x", "weird")  # type: ignore[arg-type]
    assert db.count_domains(conn) == 1


def test_feedback(conn: sqlite3.Connection) -> None:
    db.add_feedback(conn, "h1", "unverified", "right", "2026-10-29T10:00:00Z")
    rows = db.list_feedback(conn)
    assert rows[0].message_hash == "h1" and rows[0].user_label == "right"


def test_rumours_and_hits(conn: sqlite3.Connection) -> None:
    fp = 0xDEADBEEFCAFEBABE
    assert db.add_family(conn, "f1", fp, ["lemon", "water"], "en", None, "2026-10-29T10:00:00Z")
    assert not db.add_family(conn, "f1", fp, [], "en", None, "x")
    fam = db.get_family(conn, "f1")
    assert fam is not None and fam.fingerprint == fp and fam.keywords == ["lemon", "water"]
    assert db.list_fingerprints(conn) == [("f1", fp)]
    db.update_family(conn, "f1", "2026-10-29T11:00:00Z", "unverified")
    assert db.list_families(conn)[0].last_verdict == "unverified"

    assert db.add_hit(conn, "f1", "2026-10-29T10", "mh")
    assert not db.add_hit(conn, "f1", "2026-10-29T10", "mh")  # duplicate ignored
    assert db.add_hit(conn, "f1", "2026-10-29T11", "mh")
    assert db.count_hits(conn, "f1") == 2
    assert db.count_hits(conn, "f1", "2026-10-29T11", "2026-10-29T12") == 1
    assert conn.execute("SELECT COUNT(*) FROM rumour_hits").fetchone()[0] == 2


def test_no_column_can_hold_message_text(conn: sqlite3.Connection) -> None:
    banned = {"text", "message", "body", "content", "raw", "original"}
    for table in ("feedback", "rumours", "rumour_hits"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        print(table, cols)
        assert not banned & set(cols)


def test_health_counts(conn: sqlite3.Connection) -> None:
    assert db.health_counts(conn).last_refresh is None
    db.add_factcheck(conn, "c", "supported", "p", "u", "2026-03-01")
    db.add_headline(conn, "t", "d", "u2", "2026-04-01")
    h = db.health_counts(conn)
    assert (h.factchecks, h.headlines, h.domains, h.last_refresh) == (1, 1, 0, "2026-04-01")


def test_driver_errors_wrapped(tmp_path: Path) -> None:
    c = db.connect(tmp_path / "e.db")  # no init: table missing
    with pytest.raises(DataError):
        db.count_factchecks(c)
