from eval.convergence import SAMPLE_COUNTS, error_table

from verity.bn import infer, sample
from verity.schemas import PartialEvidence

EV = PartialEvidence(fact_check="refuted", sensational="high")


def test_same_seed_identical_and_different_seed_differs() -> None:
    assert sample(EV, 500, 1) == sample(EV, 500, 1)
    assert sample(EV, 500, 1).p_true != sample(EV, 500, 2).p_true


def test_posterior_sums_to_one() -> None:
    p = sample(EV, 200, 3)
    assert abs(p.p_true + p.p_false - 1.0) < 1e-12


def test_error_shrinks_as_n_grows() -> None:
    table = error_table()
    for name, errs in table.items():
        assert errs[-1] < errs[0], name
        assert errs[-1] < 0.02, (name, errs)
    assert len(SAMPLE_COUNTS) == 4


def test_close_to_exact_at_large_n() -> None:
    assert abs(sample(EV, 20000, 7).p_true - infer(EV).p_true) < 0.02
