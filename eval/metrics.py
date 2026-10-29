"""Pure metric functions. Every number in the report comes from these, computed in the run."""

import math

from sklearn.metrics import f1_score

TRUTH_TO_VERDICT = {"false": "likely_false", "true": "likely_true", "unverifiable": "unverified"}
VERDICTS = ["likely_false", "unverified", "likely_true"]


def macro_f1(y_true: list[str], y_pred: list[str], labels: list[str]) -> float:
    if not y_true:
        return float("nan")
    return float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0))


def brier(p_true: list[float], is_true: list[bool]) -> float:
    if not p_true:
        return float("nan")
    return sum((p - (1.0 if t else 0.0)) ** 2 for p, t in zip(p_true, is_true, strict=True)) / len(
        p_true
    )


def abstention_quality(verdicts: list[str], fact_checks: list[str]) -> tuple[float | None, int]:
    """Share of `unverified` verdicts whose fact_check evidence is `none`; and their count."""
    unverified = [fc for v, fc in zip(verdicts, fact_checks, strict=True) if v == "unverified"]
    if not unverified:
        return None, 0
    return sum(fc == "none" for fc in unverified) / len(unverified), len(unverified)


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolated percentile, q in [0, 100]."""
    if not values:
        return float("nan")
    ordered = sorted(values)
    pos = (len(ordered) - 1) * q / 100
    lo, hi = math.floor(pos), math.ceil(pos)
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)
