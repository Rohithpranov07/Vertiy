import csv
import json
import math
from pathlib import Path

from eval import d_metrics
from eval.ablation import EvidenceRow, ablate
from eval.metrics import abstention_quality, brier, macro_f1, percentile
from eval.run_eval import main, run
from scripts.validate_labelled import COLUMNS
from tests.conftest import DEBUNKED

from verity.pipeline import Pipeline
from verity.schemas import Evidence

# SYNTHETIC FIXTURE: made-up labelled rows and evidence.


def test_metrics() -> None:
    assert macro_f1(["a", "b"], ["a", "b"], ["a", "b"]) == 1.0
    assert math.isnan(macro_f1([], [], ["a"]))
    assert brier([1.0, 0.0], [True, False]) == 0.0
    assert brier([0.5, 0.5], [True, False]) == 0.25
    assert percentile([1, 2, 3, 4, 5], 50) == 3 and percentile([1, 2], 95) == 1.95
    assert abstention_quality(
        ["unverified", "unverified", "likely_false"], ["none", "refuted", "x"]
    ) == (
        0.5,
        2,
    )
    assert abstention_quality(["likely_true"], ["none"]) == (None, 0)


def _ev(fc: str) -> Evidence:
    return Evidence(
        source_cred="unknown",
        fact_check=fc,
        corroboration="no",  # type: ignore[arg-type]
        sensational="high",
        specifics="no",
    )


def test_ablation_keys_and_effect() -> None:
    rows = [
        EvidenceRow("false", _ev("refuted")),
        EvidenceRow("true", _ev("supported")),
        EvidenceRow("unverifiable", _ev("none")),
    ]
    out = ablate(rows, 0.75)
    assert set(out) == {
        "(none dropped)",
        "source_cred",
        "fact_check",
        "corroboration",
        "sensational",
        "specifics",
    }
    assert out["fact_check"][1] <= 0.0  # dropping the fact-check cannot help here


def test_d1_d3_starters() -> None:
    d1 = d_metrics.d1_redaction()
    assert d1["recall"] == 1.0 and d1["clean_unchanged"] == d1["clean_strings"]
    d3 = d_metrics.d3_lookalikes()
    assert (d3["true_flags"], d3["false_flags"], d3["misses"]) == (5, 0, 1)
    assert d3["missed_domains"] == ["ndtv.in"]


def test_d2_starter_reports_numbers() -> None:
    d2 = d_metrics.d2_variants()
    print(d2)
    assert d2["variants"] == 5 and d2["unrelated"] == 2
    assert d2["false_family_matches"] == 0


def _labelled(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for i, (text, label, gold, _) in enumerate(rows):
            w.writerow(
                {
                    "id": f"{path.stem}{i}",
                    "text": text,
                    "language": "en",
                    "label": label,
                    "evidence_url": "http://e.example",
                    "gold_factcheck_url": gold,
                    "notes": "",
                }
            )


def test_end_to_end_dev_run_and_test_refusal(world: Pipeline, tmp_path: Path) -> None:
    gold = "http://f.example/lemon"
    dev = [
        (DEBUNKED, "false", gold, ""),
        ("Hot lemon water every morning cures diabetes completely!!", "false", gold, ""),
        (
            "The council meeting minutes were published on the official portal on 5 March 2026",
            "true",
            "",
            "",
        ),
        (
            "Municipal budget report released in Chennai on 12 April 2026 by the office",
            "true",
            "",
            "",
        ),
        ("Share URGENT alert free recharge for everyone immediately!!!", "unverifiable", "", ""),
        ("Warning: this forward must be shared with ten people today!", "unverifiable", "", ""),
        (
            "New metro line opens in Delhi on 1 May 2026 says the transport department",
            "true",
            "",
            "",
        ),
        ("Miracle powder cures every disease in one day, doctors shocked!!!", "false", "", ""),
        ("Government announces new scholarship portal for students in Mumbai", "true", "", ""),
        ("Eating raw garlic prevents all viruses, share this alert now!!!", "false", "", ""),
        ("Bank holiday list for November 2026 published by the central bank", "true", "", ""),
        ("Secret method to double your money overnight, forward immediately", "false", "", ""),
    ]
    _labelled(tmp_path / "dev.csv", dev)
    _labelled(tmp_path / "test.csv", dev[:6])
    assert (
        main(["--split", "test", "--labelled-dir", str(tmp_path), "--out-dir", str(tmp_path)]) == 2
    )
    res = run("dev", tmp_path, tmp_path)
    assert set(res["conditions"]) == {"full index", "gold fact-checks removed"}  # type: ignore[arg-type]
    full = res["conditions"]["full index"]  # type: ignore[index]
    nogold = res["conditions"]["gold fact-checks removed"]  # type: ignore[index]
    assert full["evaluated"] == 12 and full["precision_at_3"] == 1.0
    assert "precision_at_3" not in nogold
    assert 0.0 <= full["macro_f1_3class"] <= 1.0 and full["latency_p95"] >= full["latency_median"]
    assert nogold["abstention_quality"] is None or 0.0 <= nogold["abstention_quality"] <= 1.0
    meta = res["meta"]
    assert meta["split"] == "dev" and meta["rows"] == 12 and len(meta["labelled_sha256"]) == 64  # type: ignore[index]
    diff = res["differentiators"]
    assert diff["D4_reproducibility"]["identical_records"] == diff["D4_reproducibility"]["messages"]  # type: ignore[index]
    assert diff["D5_radar_privacy"]["shown_below_min_count"] == []  # type: ignore[index]
    assert diff["D5_radar_privacy"]["tables_with_text_columns"] == {}  # type: ignore[index]
    assert (
        main(["--split", "dev", "--labelled-dir", str(tmp_path), "--out-dir", str(tmp_path)]) == 0
    )
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["meta"]["split"] == "dev" and (tmp_path / "report.md").exists()
    assert (tmp_path / "unverified_cases.csv").exists()
