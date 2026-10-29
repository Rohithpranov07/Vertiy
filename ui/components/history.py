"""Per-session history of checks. Lives in the browser session only; nothing is written to disk.

Only the extracted (already redacted) claim sentence, the verdict and the probability are kept,
never the pasted message.
"""

from datetime import UTC, datetime

import streamlit as st

from verity.schemas import VerdictRecord

KEY = "history"
HISTORY_MAX = 50


def add(record: VerdictRecord) -> None:
    items: list[dict[str, object]] = st.session_state.setdefault(KEY, [])
    if items and items[0]["hash"] == record.message_hash:
        return  # a rerun of the same result is not a new check
    items.insert(
        0,
        {
            "hash": record.message_hash,
            "claim": record.claim.text,
            "verdict": record.verdict,
            "p_true": record.p_true,
            "matches": len(record.matches),
            "time": datetime.now(UTC).strftime("%H:%M"),
        },
    )
    del items[HISTORY_MAX:]


def items() -> list[dict[str, object]]:
    return list(st.session_state.get(KEY, []))


def clear() -> None:
    st.session_state[KEY] = []
