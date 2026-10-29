import pytest
from eval.threshold_sweep import sweep

from verity.bn import decide
from verity.schemas import Posterior


def post(p_true: float) -> Posterior:
    return Posterior(p_true=p_true, p_false=1.0 - p_true)


@pytest.mark.parametrize(
    ("p_true", "expected"),
    [
        (0.25, "likely_false"),  # p_false == 0.75 exactly at threshold
        (0.2499, "likely_false"),
        (0.2501, "unverified"),
        (0.50, "unverified"),
        (0.7499, "unverified"),
        (0.75, "likely_true"),
        (0.90, "likely_true"),
    ],
)
def test_boundaries(p_true: float, expected: str) -> None:
    assert decide(post(p_true), 0.75) == expected


def test_both_sides_below_threshold_abstains() -> None:
    assert decide(post(0.6), 0.75) == "unverified"
    assert decide(post(0.4), 0.75) == "unverified"


def test_sweep_table() -> None:
    # SYNTHETIC FIXTURE
    data = [(post(0.05), "false"), (post(0.9), "true"), (post(0.3), "false"), (post(0.9), "false")]
    rows = sweep(data, [0.6, 0.75, 0.95])
    for r in rows:
        print(r)
    assert rows[0][0] == 0.6 and rows[0][1] == 1.0 and rows[0][2] == pytest.approx(0.25)
    assert rows[2][1] < rows[0][1]  # higher threshold -> lower coverage
