"""Privacy shield (D1) and message hashing.

``redact()`` replaces listed identifier types with tags before anything is hashed,
stored, fingerprinted, translated or sent out. LIMIT: names and addresses are NOT
removed, so this is redaction, not anonymisation.
"""

import hashlib
import re
from functools import lru_cache
from pathlib import Path

from verity.schemas import RedactedText, RedactionResult, RedactionType

_SUFFIX_FILE = Path(__file__).resolve().parents[2] / "data" / "upi_suffixes.txt"

_CARD = re.compile(r"(?<!\d)\d{4}(?:[ -]?\d{4}){3}(?!\d)")
_ID12 = re.compile(r"(?<!\d)\d{4}(?:[ -]?\d{4}){2}(?!\d)")
_EMAIL = re.compile(
    r"(?<![\w.%+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)
_PHONE = re.compile(r"(?<![\d\w])(?:\+91[ -]?)?[6-9](?:[ -]?\d){9}(?!\d)")

_TAGS: dict[RedactionType, str] = {
    "CARD": "[CARD]",
    "ID12": "[ID12]",
    "UPI": "[UPI]",
    "EMAIL": "[EMAIL]",
    "PHONE": "[PHONE]",
}


@lru_cache(maxsize=1)
def _upi_pattern() -> re.Pattern[str]:
    suffixes = [
        line.strip().lower()
        for line in _SUFFIX_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    alternation = "|".join(re.escape(s) for s in sorted(suffixes, key=len, reverse=True))
    return re.compile(rf"(?<![\w.%+-])[\w.\-]{{2,}}@(?:{alternation})(?![\w-])", re.IGNORECASE)


def redact(text: str) -> RedactionResult:
    """Redact CARD, ID12, UPI, EMAIL, PHONE (in that order). Pure and idempotent."""
    patterns: list[tuple[RedactionType, re.Pattern[str]]] = [
        ("CARD", _CARD),
        ("ID12", _ID12),
        ("UPI", _upi_pattern()),
        ("EMAIL", _EMAIL),
        ("PHONE", _PHONE),
    ]
    counts: dict[RedactionType, int] = {}
    for kind, pattern in patterns:
        text, n = pattern.subn(_TAGS[kind], text)
        if n:
            counts[kind] = n
    return RedactionResult(text=text, counts=counts)


def as_redacted(result: RedactionResult) -> RedactedText:
    """The ONLY place a RedactedText is created from raw input (via redact())."""
    return RedactedText(result.text)


def message_hash(text: RedactedText) -> str:
    """Hex SHA-256 of the whitespace-normalised, lower-cased redacted text."""
    normalised = " ".join(text.split()).lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
