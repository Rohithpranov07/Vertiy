from verity.cues.source import normalise_domain, source_cred
from verity.schemas import ClaimRecord

# SYNTHETIC FIXTURE: made-up domain list.
LISTED = {"trusted.example": "trusted", "scam.example": "low"}


def lookup(domain: str) -> str | None:
    return LISTED.get(domain)


def claim(*links: str) -> ClaimRecord:
    return ClaimRecord(text="t", entities=[], numbers=[], links=list(links))


def test_normalise() -> None:
    assert normalise_domain("https://WWW.Trusted.Example/a?b=1") == "trusted.example"
    assert normalise_domain("bit.ly/abc") == "bit.ly"


def test_trusted_and_subdomain() -> None:
    assert source_cred(claim("https://trusted.example/x"), None, [], lookup) == "trusted"
    assert source_cred(claim("https://news.trusted.example/x"), None, [], lookup) == "trusted"


def test_mixed_trusted_and_low_is_low() -> None:
    c = claim("https://trusted.example/x", "http://scam.example/y")
    assert source_cred(c, None, [], lookup) == "low"


def test_unlisted_and_no_link_unknown() -> None:
    assert source_cred(claim("https://other.example"), None, [], lookup) == "unknown"
    assert source_cred(claim(), None, [], lookup) == "unknown"


def test_request_url_is_considered() -> None:
    assert source_cred(claim(), "https://scam.example/z", [], lookup) == "low"
