import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from scripts.simulate_radar import SIMULATED, populate

from verity import db
from verity.api.app import create_app
from verity.pipeline import Pipeline
from verity.rumour import radar
from verity.schemas import CheckRequest

# SYNTHETIC FIXTURE / SIMULATED counts: not measured usage.
NOW = datetime(2026, 10, 29, 12, 30, tzinfo=UTC)


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = db.connect(tmp_path / "r.db")
    db.init_db(c)
    return c


def _hit(conn: sqlite3.Connection, fid: str, hours_ago: int, h: str) -> None:
    db.add_hit(conn, fid, (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H"), h)


def _family(conn: sqlite3.Connection, fid: str, verdict: str = "unverified") -> None:
    db.add_family(conn, fid, 1, ["kw"], "en", None, "2026-10-01T00:00:00Z", verdict)  # type: ignore[arg-type]


def test_simulation_reproduces_reference_surges(conn: sqlite3.Connection) -> None:
    names = populate(conn, NOW)
    items = radar.top(conn, 24, 10, NOW)
    got = [(names[i.family_id], round(i.surge, 2)) for i in items]
    print(got)
    assert [s for _, s in got] == [13.00, 10.25, 1.12, 0.27]
    assert [n for n, _ in got] == [
        "F3 scheme money claim",
        "F1 miracle cure forward",
        "F2 recharge scam",
        "F4 old hoax",
    ]
    assert len(SIMULATED) == 4


def test_minimum_checks_two_excluded_three_included(conn: sqlite3.Connection) -> None:
    _family(conn, "f")
    _hit(conn, "f", 0, "a")
    _hit(conn, "f", 1, "b")
    assert radar.top(conn, 24, 10, NOW) == []
    _hit(conn, "f", 2, "c")
    assert [i.family_id for i in radar.top(conn, 24, 10, NOW)] == ["f"]


def test_same_hash_same_hour_counts_once(conn: sqlite3.Connection) -> None:
    _family(conn, "f")
    for _ in range(5):
        _hit(conn, "f", 0, "same")
    assert radar.top(conn, 24, 10, NOW) == []  # one distinct check only


def test_only_unverified_families_listed(conn: sqlite3.Connection) -> None:
    _family(conn, "f", "likely_false")
    for i in range(4):
        _hit(conn, "f", 0, f"h{i}")
    assert radar.top(conn, 24, 10, NOW) == []


def test_radar_is_read_only(conn: sqlite3.Connection) -> None:
    populate(conn, NOW)
    before = (
        conn.execute("SELECT * FROM rumours ORDER BY 1").fetchall(),
        conn.execute("SELECT * FROM rumour_hits ORDER BY 1,2,3").fetchall(),
    )
    radar.top(conn, 24, 10, NOW)
    after = (
        conn.execute("SELECT * FROM rumours ORDER BY 1").fetchall(),
        conn.execute("SELECT * FROM rumour_hits ORDER BY 1,2,3").fetchall(),
    )
    assert [tuple(r) for r in before[0]] == [tuple(r) for r in after[0]]
    assert [tuple(r) for r in before[1]] == [tuple(r) for r in after[1]]


def test_marker_never_in_radar_output_or_storage(world: Pipeline, tmp_path: Path) -> None:
    marker = "RADARMARK8472910365"
    for i in range(3):
        world.check(
            CheckRequest(text=f"Unusual alert {i}: {marker} the council will cancel all exams soon")
        )
    client = TestClient(create_app(world))
    resp = client.get("/radar", params={"window_hours": 24, "limit": 10})
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1 and items[0]["recent"] == 3
    assert marker not in resp.text and "will cancel all exams" not in resp.text
    print("radar output:", resp.text)
    assert marker.encode() not in (tmp_path / "verity.db").read_bytes()
    assert set(items[0]) == {"family_id", "keywords", "recent", "previous", "surge", "linked_url"}


def test_radar_does_not_change_verdicts(world: Pipeline) -> None:
    req = CheckRequest(text="The municipal office announced new parking rules for the market")
    first = world.check(req)
    client = TestClient(create_app(world))
    client.get("/radar")
    again = world.check(req)
    assert first.verdict == again.verdict and first.p_true == again.p_true


def test_radar_endpoint_validation(world: Pipeline) -> None:
    client = TestClient(create_app(world))
    assert client.get("/radar", params={"limit": 0}).status_code == 422
    assert client.get("/radar").json() == []
