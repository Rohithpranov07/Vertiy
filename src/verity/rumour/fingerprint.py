"""64-bit SimHash of a redacted claim (D2). Deterministic; stores no text."""

import hashlib
import unicodedata

from verity.schemas import RedactedText

SHINGLE = 5
BITS = 64
_DROP_CHARS = {"️", "‍", "‌", "⃣"}  # emoji joiners / variation selectors


def normalise(text: str) -> str:
    """NFKC, lower-case, drop punctuation/symbols/emoji, collapse whitespace."""
    folded = unicodedata.normalize("NFKC", text).lower()
    kept = [
        c if not c.isspace() else " "
        for c in folded
        if c not in _DROP_CHARS and unicodedata.category(c)[0] not in ("P", "S", "C") or c.isspace()
    ]
    return " ".join("".join(kept).split())


def shingles(normalised: str) -> list[str]:
    if len(normalised) < SHINGLE:
        return [normalised]
    return [normalised[i : i + SHINGLE] for i in range(len(normalised) - SHINGLE + 1)]


def fingerprint(text: RedactedText) -> int:
    votes = [0] * BITS
    for sh in shingles(normalise(str(text))):
        h = int.from_bytes(hashlib.blake2b(sh.encode("utf-8"), digest_size=8).digest(), "big")
        for i in range(BITS):
            votes[i] += 1 if (h >> i) & 1 else -1
    return sum(1 << i for i, v in enumerate(votes) if v > 0)


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()
