import itertools
from pathlib import Path

import pytest

from verity.cues import tone as tone_mod
from verity.cues.specifics import specifics
from verity.cues.train_tone import main as train_main
from verity.cues.train_tone import train
from verity.schemas import ClaimSignals

# SYNTHETIC FIXTURE: made-up training messages.


@pytest.mark.parametrize("combo", list(itertools.product([False, True], repeat=4)))
def test_specifics_truth_table(combo: tuple[bool, bool, bool, bool]) -> None:
    s = ClaimSignals(
        has_person_org=combo[0], has_date=combo[1], has_place=combo[2], has_link=combo[3]
    )
    assert specifics(s) == ("yes" if sum(combo) >= 2 else "no")


ALARM = "SHOCKING!!! URGENT warning, share this immediately!!!"
CALM = "The municipal office will hold a meeting on Tuesday about road repairs."


def test_style_score_ordering() -> None:
    assert tone_mod.style_score(ALARM) > 0.8
    assert tone_mod.style_score(CALM) < 0.1
    assert 0.0 <= tone_mod.style_score("") <= 1.0


def test_tone_style_only_without_model(tmp_path: Path) -> None:
    missing = tmp_path / "none.pkl"
    assert tone_mod.tone(ALARM, missing) == "high"
    assert tone_mod.tone(CALM, missing) == "low"


def test_train_and_score(tmp_path: Path) -> None:
    rows = [{"text": f"miracle cure share now number {i}", "label": "false"} for i in range(6)] + [
        {"text": f"council meeting minutes report item {i}", "label": "true"} for i in range(6)
    ]
    rows.append({"text": "who knows", "label": "unverifiable"})
    model = tmp_path / "tone.pkl"
    assert train(rows, model) == 12
    tone_mod.reset_model_cache()
    hi = tone_mod.tone_score("miracle cure share now", model)
    lo = tone_mod.tone_score("council meeting report", model)
    print("scores:", hi, lo, tone_mod.tone_score(ALARM, model))
    assert hi > lo and 0.0 <= lo <= hi <= 1.0


def test_training_rejects_test_split(tmp_path: Path) -> None:
    p = tmp_path / "test.csv"
    p.write_text("id,text,language,label,evidence_url,gold_factcheck_url,notes\n")
    assert train_main(["--csv", str(p), "--out", str(tmp_path / "m.pkl")]) == 2
    assert not (tmp_path / "m.pkl").exists()
