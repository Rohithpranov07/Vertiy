import csv
from pathlib import Path

import pytest
from eval import final_run
from eval.final_run import apply_defaults, fact_check_sweep, final, headline_sweep, tone_sweep
from scripts.validate_labelled import COLUMNS
from tests.conftest import DEBUNKED
from tests.test_eval import _labelled

from verity.errors import DataError
from verity.pipeline import Pipeline

ROOT = Path(__file__).resolve().parents[1]

# SYNTHETIC FIXTURE


def test_apply_defaults_edits_copies_only(tmp_path: Path) -> None:
    env = tmp_path / ".env.example"
    cfg = tmp_path / "config.py"
    env.write_text((ROOT / ".env.example").read_text())
    cfg.write_text((ROOT / "src/verity/config.py").read_text())
    apply_defaults({"VERDICT_THRESHOLD": 0.8, "TONE_THRESHOLD": 0.45}, env, cfg)
    assert "VERDICT_THRESHOLD=0.8" in env.read_text() and "TONE_THRESHOLD=0.45" in env.read_text()
    assert "verdict_threshold: float = Field(0.8," in cfg.read_text()
    assert "tone_threshold: float = Field(0.45," in cfg.read_text()
    with pytest.raises(DataError):
        apply_defaults({"RANDOM_SEED": 1.0}, env, cfg)
    with pytest.raises(DataError):
        apply_defaults({"VERDICT_THRESHOLD": 7.0}, env, cfg)
    assert "0.75" in (ROOT / ".env.example").read_text()  # the real file was not touched


def test_sweeps_and_single_use_lock(world: Pipeline, tmp_path: Path) -> None:
    gold = "http://f.example/lemon"
    rows = [
        (DEBUNKED, "false", gold, ""),
        ("Hot lemon water cures diabetes every morning", "false", gold, ""),
        ("Council budget minutes published for Chennai on 5 March 2026", "true", "", ""),
        ("URGENT!!! share this immediately!!!", "false", "", ""),
        ("Municipal office announces new parking rules on 1 May 2026", "true", "", ""),
        ("Secret miracle exposed, forward now!!!", "unverifiable", "", ""),
    ]
    _labelled(tmp_path / "dev.csv", rows)
    _labelled(tmp_path / "test.csv", rows)
    dev = list(csv.DictReader((tmp_path / "dev.csv").open()))
    retriever = world.retriever(__import__("verity").db.connect(tmp_path / "verity.db"))
    fc = fact_check_sweep(dev, retriever)
    assert fc[0][1] == 1.0 and fc[-1][1] <= fc[0][1]  # recall can only fall as threshold rises
    assert all(0.0 <= (x[2] or 0.0) <= 1.0 for x in fc)
    assert len(headline_sweep(dev, retriever)) == len(fc)
    assert all(a is None or 0 <= a <= 1 for _, a in tone_sweep(dev))

    lock = tmp_path / "lock.json"
    assert final(tmp_path, tmp_path, lock) == 0 and lock.exists()
    assert final(tmp_path, tmp_path, lock) == 3  # second use refused
    assert COLUMNS and final_run.main(["--final", "--labelled-dir", str(tmp_path)]) == 2
