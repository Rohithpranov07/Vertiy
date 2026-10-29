import pytest
from pydantic import ValidationError

from verity.config import load_settings
from verity.errors import DataError, InputError, VerityError
from verity.privacy import message_hash
from verity.schemas import (
    CheckRequest,
    ClaimRecord,
    Evidence,
    Match,
    Passport,
    Reason,
    RedactedText,
    VerdictRecord,
    WhatIf,
)


def test_check_request_valid_and_invalid() -> None:
    assert CheckRequest.model_validate({"text": "hello"}).url is None
    with pytest.raises(ValidationError):
        CheckRequest.model_validate({"text": "hi", "extra": 1})
    with pytest.raises(ValidationError):
        CheckRequest.model_validate({"url": "http://x"})


def _record() -> VerdictRecord:
    return VerdictRecord(
        verdict="likely_false",
        p_true=0.09,
        claim=ClaimRecord(text="c", entities=["e"], numbers=["1"], links=[]),
        matches=[Match(publisher="p", rating="refuted", url="u", similarity=0.8)],
        reasons=[Reason(node="fact_check", state="refuted", shift=-0.6)],
        what_if=[WhatIf(node="corroboration", state="yes", p_true=0.35)],
        reply_card="r",
        message_hash="h",
        evidence=Evidence(
            source_cred="unknown",
            fact_check="refuted",
            corroboration="no",
            sensational="high",
            specifics="no",
        ),
        redactions={"PHONE": 1},
        lookalikes=[],
        family=None,
        passport=Passport(
            passport_id="a", index_version="i", cpt_version="c", threshold=0.75, created_at="t"
        ),
    )


def test_verdict_record_round_trip() -> None:
    rec = _record()
    assert VerdictRecord.model_validate_json(rec.model_dump_json()) == rec


def test_bad_enum_rejected() -> None:
    data = _record().model_dump()
    data["verdict"] = "fake"
    with pytest.raises(ValidationError):
        VerdictRecord.model_validate(data)


def test_message_hash_stable_under_case_and_whitespace() -> None:
    a = message_hash(RedactedText("Hello   World\n"))
    b = message_hash(RedactedText("  hello world"))
    assert a == b
    assert a != message_hash(RedactedText("hello there"))


def test_errors_carry_codes() -> None:
    assert isinstance(InputError("x"), VerityError)
    assert InputError("x", code="unsupported_language").code == "unsupported_language"
    assert DataError("x").code == "data_error"


def test_config_defaults_and_overrides() -> None:
    s = load_settings({})
    assert s.verdict_threshold == 0.75 and s.simhash_max_hamming == 14
    s2 = load_settings({"VERDICT_THRESHOLD": "0.8  # tuned", "RANDOM_SEED": "7"})
    assert s2.verdict_threshold == 0.8 and s2.random_seed == 7
    with pytest.raises(DataError):
        load_settings({"VERDICT_THRESHOLD": "abc"})
    with pytest.raises(DataError):
        load_settings({"TRANSLATION_PROVIDER": "bogus"})
