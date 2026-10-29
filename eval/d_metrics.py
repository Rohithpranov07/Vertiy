"""Differentiator metrics (D1-D5). Inputs are small CSV files; starters are SYNTHETIC."""

import csv
import json
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from verity import db
from verity.config import get_settings
from verity.cues.links import lookalike_flags
from verity.privacy import as_redacted, redact
from verity.rumour import fingerprint, hamming, radar
from verity.schemas import CheckRequest, ClaimRecord, VerdictRecord

EVAL_DIR = Path(__file__).resolve().parent
BANNED_COLUMNS = {"text", "message", "body", "content", "raw", "original"}


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def d2_variants(path: Path | None = None) -> dict[str, object]:
    """Variant recall (variants within SIMHASH_MAX_HAMMING of their base) and false matches
    (unrelated messages within the threshold of ANY base)."""
    rows = _rows(path or EVAL_DIR / "variants" / "starter.csv")
    th = get_settings().simhash_max_hamming

    def fp(text: str) -> int:
        return fingerprint(as_redacted(redact(text)))

    bases = {r["group_id"]: fp(r["text"]) for r in rows if r["kind"] == "base"}
    variants = [r for r in rows if r["kind"] == "variant"]
    unrelated = [r for r in rows if r["kind"] == "unrelated"]
    recalled = sum(hamming(bases[r["group_id"]], fp(r["text"])) <= th for r in variants)
    false = sum(any(hamming(b, fp(r["text"])) <= th for b in bases.values()) for r in unrelated)
    return {
        "threshold": th,
        "variants": len(variants),
        "variants_in_family": recalled,
        "variant_recall": recalled / len(variants) if variants else None,
        "unrelated": len(unrelated),
        "false_family_matches": false,
    }


def d3_lookalikes(
    test_path: Path | None = None, trusted_path: Path | None = None
) -> dict[str, object]:
    trusted = [r["domain"] for r in _rows(trusted_path or EVAL_DIR / "domains_trusted.csv")]
    tp = fp_ = fn = 0
    misses: list[str] = []
    false_flags: list[str] = []
    for r in _rows(test_path or EVAL_DIR / "domains_test.csv"):
        claim = ClaimRecord(text="", entities=[], numbers=[], links=[f"https://{r['domain']}/"])
        flags = lookalike_flags(claim, None, trusted)
        flagged = any(f.kind == "lookalike" for f in flags)
        expected = r["expected"] == "lookalike"
        if flagged and expected:
            tp += 1
        elif flagged and not expected:
            fp_ += 1
            false_flags.append(r["domain"])
        elif expected:
            fn += 1
            misses.append(r["domain"])
    return {
        "true_flags": tp,
        "false_flags": fp_,
        "misses": fn,
        "precision": tp / (tp + fp_) if tp + fp_ else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "missed_domains": misses,
        "false_flag_domains": false_flags,
    }


def d1_redaction(path: Path | None = None) -> dict[str, object]:
    types = ["PHONE", "EMAIL", "UPI", "CARD", "ID12"]
    expected_total = removed_total = 0
    clean_total = clean_unchanged = 0
    failures: list[str] = []
    for r in _rows(path or EVAL_DIR / "redaction_test.csv"):
        want = {t: int(r[t]) for t in types}
        result = redact(r["text"])
        if sum(want.values()) == 0:
            clean_total += 1
            if result.text == r["text"] and not result.counts:
                clean_unchanged += 1
            else:
                failures.append(r["text"][:40])
            continue
        expected_total += sum(want.values())
        removed_total += sum(min(result.counts.get(t, 0), want[t]) for t in types)  # type: ignore[call-overload]
    return {
        "identifiers_expected": expected_total,
        "identifiers_removed": removed_total,
        "recall": removed_total / expected_total if expected_total else None,
        "clean_strings": clean_total,
        "clean_unchanged": clean_unchanged,
        "clean_failures": failures,
    }


def d4_reproducibility(
    check: Callable[[CheckRequest, datetime | None], VerdictRecord], texts: list[str]
) -> dict[str, object]:
    """Run each text twice with the same clock; records must match except created_at and the
    rumour-family block (the second check legitimately sees the family from the first)."""
    fixed = datetime(2026, 1, 1, tzinfo=UTC)
    identical = 0
    for text in texts:
        a = check(CheckRequest(text=text), fixed).model_dump(exclude={"family"})
        b = check(CheckRequest(text=text), fixed).model_dump(exclude={"family"})
        identical += json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    return {"messages": len(texts), "identical_records": identical}


def d5_radar_privacy(conn: sqlite3.Connection) -> dict[str, object]:
    min_count = get_settings().radar_min_count
    shown = radar.top(conn, limit=1000)
    below = [i.family_id for i in shown if db.count_hits(conn, i.family_id) < min_count]
    columns = {
        table: [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        for table in ("rumours", "rumour_hits", "feedback")
    }
    text_columns = {t: sorted(BANNED_COLUMNS & set(cols)) for t, cols in columns.items()}
    return {
        "families_shown": len(shown),
        "shown_below_min_count": below,
        "tables_with_text_columns": {t: c for t, c in text_columns.items() if c},
    }
