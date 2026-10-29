"""Evidence passport (D4): versions + a deterministic id, so a verdict is reproducible."""

import hashlib
import json
from collections.abc import Collection
from datetime import UTC, datetime
from pathlib import Path

from verity.bn.version import cpt_version
from verity.config import get_settings
from verity.retrieval.build import INDEX_META
from verity.schemas import Passport, VerdictRecord

NO_INDEX = "no-index"


def read_index_version(index_dir: Path | None = None) -> str:
    path = (index_dir or get_settings().index_dir) / INDEX_META
    if not path.exists():
        return NO_INDEX
    return str(json.loads(path.read_text(encoding="utf-8"))["index_version"])


def passport_id(message_hash: str, index_version: str, cpt_ver: str, threshold: float) -> str:
    """First 16 hex chars of SHA-256 over message_hash|index_version|cpt_version|threshold.
    created_at is deliberately NOT part of the id."""
    raw = f"{message_hash}|{index_version}|{cpt_ver}|{threshold}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_passport(
    message_hash: str,
    threshold: float,
    index_dir: Path | None = None,
    cpt_path: Path | None = None,
    now: datetime | None = None,
) -> Passport:
    index_ver = read_index_version(index_dir)
    cpt_ver = cpt_version(cpt_path)
    stamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return Passport(
        passport_id=passport_id(message_hash, index_ver, cpt_ver, threshold),
        index_version=index_ver,
        cpt_version=cpt_ver,
        threshold=threshold,
        created_at=stamp,
    )


def ungrounded_urls(record: VerdictRecord, known_urls: Collection[str]) -> list[str]:
    """URLs in a verdict record that are not in the fact-check/headline index."""
    urls = [m.url for m in record.matches]
    return [u for u in urls if u not in known_urls]
