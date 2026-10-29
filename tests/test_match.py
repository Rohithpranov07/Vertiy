import logging
from pathlib import Path

import pytest

from verity import db
from verity.retrieval import (
    Retriever,
    match_factchecks,
    match_headlines,
    to_corroboration,
    to_fact_check_state,
)
from verity.retrieval.build import build_indexes
from verity.schemas import ClaimRecord, HeadlineMatch, Match

# SYNTHETIC FIXTURE: made-up fact-checks and headlines.


@pytest.fixture()
def retriever(tmp_path: Path) -> Retriever:
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    db.add_factcheck(
        conn, "hot lemon water cures diabetes completely", "refuted", "P1", "http://f/1"
    )
    db.add_factcheck(conn, "government recharge scheme is genuine", "supported", "P2", "http://f/2")
    db.add_headline(
        conn, "Government announces recharge scheme for students", "news.example", "http://n/1"
    )
    build_indexes(conn, tmp_path / "ix")
    return Retriever.load(conn, tmp_path / "ix")


def _claim(text: str) -> ClaimRecord:
    return ClaimRecord(text=text, entities=[], numbers=[], links=[])


def test_no_match_gives_none_and_no(retriever: Retriever) -> None:
    c = _claim("entirely unrelated zebra paragraph")
    fc, hl = match_factchecks(c, retriever), match_headlines(c, retriever)
    assert (to_fact_check_state(fc), to_corroboration(hl)) == ("none", "no")


def test_refuted_top_match(retriever: Retriever) -> None:
    m = match_factchecks(_claim("lemon water cures diabetes"), retriever)
    assert m and m[0].rating == "refuted" and m[0].url == "http://f/1"
    assert to_fact_check_state(m) == "refuted"


def test_below_threshold_ignored(retriever: Retriever) -> None:
    # shares one word with each document: similarity ~0.23, below the 0.30 threshold
    assert match_factchecks(_claim("water government"), retriever) == []


def test_conflict_resolved_by_similarity_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    ms = [
        Match(publisher="a", rating="supported", url="u1", similarity=0.5),
        Match(publisher="b", rating="refuted", url="u2", similarity=0.8),
    ]
    with caplog.at_level(logging.INFO):
        assert to_fact_check_state(ms) == "refuted"
    assert "conflict" in caplog.text


def test_corroboration_yes(retriever: Retriever) -> None:
    hl = match_headlines(_claim("government recharge scheme for students"), retriever)
    assert hl and isinstance(hl[0], HeadlineMatch) and to_corroboration(hl) == "yes"
