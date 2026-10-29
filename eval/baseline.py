"""Baseline: TF-IDF + logistic regression. Trained on DEV `true`/`false` rows only.

  python -m eval.baseline --split dev            # cross-validated dev metrics
  python -m eval.baseline --split test --final   # trained on dev, evaluated on test

It cannot abstain: every message gets a P(true). The test split needs --final.
"""

import argparse
import csv
import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline, make_pipeline

from verity.config import get_settings

LABELLED = Path(__file__).resolve().parent / "labelled"
MIN_PER_CLASS_FOR_CV = 5


def _model(seed: int) -> Pipeline:
    model: Pipeline = make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, lowercase=True),
        LogisticRegression(max_iter=1000, random_state=seed),
    )
    return model


class Baseline:
    """P(true) for any text. Class labels are 'true' / 'false'."""

    def __init__(self, seed: int | None = None) -> None:
        self._seed = get_settings().random_seed if seed is None else seed
        self._model = _model(self._seed)

    def fit(self, rows: list[dict[str, str]]) -> "Baseline":
        decidable = [r for r in rows if r["label"] in ("true", "false")]
        self._model.fit([r["text"] for r in decidable], [r["label"] for r in decidable])
        return self

    def predict_proba(self, texts: list[str]) -> list[float]:
        proba = self._model.predict_proba(texts)
        idx = list(self._model.classes_).index("true")
        return [float(p[idx]) for p in proba]


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _metrics(y_true: list[str], p_true: list[float]) -> tuple[float, float]:
    y_pred = ["true" if p > 0.5 else "false" for p in p_true]
    return accuracy_score(y_true, y_pred), f1_score(y_true, y_pred, average="macro")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--split", choices=["dev", "test"], required=True)
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--labelled-dir", type=Path, default=LABELLED)
    args = ap.parse_args(argv)
    if args.split == "test" and not args.final:
        print("REFUSED: the test split is only evaluated with --final.", file=sys.stderr)
        return 2
    dev_path = args.labelled_dir / "dev.csv"
    if not dev_path.exists():
        print(f"{dev_path} not found (build it with scripts.split_labelled)", file=sys.stderr)
        return 1
    dev = [r for r in read_rows(dev_path) if r["label"] in ("true", "false")]
    seed = get_settings().random_seed
    if args.split == "dev":
        labels = [r["label"] for r in dev]
        if min(labels.count("true"), labels.count("false")) < MIN_PER_CLASS_FOR_CV:
            print("too few rows per class for cross-validation", file=sys.stderr)
            return 1
        cv = StratifiedKFold(n_splits=MIN_PER_CLASS_FOR_CV, shuffle=True, random_state=seed)
        proba = cross_val_predict(
            _model(seed), [r["text"] for r in dev], labels, cv=cv, method="predict_proba"
        )
        classes = sorted(set(labels))
        p_true = [float(p[classes.index("true")]) for p in proba]
        acc, f1 = _metrics(labels, p_true)
        print(f"dev rows={len(dev)} (5-fold cross-validated): accuracy={acc:.3f} macro-F1={f1:.3f}")
    else:
        test = [
            r for r in read_rows(args.labelled_dir / "test.csv") if r["label"] in ("true", "false")
        ]
        base = Baseline(seed).fit(dev)
        acc, f1 = _metrics(
            [r["label"] for r in test], base.predict_proba([r["text"] for r in test])
        )
        print(f"test rows={len(test)}: accuracy={acc:.3f} macro-F1={f1:.3f}")
    print("Note: the baseline cannot abstain.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
