"""Sweep VERDICT_THRESHOLD on the DEV split. Prints a table; writes nothing.

  python -m eval.threshold_sweep [--csv eval/labelled/dev.csv]

coverage         = share of messages that are NOT abstained (verdict != unverified)
confident-error  = share of confident verdicts that are wrong, where wrong means the
                   opposite of the label, or any confident verdict on an `unverifiable` row.
"""

import argparse
import csv
import sys
from pathlib import Path

from verity import db
from verity.bn import decide, infer
from verity.bn.evidence_table import evidence_for_text
from verity.cues.source import db_lookup
from verity.retrieval import Retriever
from verity.schemas import PartialEvidence, Posterior, VerdictLabel

THRESHOLDS = [round(0.60 + 0.05 * i, 2) for i in range(8)]  # 0.60 .. 0.95


def _is_error(verdict: VerdictLabel, label: str) -> bool:
    if label == "unverifiable":
        return True
    return (label == "false") != (verdict == "likely_false")


def sweep(
    posteriors: list[tuple[Posterior, str]], thresholds: list[float]
) -> list[tuple[float, float, float | None, int]]:
    """Rows of (threshold, coverage, confident_error_rate or None, n_confident)."""
    out: list[tuple[float, float, float | None, int]] = []
    for th in thresholds:
        verdicts = [(decide(p, th), label) for p, label in posteriors]
        confident = [(v, lab) for v, lab in verdicts if v != "unverified"]
        errors = sum(_is_error(v, lab) for v, lab in confident)
        out.append(
            (
                th,
                len(confident) / len(verdicts) if verdicts else 0.0,
                errors / len(confident) if confident else None,
                len(confident),
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=Path("eval/labelled/dev.csv"))
    args = ap.parse_args(argv)
    if "test" in args.csv.stem.lower():
        print("REFUSED: threshold tuning never touches the test split.", file=sys.stderr)
        return 2
    with args.csv.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    with db.session() as conn:
        retriever = Retriever.load(conn)
        trusted = [d.domain for d in db.list_domains(conn) if d.cls == "trusted"]
        lookup = db_lookup(conn)
        posteriors = [
            (
                infer(
                    PartialEvidence(
                        **evidence_for_text(r["text"], retriever, lookup, trusted).model_dump()
                    )
                ),
                r["label"],
            )
            for r in rows
        ]
    print(f"{len(rows)} dev rows")
    print("threshold  coverage  confident-error  n_confident")
    for th, cov, err, n in sweep(posteriors, THRESHOLDS):
        e = "   n/a" if err is None else f"{err:6.3f}"
        print(f"{th:9.2f}  {cov:8.3f}  {e:>15}  {n:11d}")
    print("No threshold was written; choose VERDICT_THRESHOLD yourself.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
