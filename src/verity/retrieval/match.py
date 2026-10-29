"""Retrieval results -> belief-network evidence (Stage 3)."""

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from verity import db
from verity.config import get_settings
from verity.errors import ModelError
from verity.retrieval.build import FACTCHECK_INDEX, HEADLINE_INDEX
from verity.retrieval.index import TfidfIndex
from verity.schemas import ClaimRecord, FactCheckState, HeadlineMatch, Match, YesNo

log = logging.getLogger(__name__)


def _load_or_empty(path: Path) -> TfidfIndex:
    """A missing index file degrades to an empty index (fact_check = none), with a warning."""
    try:
        return TfidfIndex.load(path)
    except ModelError:
        log.warning("index %s not found; retrieval returns no matches (run make setup)", path.name)
        return TfidfIndex.build([])


@dataclass
class Retriever:
    """Both indexes plus the row lookups needed to turn hits into Match records."""

    fc_index: TfidfIndex
    hl_index: TfidfIndex
    fc_rows: dict[int, db.models.FactCheckRow]
    hl_rows: dict[int, db.models.HeadlineRow]

    @classmethod
    def load(cls, conn: sqlite3.Connection, index_dir: Path | None = None) -> "Retriever":
        base = index_dir or get_settings().index_dir
        return cls(
            _load_or_empty(base / FACTCHECK_INDEX),
            _load_or_empty(base / HEADLINE_INDEX),
            {r.id: r for r in db.list_factchecks(conn)},
            {r.id: r for r in db.list_headlines(conn)},
        )

    def is_empty(self) -> bool:
        return len(self.fc_index) == 0


_default: Retriever | None = None


def set_default_retriever(retriever: Retriever | None) -> None:
    global _default
    _default = retriever


def _get(retriever: Retriever | None) -> Retriever:
    global _default
    if retriever is not None:
        return retriever
    if _default is None:
        with db.session() as conn:
            _default = Retriever.load(conn)
    return _default


def match_factchecks(claim: ClaimRecord, retriever: Retriever | None = None) -> list[Match]:
    """Top-k fact-checks with similarity >= FACTCHECK_MATCH_THRESHOLD, best first."""
    s = get_settings()
    r = _get(retriever)
    out: list[Match] = []
    for fid, sim in r.fc_index.search(claim.text, s.retrieval_top_k):
        row = r.fc_rows.get(fid)
        if row is None or sim < s.factcheck_match_threshold:
            continue
        out.append(
            Match(publisher=row.publisher, rating=row.rating, url=row.url, similarity=round(sim, 6))
        )
    return out


def match_headlines(claim: ClaimRecord, retriever: Retriever | None = None) -> list[HeadlineMatch]:
    """Top-k trusted headlines with similarity >= HEADLINE_MATCH_THRESHOLD, best first."""
    s = get_settings()
    r = _get(retriever)
    out: list[HeadlineMatch] = []
    for hid, sim in r.hl_index.search(claim.text, s.retrieval_top_k):
        row = r.hl_rows.get(hid)
        if row is None or sim < s.headline_match_threshold:
            continue
        out.append(
            HeadlineMatch(title=row.title, domain=row.domain, url=row.url, similarity=round(sim, 6))
        )
    return out


def to_fact_check_state(matches: list[Match]) -> FactCheckState:
    """The highest-similarity match decides; a disagreement among the top two is logged."""
    if not matches:
        return "none"
    ranked = sorted(matches, key=lambda m: -m.similarity)
    if len(ranked) > 1 and ranked[0].rating != ranked[1].rating:
        log.info(
            "fact-check conflict: %s (%.3f) vs %s (%.3f); higher similarity decides",
            ranked[0].rating,
            ranked[0].similarity,
            ranked[1].rating,
            ranked[1].similarity,
        )
    return ranked[0].rating


def to_corroboration(headlines: list[HeadlineMatch]) -> YesNo:
    return "yes" if headlines else "no"
