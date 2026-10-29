"""The shipped demo domain list is well-formed and consistent with the feed list."""

import csv
from pathlib import Path

from scripts.ingest_headlines import read_feeds
from scripts.load_domains import CLASSES, normalise

from verity.clients.feeds import domain_of

DATA = Path(__file__).resolve().parents[1] / "data"


def _trusted() -> set[str]:
    with (DATA / "domains.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows and all(r["class"] in CLASSES for r in rows)
    assert len({normalise(r["domain"]) for r in rows}) == len(rows)  # no duplicates
    return {normalise(r["domain"]) for r in rows if r["class"] == "trusted"}


def test_domains_csv_is_valid_and_rated_by_a_human_reviewable_rationale() -> None:
    with (DATA / "domains.csv").open(newline="", encoding="utf-8") as fh:
        assert all(r["rationale"].strip() for r in csv.DictReader(fh))


def test_every_feed_domain_is_trusted() -> None:
    trusted = _trusted()
    for url in read_feeds(DATA / "feeds.txt"):
        host = domain_of(url)
        assert any(host == d or host.endswith("." + d) for d in trusted), url
