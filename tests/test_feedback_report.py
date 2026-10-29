from eval.feedback_report import report, suggest, summarise

# SYNTHETIC FIXTURE: made-up feedback taps.
ROWS = (
    [("likely_false", "right")] * 14
    + [("likely_false", "wrong")] * 6
    + [("likely_true", "right")] * 5
    + [("unverified", "right")] * 3
    + [("unverified", "wrong")] * 1
)


def test_summary_and_suggestion() -> None:
    s = summarise(ROWS)
    assert s["likely_false"] == (14, 6) and s["unverified"] == (3, 1)
    assert suggest(s, 0.75) == (0.8, 0.85)  # 30% wrong => two steps above 10%


def test_no_suggestion_when_few_taps_or_accurate() -> None:
    assert suggest(summarise([("likely_false", "wrong")] * 3), 0.75) is None
    assert suggest(summarise([("likely_true", "right")] * 20), 0.75) is None
    assert suggest(summarise([("likely_true", "wrong")] * 20), 0.95) is None  # already at cap


def test_report_text() -> None:
    text = report(ROWS, 0.75)
    print(text)
    assert "30.0%" in text and "too few taps" in text and "[0.8, 0.85]" in text
    assert "nothing was changed" in text
    assert "no change" in report([], 0.75)
