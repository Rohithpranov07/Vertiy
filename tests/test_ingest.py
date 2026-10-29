import json
from pathlib import Path

import httpx
import pytest
from scripts.ingest_factchecks import ingest_claims, ingest_offline, load_rating_map
from scripts.load_domains import load_domains

from verity import db
from verity.clients.factcheck import FactCheckClient
from verity.config import load_settings
from verity.errors import DataError, ExternalServiceError
from verity.schemas import RedactedText

# SYNTHETIC FIXTURE: made-up API payloads; no real fact-checks.
PAGE1 = {
    "claims": [
        {
            "text": "synthetic claim one",
            "claimReview": [
                {
                    "publisher": {"name": "Pub A", "site": "a.example"},
                    "url": "http://a.example/1",
                    "reviewDate": "2026-01-01T00:00:00Z",
                    "textualRating": "False",
                    "languageCode": "en",
                },
                {
                    "publisher": {"site": "b.example"},
                    "url": "http://b.example/2",
                    "textualRating": "Half Pants",
                },
            ],
        }
    ],
    "nextPageToken": "tok2",
}
PAGE2 = {"claims": [], "extraField": 1}


def _client(handler: httpx.MockTransport, sleeps: list[float] | None = None) -> FactCheckClient:
    return FactCheckClient(
        "KEY",
        settings=load_settings({"HTTP_BACKOFF_S": "0"}),
        http=httpx.Client(transport=handler),
        sleep=(sleeps.append if sleeps is not None else lambda _s: None),
    )


def test_search_all_paginates_and_sends_key_in_header() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json=PAGE2 if "pageToken" in req.url.params else PAGE1)

    claims = _client(httpx.MockTransport(handler)).search_all(RedactedText("lemon"))
    assert len(claims) == 1 and len(seen) == 2
    assert seen[0].headers["x-goog-api-key"] == "KEY"
    assert "KEY" not in str(seen[0].url)
    assert seen[1].url.params["pageToken"] == "tok2"


def test_retry_then_error_without_leaking_key() -> None:
    calls: list[int] = []
    sleeps: list[float] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(503)

    with pytest.raises(ExternalServiceError) as ei:
        _client(httpx.MockTransport(handler), sleeps).search(RedactedText("q"))
    assert len(calls) == 4 and "KEY" not in str(ei.value)


def test_bad_shape_and_4xx() -> None:
    bad = httpx.MockTransport(lambda r: httpx.Response(200, json={"claims": "nope"}))
    with pytest.raises(ExternalServiceError) as ei:
        _client(bad).search(RedactedText("q"))
    assert ei.value.code == "factcheck_bad_shape"
    forbidden = httpx.MockTransport(lambda r: httpx.Response(403))
    with pytest.raises(ExternalServiceError):
        _client(forbidden).search(RedactedText("q"))


def test_ingest_maps_dedupes_and_reports_unmapped(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    page = _client(httpx.MockTransport(lambda r: httpx.Response(200, json=PAGE1))).search(
        RedactedText("q")
    )
    rmap = {"false": "refuted"}
    a, s, unmapped = ingest_claims(conn, page.claims, rmap)  # type: ignore[arg-type]
    assert (a, s, unmapped) == (1, 1, {"Half Pants"})
    assert ingest_claims(conn, page.claims, rmap)[0] == 0  # type: ignore[arg-type]
    assert db.count_factchecks(conn) == 1


def test_offline_seed_and_rating_map_validation(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    seed = tmp_path / "seed.jsonl"
    seed.write_text(
        json.dumps({"claim_text": "c", "rating": "refuted", "publisher": "p", "url": "http://u/1"})
        + "\n"
    )
    assert ingest_offline(conn, seed) == (1, 1)
    assert ingest_offline(conn, seed) == (0, 1)
    bad = tmp_path / "map.json"
    bad.write_text('{"x": "maybe"}')
    with pytest.raises(DataError):
        load_rating_map(bad)


def test_load_domains_rejects_bad_class(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    good = tmp_path / "d.csv"
    good.write_text("domain,class,rationale\nWWW.Good.example,trusted,x\nbad.example,low,y\n")
    assert load_domains(conn, good) == 2 and load_domains(conn, good) == 0
    assert db.get_domain(conn, "good.example") is not None
    bad = tmp_path / "b.csv"
    bad.write_text("domain,class,rationale\nx.example,great,z\n")
    with pytest.raises(DataError):
        load_domains(conn, bad)
    assert db.get_domain(conn, "x.example") is None


def test_prefix_rules_resolve_free_text_ratings() -> None:
    from scripts.ingest_factchecks import resolve_rating

    rules = {
        "false": "refuted",
        "false.*": "refuted",
        "mostly true": "supported",
        "true.*": "supported",
    }
    assert resolve_rating("False", rules) == "refuted"  # type: ignore[arg-type]
    assert resolve_rating("False. The video is old.", rules) == "refuted"  # type: ignore[arg-type]
    assert resolve_rating("True. It is official.", rules) == "supported"  # type: ignore[arg-type]
    assert resolve_rating("Half true", rules) is None  # type: ignore[arg-type]
