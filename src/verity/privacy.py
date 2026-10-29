"""Privacy helpers. ``redact()`` (D1) is added in T2.0."""

import hashlib

from verity.schemas import RedactedText


def message_hash(text: RedactedText) -> str:
    """Hex SHA-256 of the whitespace-normalised, lower-cased redacted text."""
    normalised = " ".join(text.split()).lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
