"""Lookalike-link guard (D3). Pure Python; never visits, resolves or fetches a link."""

from collections.abc import Collection
from functools import lru_cache
from pathlib import Path

from verity.config import get_settings
from verity.cues.source import normalise_domain
from verity.schemas import ClaimRecord, LookalikeFlag

_SHORTENERS = Path(__file__).resolve().parents[3] / "data" / "shorteners.txt"

_CHAR_MAP = str.maketrans({"0": "o", "1": "l", "5": "s"})


@lru_cache(maxsize=1)
def shorteners() -> frozenset[str]:
    return frozenset(
        ln.strip().lower()
        for ln in _SHORTENERS.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.startswith("#")
    )


def levenshtein(a: str, b: str) -> int:
    """Classic edit distance (insert, delete, substitute), pure Python."""
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _is_or_under(domain: str, parent: str) -> bool:
    return domain == parent or domain.endswith("." + parent)


def _confusable(domain: str) -> str:
    """Replace 0->o, 1->l, 5->s, rn->m, vv->w and drop hyphens."""
    return domain.translate(_CHAR_MAP).replace("rn", "m").replace("vv", "w").replace("-", "")


def lookalike_flags(
    claim: ClaimRecord, url: str | None, trusted: Collection[str]
) -> list[LookalikeFlag]:
    s = get_settings()
    trusted_domains = sorted({normalise_domain(t) for t in trusted})
    links = list(claim.links) + ([url] if url else [])
    seen: set[str] = set()
    flags: list[LookalikeFlag] = []
    for link in links:
        domain = normalise_domain(link)
        if not domain or domain in seen:
            continue
        seen.add(domain)
        if any(_is_or_under(domain, t) for t in trusted_domains):
            continue
        if domain in shorteners():
            flags.append(
                LookalikeFlag(domain=domain, lookalike_of=None, distance=None, kind="shortener")
            )
            continue
        folded = _confusable(domain)
        best: tuple[int, str] | None = None
        for t in trusted_domains:
            by_chars = folded == t
            by_edit = len(t) >= s.lookalike_min_len and (
                levenshtein(domain, t) <= s.lookalike_max_edit
            )
            if by_chars or by_edit:
                cand = (levenshtein(domain, t), t)
                if best is None or cand < best:
                    best = cand
        if best is not None:
            flags.append(
                LookalikeFlag(
                    domain=domain, lookalike_of=best[1], distance=best[0], kind="lookalike"
                )
            )
    return flags
