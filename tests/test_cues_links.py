from verity.cues.links import levenshtein, lookalike_flags
from verity.cues.source import source_cred
from verity.schemas import ClaimRecord

# SYNTHETIC FIXTURE: 7-entry trusted list and 13 hand-made test domains (TRD section 12).
TRUSTED = [
    "pib.gov.in",
    "who.int",
    "thehindu.com",
    "reuters.com",
    "bbc.com",
    "indianexpress.com",
    "ndtv.com",
]


def _flags(domain: str) -> list:  # type: ignore[type-arg]
    claim = ClaimRecord(text="t", entities=[], numbers=[], links=[f"https://{domain}/x"])
    return lookalike_flags(claim, None, TRUSTED)


def test_levenshtein() -> None:
    assert levenshtein("kitten", "sitting") == 3
    assert levenshtein("", "abc") == 3 and levenshtein("same", "same") == 0


def test_reference_run() -> None:
    flagged = ["pib-gov.in", "wh0.int", "thehindu.co", "thehlndu.com", "reuters.corn"]
    clean = [
        "bbc.com",
        "news.bbc.com",
        "indianexpress.com",
        "who.int",
        "wikipedia.org",
        "example.org",
    ]
    rows: list[tuple[str, str]] = []
    true_flags = false_flags = 0
    for d in flagged:
        f = _flags(d)
        rows.append((d, f"{f[0].kind} of {f[0].lookalike_of} d={f[0].distance}" if f else "-"))
        true_flags += bool(f and f[0].kind == "lookalike")
    for d in clean:
        f = _flags(d)
        rows.append((d, "FLAGGED" if f else "ok"))
        false_flags += bool(f)
    short = _flags("bit.ly")
    assert short and short[0].kind == "shortener" and short[0].lookalike_of is None
    for r in rows:
        print(*r)
    assert (true_flags, false_flags) == (5, 0)


def test_ndtv_in_is_a_documented_known_limitation() -> None:
    # ndtv.in is 3 edits from ndtv.com: beyond the distance-2 rule, so it is NOT flagged.
    assert _flags("ndtv.in") == []


def test_source_cred_low_for_lookalike_unchanged_for_trusted() -> None:
    def cred(domain: str) -> str:
        claim = ClaimRecord(text="t", entities=[], numbers=[], links=[f"https://{domain}"])
        flags = lookalike_flags(claim, None, TRUSTED)
        return source_cred(claim, None, flags, lambda d: "trusted" if d in TRUSTED else None)

    assert cred("thehlndu.com") == "low"
    assert cred("bbc.com") == "trusted"
    assert cred("bit.ly") == "unknown"
