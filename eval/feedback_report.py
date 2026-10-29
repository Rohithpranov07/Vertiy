"""Suggest (never apply) threshold changes from the "was this right?" feedback.

  python -m eval.feedback_report

Reads the `feedback` table and prints wrong-vs-right rates by verdict and a suggested
VERDICT_THRESHOLD range for a human to review. Nothing is written or changed.
"""

import math
import sys
from collections import Counter

from verity import db
from verity.config import get_settings
from verity.schemas import VerdictLabel

MIN_FEEDBACK = 10  # fewer taps than this per verdict gives no suggestion
TOLERABLE_WRONG = 0.10  # confident verdicts judged wrong above this suggest a higher threshold
STEP = 0.05
MAX_THRESHOLD = 0.95
VERDICTS: list[VerdictLabel] = ["likely_false", "unverified", "likely_true"]


def summarise(rows: list[tuple[str, str]]) -> dict[str, tuple[int, int]]:
    """{verdict: (right, wrong)} from (verdict, user_label) pairs."""
    counts: Counter[tuple[str, str]] = Counter(rows)
    return {v: (counts[(v, "right")], counts[(v, "wrong")]) for v in VERDICTS}


def suggest(summary: dict[str, tuple[int, int]], current: float) -> tuple[float, float] | None:
    """A (low, high) threshold range, or None if no change is suggested/supportable."""
    worst = 0.0
    for verdict in ("likely_false", "likely_true"):
        right, wrong = summary[verdict]
        if right + wrong >= MIN_FEEDBACK:
            worst = max(worst, wrong / (right + wrong))
    if worst <= TOLERABLE_WRONG:
        return None
    steps = math.ceil((worst - TOLERABLE_WRONG) / TOLERABLE_WRONG)
    high = min(MAX_THRESHOLD, round(current + STEP * steps, 2))
    low = min(high, round(current + STEP, 2))
    return (low, high) if high > current else None


def report(rows: list[tuple[str, str]], current: float) -> str:
    summary = summarise(rows)
    lines = [f"Feedback taps: {len(rows)}   current VERDICT_THRESHOLD: {current}", ""]
    lines.append(f"{'verdict':<14}{'right':>6}{'wrong':>6}{'wrong rate':>12}")
    for v in VERDICTS:
        right, wrong = summary[v]
        n = right + wrong
        rate = f"{wrong / n:10.1%}" if n else "       n/a"
        note = "" if n >= MIN_FEEDBACK else "  (too few taps for a suggestion)"
        lines.append(f"{v:<14}{right:>6}{wrong:>6}{rate:>12}{note}")
    suggestion = suggest(summary, current)
    lines.append("")
    if suggestion is None:
        lines.append("Suggestion: no change supported by this feedback.")
    else:
        lines.append(
            f"Suggestion for human review: consider VERDICT_THRESHOLD in "
            f"[{suggestion[0]}, {suggestion[1]}] (confident verdicts are judged wrong too often)."
        )
    lines.append("This is a suggestion only; nothing was changed. Re-check on the dev split first.")
    return "\n".join(lines)


def main() -> int:
    with db.session() as conn:
        db.init_db(conn)
        rows: list[tuple[str, str]] = [(r.verdict, r.user_label) for r in db.list_feedback(conn)]
    print(report(rows, get_settings().verdict_threshold))
    return 0


if __name__ == "__main__":
    sys.exit(main())
