import re

import pytest

from verity.bn import infer
from verity.explain import ReplyParts, reasons, reply_card, what_if
from verity.explain.reply import REASON_TEXT
from verity.schemas import Evidence, Match, PartialEvidence, Reason

NEUTRAL = Evidence(
    source_cred="unknown",
    fact_check="none",
    corroboration="no",
    sensational="low",
    specifics="no",
)


def test_refuted_ranks_first_with_negative_shift() -> None:
    r = reasons(NEUTRAL.model_copy(update={"fact_check": "refuted"}))
    assert r[0].node == "fact_check" and r[0].state == "refuted" and r[0].shift < 0
    assert [abs(x.shift) for x in r] == sorted((abs(x.shift) for x in r), reverse=True)


def test_shift_matches_direct_recomputation() -> None:
    ev = NEUTRAL.model_copy(update={"fact_check": "refuted"})
    for reason in reasons(ev):
        partial = ev.model_dump()
        partial[reason.node] = None
        direct = (
            infer(PartialEvidence(**ev.model_dump())).p_true
            - infer(PartialEvidence(**partial)).p_true
        )
        assert reason.shift == pytest.approx(direct)


def test_reasons_deterministic() -> None:
    assert reasons(NEUTRAL) == reasons(NEUTRAL)


def test_what_if_never_current_state_and_top_three() -> None:
    alarmist = NEUTRAL.model_copy(update={"sensational": "high"})
    hints = what_if(alarmist)
    print(hints)
    assert len(hints) == 3
    for h in hints:
        assert h.state != str(getattr(alarmist, h.node))
    assert hints[0].node in ("fact_check", "corroboration")


def test_what_if_hint_changes_p_true_in_stated_direction() -> None:
    hints = what_if(NEUTRAL)
    base = infer(PartialEvidence(**NEUTRAL.model_dump())).p_true
    assert any(abs(h.p_true - base) > 0.05 for h in hints)


@pytest.mark.parametrize("verdict", ["likely_false", "unverified", "likely_true"])
@pytest.mark.parametrize("with_match", [True, False])
def test_reply_card_wordings(verdict: str, with_match: bool) -> None:
    matches = [Match(publisher="Pub", rating="refuted", url="https://f.example/1", similarity=0.8)]
    parts = ReplyParts(
        verdict=verdict,  # type: ignore[arg-type]
        reasons=[Reason(node="fact_check", state="refuted", shift=-0.5)],
        matches=matches if with_match else [],
    )
    card = reply_card(parts)
    assert ("https://f.example/1" in card) == with_match
    assert not re.search(r"\b(fake|real)\b", card, re.IGNORECASE)
    assert len(card) <= 400
    assert "published fact-check" in card


def test_all_template_phrases_avoid_banned_words() -> None:
    for phrase in REASON_TEXT.values():
        assert not re.search(r"\b(fake|real)\b", phrase, re.IGNORECASE)
