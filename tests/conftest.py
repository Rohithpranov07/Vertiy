from pathlib import Path

import pytest

from verity import db
from verity.cues.tone import reset_model_cache
from verity.pipeline import Pipeline, set_pipeline
from verity.retrieval import Retriever, set_default_retriever
from verity.retrieval.build import build_indexes

# SYNTHETIC FIXTURE: made-up fact-check, headline and domain data used by pipeline/API tests.
DEBUNKED = "drinking hot lemon water every morning cures diabetes completely in two weeks"
HEADLINE = "Government announces recharge scheme for students across the country"


@pytest.fixture()
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Pipeline:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "verity.db"))
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "index"))
    reset_model_cache()
    conn = db.connect(tmp_path / "verity.db")
    db.init_db(conn)
    db.add_factcheck(conn, DEBUNKED, "refuted", "Synthetic Checker", "http://f.example/lemon")
    db.add_headline(conn, HEADLINE, "news.example", "http://news.example/a")
    db.add_domain(conn, "news.example", "trusted")
    db.add_domain(conn, "scam.example", "low")
    from scripts.seed_rumour_families import seed_families

    seed_families(conn)
    build_indexes(conn, tmp_path / "index")
    conn.commit()
    retriever = Retriever.load(conn, tmp_path / "index")
    conn.close()
    set_default_retriever(retriever)
    pipeline = Pipeline(retriever=retriever)
    set_pipeline(pipeline)
    yield pipeline
    set_pipeline(None)
    set_default_retriever(None)
