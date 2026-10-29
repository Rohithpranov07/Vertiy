"""Validate a labelled-messages CSV; reports every problem with its row id."""

import argparse
import csv
import difflib
import re
import sys
from pathlib import Path

from pydantic import ValidationError

from verity.schemas import LabelledRow

COLUMNS = ["id", "text", "language", "label", "evidence_url", "gold_factcheck_url", "notes"]
NEAR_DUP_RATIO = 0.92


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", text.lower())).strip()


def read_raw(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = [h.strip() for h in (reader.fieldnames or [])]
        rows = [{k.strip(): (v or "") for k, v in r.items() if k} for r in reader]
    return header, rows


def validate(path: Path) -> list[str]:
    header, rows = read_raw(path)
    if header != COLUMNS:
        return [f"header: expected {COLUMNS}, got {header}"]
    problems: list[str] = []
    seen: dict[str, int] = {}
    parsed: list[tuple[str, str]] = []
    for line, raw in enumerate(rows, start=2):
        rid = raw["id"].strip() or f"<line {line}>"
        data: dict[str, str | None] = {
            k: (v.strip() or None) if k in ("evidence_url", "gold_factcheck_url", "notes") else v
            for k, v in raw.items()
        }
        try:
            row = LabelledRow.model_validate(data)
        except ValidationError as exc:
            for err in exc.errors():
                loc = ".".join(str(p) for p in err["loc"])
                problems.append(f"{rid}: invalid {loc} ({err['msg']})")
            continue
        if not row.id.strip():
            problems.append(f"{rid}: empty id")
        if row.id in seen:
            problems.append(f"{rid}: duplicate id (first on line {seen[row.id]})")
        seen.setdefault(row.id, line)
        if not row.text.strip():
            problems.append(f"{rid}: empty text")
        if row.label in ("false", "true") and not row.evidence_url:
            problems.append(f"{rid}: label {row.label!r} requires evidence_url")
        parsed.append((row.id, _norm(row.text)))
    for i, (id_a, a) in enumerate(parsed):
        for id_b, b in parsed[i + 1 :]:
            if a and b and difflib.SequenceMatcher(None, a, b).ratio() >= NEAR_DUP_RATIO:
                problems.append(f"{id_b}: near-duplicate text of {id_a}")
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv", type=Path)
    args = ap.parse_args(argv)
    problems = validate(args.csv)
    for p in problems:
        print(p)
    print(f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
