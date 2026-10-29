from pathlib import Path

import httpx
import pytest
from scripts.ingest_headlines import ingest_feeds

from verity import db
from verity.clients.feeds import FeedClient, parse_feed
from verity.config import load_settings
from verity.errors import ExternalServiceError

# SYNTHETIC FIXTURE: made-up feeds on example domains.
RSS = b"""<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Headline one</title><link>https://www.news.example/a/1</link>
<pubDate>Wed, 28 Oct 2026 10:00:00 GMT</pubDate></item>
<item><title>Off-site item</title><link>https://other.example/x</link></item>
<item><title></title><link>https://news.example/empty</link></item>
</channel></rss>"""
ATOM = b"""<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom headline</title><link href="https://news.example/b/2"/>
<updated>2026-10-28T09:00:00Z</updated></entry></feed>"""
BOMB = b"""<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel/></rss>"""


def test_parse_rss_and_atom() -> None:
    rss = parse_feed(RSS)
    assert [i.title for i in rss] == ["Headline one", "Off-site item"]
    assert rss[0].date and rss[0].date.startswith("2026-10-28T10:00:00")
    atom = parse_feed(ATOM)
    assert atom[0].url == "https://news.example/b/2" and atom[0].date == "2026-10-28T09:00:00Z"


def test_unsafe_and_invalid_xml_refused() -> None:
    with pytest.raises(ExternalServiceError):
        parse_feed(BOMB)
    with pytest.raises(ExternalServiceError):
        parse_feed(b"<rss><oops>")


def test_ingest_trust_idempotence_and_isolation(tmp_path: Path) -> None:
    conn = db.connect(tmp_path / "t.db")
    db.init_db(conn)
    db.add_domain(conn, "news.example", "trusted")

    def handler(req: httpx.Request) -> httpx.Response:
        if "broken" in req.url.host:
            return httpx.Response(500)
        return httpx.Response(200, content=RSS if req.url.path == "/rss" else ATOM)

    client = FeedClient(
        settings=load_settings({"HTTP_MAX_RETRIES": "0"}),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=lambda _s: None,
    )
    urls = [
        "https://news.example/rss",
        "https://untrusted.example/rss",
        "https://sub.news.example/atom",
    ]
    rep = ingest_feeds(conn, client, urls)
    assert rep[urls[0]] == "added=1 skipped=1 items=2"
    assert rep[urls[1]].startswith("REFUSED")
    assert rep[urls[2]] == "added=1 skipped=0 items=1"
    assert db.count_headlines(conn) == 2
    again = ingest_feeds(conn, client, urls)
    assert again[urls[0]] == "added=0 skipped=1 items=2" and db.count_headlines(conn) == 2
    db.add_domain(conn, "broken.example", "trusted")
    rep2 = ingest_feeds(conn, client, ["https://broken.example/rss", urls[0]])
    assert rep2["https://broken.example/rss"].startswith("ERROR")
    assert rep2[urls[0]].startswith("added=")
