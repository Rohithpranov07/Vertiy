"""Train the unigram+bigram naive Bayes tone model on the DEV split only.

  python -m verity.cues.train_tone --csv eval/labelled/dev.csv

Only `true` and `false` rows are used. The script refuses to read the test split.
"""

import argparse
import csv
import pickle
import sys
from pathlib import Path

from sklearn.feature_extraction.text import CountVectorizer
from sklearn.naive_bayes import MultinomialNB

from verity.config import get_settings
from verity.cues.tone import MODEL_FILE
from verity.errors import InputError


def _guard(path: Path) -> None:
    if "test" in path.stem.lower():
        raise InputError(
            f"refusing to read {path.name}: the test split is never used for training",
            code="test_split_refused",
        )


def train(rows: list[dict[str, str]], out: Path) -> int:
    labelled = [(r["text"], r["label"]) for r in rows if r["label"] in ("true", "false")]
    if len({label for _, label in labelled}) < 2:
        raise InputError("need both true and false rows to train", code="not_enough_data")
    vec = CountVectorizer(ngram_range=(1, 2), lowercase=True)
    x = vec.fit_transform([t for t, _ in labelled])
    nb = MultinomialNB(alpha=1.0).fit(x, [label for _, label in labelled])
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        pickle.dump((vec, nb), fh)
    return len(labelled)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=Path("eval/labelled/dev.csv"))
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args(argv)
    try:
        _guard(args.csv)
        with args.csv.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
        n = train(rows, args.out or get_settings().index_dir / MODEL_FILE)
    except InputError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        return 2
    print(f"trained on {n} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
