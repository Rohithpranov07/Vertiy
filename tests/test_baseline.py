import csv
from pathlib import Path

from eval.baseline import Baseline, main
from scripts.validate_labelled import COLUMNS

# SYNTHETIC FIXTURE: made-up training messages.


def _write(path: Path, rows: list[tuple[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for i, (text, label) in enumerate(rows):
            w.writerow(
                {
                    "id": f"r{i}",
                    "text": text,
                    "language": "en",
                    "label": label,
                    "evidence_url": "http://e.example",
                    "gold_factcheck_url": "",
                    "notes": "",
                }
            )


ROWS = [(f"miracle cure share now forward {i}", "false") for i in range(10)] + [
    (f"council meeting report budget minutes {i}", "true") for i in range(10)
]


def test_baseline_learns_and_is_seeded() -> None:
    rows = [{"text": t, "label": lab} for t, lab in ROWS] + [{"text": "x", "label": "unverifiable"}]
    a = Baseline(1).fit(rows).predict_proba(["miracle cure share", "council budget report"])
    b = Baseline(1).fit(rows).predict_proba(["miracle cure share", "council budget report"])
    assert a == b and a[0] < 0.5 < a[1]
    assert all(0.0 <= p <= 1.0 for p in a)


def test_dev_metrics_and_test_split_refused(tmp_path: Path, capsys: object) -> None:
    _write(tmp_path / "dev.csv", ROWS)
    _write(tmp_path / "test.csv", ROWS[:4] + ROWS[10:14])
    assert main(["--split", "dev", "--labelled-dir", str(tmp_path)]) == 0
    assert main(["--split", "test", "--labelled-dir", str(tmp_path)]) == 2
    assert main(["--split", "test", "--final", "--labelled-dir", str(tmp_path)]) == 0
