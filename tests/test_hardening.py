from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from scripts.ingest_factchecks import main as ingest_main

from verity import db
from verity.api.app import create_app
from verity.clients.factcheck import read_ingest_status
from verity.pipeline import Pipeline, set_pipeline
from verity.retrieval import Retriever, set_default_retriever
from verity.schemas import CheckRequest

# SYNTHETIC FIXTURE


@pytest.fixture()
def bare_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "v.db"))
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "ix"))
    set_default_retriever(None)
    set_pipeline(None)
    return tmp_path


def test_missing_index_degrades_to_none_and_warns(bare_env: Path) -> None:
    rec = Pipeline().check(CheckRequest(text="Hot lemon water cures diabetes, share now"))
    assert rec.evidence.fact_check == "none" and rec.evidence.corroboration == "no"
    assert rec.verdict in ("unverified", "likely_false", "likely_true") and rec.reply_card
    client = TestClient(create_app(Pipeline()))
    h = client.get("/health")
    assert h.status_code == 200
    warnings = h.headers["X-Verity-Warnings"]
    assert "empty-index" in warnings and "cpt-priors-only" in warnings


def test_empty_retriever_loads_without_files(bare_env: Path) -> None:
    conn = db.connect(bare_env / "v.db")
    db.init_db(conn)
    assert Retriever.load(conn, bare_env / "nowhere").is_empty()


def test_api_outage_keeps_cache_and_flags_health(
    bare_env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("FACTCHECK_API_KEY", "k")
    queries = bare_env / "q.txt"
    queries.write_text("some query\n")
    with db.session() as conn:
        db.init_db(conn)
        db.add_factcheck(conn, "cached claim", "refuted", "P", "http://f/1")

    def down(self: httpx.Client, *a: object, **k: object) -> httpx.Response:
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(httpx.Client, "request", down)
    monkeypatch.setenv("HTTP_MAX_RETRIES", "0")
    (bare_env / "m.json").write_text("{}")
    assert ingest_main(["--queries", str(queries), "--rating-map", str(bare_env / "m.json")]) == 1
    assert "keeping the local cache (1 fact-checks)" in capsys.readouterr().err
    assert read_ingest_status() is False
    monkeypatch.undo()
    monkeypatch.setenv("DB_PATH", str(bare_env / "v.db"))
    monkeypatch.setenv("INDEX_DIR", str(bare_env / "ix"))
    h = TestClient(create_app(Pipeline())).get("/health")
    assert "factcheck-cache-only" in h.headers["X-Verity-Warnings"]
    assert h.json()["factchecks"] == 1


def test_unexpected_error_is_structured_and_does_not_leak(
    bare_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pipeline = Pipeline()

    def boom(request: CheckRequest, now: object = None) -> object:
        raise RuntimeError("SECRET-FRAGMENT-OF-MESSAGE")

    monkeypatch.setattr(pipeline, "check", boom)
    client = TestClient(create_app(pipeline), raise_server_exceptions=False)
    r = client.post("/check", json={"text": "hello world friends"})
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal_error"
    assert "SECRET" not in r.text
