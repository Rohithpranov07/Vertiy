import json
from pathlib import Path

import pytest

from verity.bn import infer
from verity.bn.network import EDGES, PRIORS_FILE, STATES, load_cpt_file, validate_cpts
from verity.errors import ModelError
from verity.schemas import PartialEvidence


def pt(**kw: str) -> float:
    return infer(PartialEvidence(**kw)).p_true  # type: ignore[arg-type]


def test_structure_matches_spec() -> None:
    assert len(EDGES) == 5 and set(STATES) == {
        "source_cred",
        "claim_true",
        "fact_check",
        "corroboration",
        "sensational",
        "specifics",
    }


def test_cpt_columns_sum_to_one_and_no_zero() -> None:
    cpts = load_cpt_file(PRIORS_FILE)
    validate_cpts(cpts)
    assert cpts.source == "expert-prior-v0" and "AWAITING" in (cpts.status or "")


def test_no_evidence_equals_prior() -> None:
    cpts = load_cpt_file(PRIORS_FILE)
    src = [r[0] for r in cpts.tables["source_cred"].values]
    p_true_given = cpts.tables["claim_true"].values[0]
    expected = sum(p * t for p, t in zip(src, p_true_given, strict=True))
    assert pt() == pytest.approx(expected, abs=1e-9)


def test_directions() -> None:
    base = pt()
    assert pt(fact_check="refuted") < pt(fact_check="none") < pt(fact_check="supported")
    assert pt(fact_check="refuted") < base < pt(fact_check="supported")
    assert pt(source_cred="trusted") > pt(source_cred="low")
    assert pt(corroboration="no") < pt(corroboration="yes")
    assert pt(sensational="high") < pt(sensational="low")
    assert pt(specifics="no") < pt(specifics="yes")


def test_five_hand_picked_combinations(capsys: pytest.CaptureFixture[str]) -> None:
    combos = [
        dict(
            source_cred="unknown",
            fact_check="refuted",
            corroboration="no",
            sensational="high",
            specifics="no",
        ),
        dict(
            source_cred="trusted",
            fact_check="supported",
            corroboration="yes",
            sensational="low",
            specifics="yes",
        ),
        dict(
            source_cred="unknown",
            fact_check="none",
            corroboration="no",
            sensational="high",
            specifics="no",
        ),
        dict(
            source_cred="low",
            fact_check="none",
            corroboration="no",
            sensational="high",
            specifics="yes",
        ),
        dict(
            source_cred="unknown",
            fact_check="none",
            corroboration="yes",
            sensational="low",
            specifics="yes",
        ),
    ]
    for c in combos:
        print(c, "->", round(pt(**c), 4))
    vals = [pt(**c) for c in combos]
    assert vals[0] < 0.1 and vals[1] > 0.9 and all(0 < v < 1 for v in vals)


def test_invalid_cpt_rejected(tmp_path: Path) -> None:
    data = json.loads(PRIORS_FILE.read_text())
    data["tables"]["specifics"]["values"] = [[0.9, 0.3], [0.2, 0.7]]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(data))
    with pytest.raises(ModelError):
        load_cpt_file(bad)
