import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from scripts import demo, setup
from tests.conftest import DEBUNKED

from verity.api.app import create_app
from verity.pipeline import Pipeline

# SYNTHETIC FIXTURE: made-up demo messages written to a temp directory.


def test_repo_demo_files_are_todo_placeholders() -> None:
    for step in demo.FILES:
        assert demo.load_message(step) is None  # nothing invented in the repository


def test_load_message(tmp_path: Path) -> None:
    (tmp_path / demo.FILES[1]).write_text("a real message\n")
    (tmp_path / demo.FILES[2]).write_text("TODO: fill me")
    assert demo.load_message(1, tmp_path) == "a real message"
    assert demo.load_message(2, tmp_path) is None and demo.load_message(3, tmp_path) is None


def test_run_demo_steps_and_family_match(
    world: Pipeline, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / demo.FILES[1]).write_text(f"Call 9876543210 now. {DEBUNKED}. Forward to all")
    (tmp_path / demo.FILES[2]).write_text("URGENT!!! The office said on 5 March 2026 to share now!")
    (tmp_path / demo.FILES[3]).write_text(f"Good morning \U0001f64f {DEBUNKED} \U0001f525")
    (tmp_path / demo.FILES[4]).write_text("Claim your prize at https://new5.example/now")
    (tmp_path / demo.FILES[5]).write_text("TODO")
    (tmp_path / "expected.json").write_text(json.dumps({"1": {"verdict": "likely_false"}}))
    client = TestClient(create_app(world))
    assert demo.run_demo(client, tmp_path) == 0
    out = capsys.readouterr().out
    assert "expected likely_false: MATCH" in out
    assert "redactions: {'PHONE': 1}" in out
    assert "step 3 joins step 1's family: YES" in out
    assert "Step 5: Tamil message ===\nSKIPPED" in out
    assert "Step 6: Rumour Radar" in out and "Step 7: Reply card" in out
    assert "passport:" in out


def test_setup_is_rerunnable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DB_PATH", str(tmp_path / "v.db"))
    monkeypatch.setenv("INDEX_DIR", str(tmp_path / "ix"))
    monkeypatch.setenv("FACTCHECK_API_KEY", "")
    assert setup.setup() == 0
    assert setup.setup() == 0
    assert (tmp_path / "ix" / "factchecks.idx").exists()
