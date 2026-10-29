"""Retrieval precision@k on a labelled split.

  python -m eval.retrieval_precision --split dev --k 3

For each labelled row with a gold_factcheck_url, checks whether a fact-check with that
URL is in the top-k. The test split is refused unless --final is passed.
"""

import argparse
import csv
import sys
from pathlib import Path

from verity import db
from verity.config import get_settings
from verity.extract import extract_claim
from verity.retrieval.build import FACTCHECK_INDEX
from verity.retrieval.index import TfidfIndex
from verity.schemas import PreparedText

LABELLED = Path(__file__).resolve().parent / "labelled"


def _query(text: str, language: str) -> str:
    if language != "en":  # no translation here: non-English rows use their own text
        return text
    prepared = PreparedText(original=text, language="en", english=text, translation_ok=True)
    return extract_claim(prepared).claim.text or text


def precision_at_k(
    rows: list[dict[str, str]], index: TfidfIndex, url_by_id: dict[int, str], k: int
) -> tuple[float | None, list[str], int]:
    """Returns (precision, missed row ids, number of evaluated rows)."""
    hits = 0
    misses: list[str] = []
    evaluated = 0
    for row in rows:
        gold = (row.get("gold_factcheck_url") or "").strip()
        if not gold:
            continue
        evaluated += 1
        top = index.search(_query(row["text"], row["language"]), k)
        if gold in {url_by_id[i] for i, _ in top}:
            hits += 1
        else:
            misses.append(row["id"])
    return (hits / evaluated if evaluated else None), misses, evaluated


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--labelled-dir", type=Path, default=LABELLED)
    args = ap.parse_args(argv)
    if args.split == "test" and not args.final:
        print("REFUSED: the test split is only evaluated with --final.", file=sys.stderr)
        return 2
    path = args.labelled_dir / f"{args.split}.csv"
    if not path.exists():
        print(f"{path} not found (build it with scripts.split_labelled)", file=sys.stderr)
        return 1
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    index = TfidfIndex.load(get_settings().index_dir / FACTCHECK_INDEX)
    with db.session() as conn:
        url_by_id = {r.id: r.url for r in db.list_factchecks(conn)}
    p, misses, n = precision_at_k(rows, index, url_by_id, args.k)
    print(f"split={args.split} rows_with_gold={n} of {len(rows)}")
    print(f"precision@{args.k} = {p if p is None else round(p, 3)}")
    for m in misses:
        print("miss:", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
