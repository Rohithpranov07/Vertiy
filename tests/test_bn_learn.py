import json
from pathlib import Path

import pytest

from verity.bn import infer
from verity.bn.evidence_table import Truth
from verity.bn.learn import diff_report, learn_cpts, main
from verity.bn.network import PRIORS_FILE, STATES, load_cpt_file
from verity.schemas import Evidence, PartialEvidence

# SYNTHETIC FIXTURE: made-up evidence rows with made-up truth labels.


def _ev(fc: str, corr: str = "no") -> Evidence:
    return Evidence(
        source_cred="unknown",
        fact_check=fc,  # type: ignore[arg-type]
        corroboration=corr,  # type: ignore[arg-type]
        sensational="high",
        specifics="no",
    )


TABLE: list[tuple[Evidence, Truth]] = [(_ev("refuted"), "false")] * 30 + [
    (_ev("supported", "yes"), "true")
] * 10


def test_learn_matches_manual_bayes_and_has_no_zeros() -> None:
    priors = load_cpt_file(PRIORS_FILE)
    learned = learn_cpts(TABLE, priors, ess=10)
    # fact_check | claim: 30 false rows are all 'refuted', 10 true rows all 'supported'.
    prior = priors.tables["fact_check"].values
    got = learned.tables["fact_check"].values
    # column 1 = claim false: (counts + 10*prior) / (30 + 10)
    assert got[0][1] == pytest.approx((30 + 10 * prior[0][1]) / 40)
    assert got[1][1] == pytest.approx((0 + 10 * prior[1][1]) / 40)
    for node in STATES:
        cells = [v for row in learned.tables[node].values for v in row]
        assert min(cells) > 0.0
        for c in range(len(learned.tables[node].values[0])):
            assert sum(r[c] for r in learned.tables[node].values) == pytest.approx(1.0)
    assert "fact_check" in diff_report(priors, learned)


def test_learned_cpts_used_by_infer(tmp_path: Path) -> None:
    learned = learn_cpts(TABLE, load_cpt_file(PRIORS_FILE), ess=10, dev_hash="abc")
    path = tmp_path / "cpt_learned.json"
    path.write_text(json.dumps(learned.model_dump()))
    assert learned.version and learned.dev_set_hash == "abc"
    base = infer(PartialEvidence(fact_check="refuted"))
    new = infer(PartialEvidence(fact_check="refuted"), cpt_path=path)
    assert new.p_true < base.p_true  # refuted was even more predictive of false in the data


def test_test_split_refused(tmp_path: Path) -> None:
    p = tmp_path / "test.csv"
    p.write_text("id,text,language,label,evidence_url,gold_factcheck_url,notes\n")
    assert main(["--csv", str(p), "--out", str(tmp_path / "o.json")]) == 2
    assert not (tmp_path / "o.json").exists()
