import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from tests.conftest import DEBUNKED

from verity import db
from verity.api.app import create_app
from verity.clients.translate import Translator
from verity.errors import InputError
from verity.explain.passport import ungrounded_urls
from verity.pipeline import Pipeline
from verity.schemas import CheckRequest, Language, RedactedText

PHONE = "9876543210"
MARKER = "VERIFYMARK7391846205"


def test_debunked_message_with_phone(world: Pipeline) -> None:
    rec = world.check(CheckRequest(text=f"Share now! Call {PHONE}. {DEBUNKED}. Forward to all"))
    assert rec.verdict == "likely_false" and rec.p_true < 0.25
    assert rec.redactions == {"PHONE": 1}
    assert rec.matches and rec.matches[0].url == "http://f.example/lemon"
    assert rec.evidence.fact_check == "refuted"
    assert rec.reasons[0].node == "fact_check" and rec.what_if and rec.reply_card
    assert "http://f.example/lemon" in rec.reply_card
    assert rec.passport.passport_id and rec.family is not None
    with db.session() as conn:
        known = {r.url for r in db.list_factchecks(conn)} | {r.url for r in db.list_headlines(conn)}
    assert ungrounded_urls(rec, known) == []


def test_deterministic_record_apart_from_time(world: Pipeline) -> None:
    req = CheckRequest(text=DEBUNKED)
    a, b = world.check(req), world.check(req)
    assert a.passport.passport_id == b.passport.passport_id
    assert a.model_dump(exclude={"passport": {"created_at"}, "family": True}) == b.model_dump(
        exclude={"passport": {"created_at"}, "family": True}
    )


def test_edited_copy_joins_same_family_as_variant(world: Pipeline) -> None:
    first = world.check(CheckRequest(text=DEBUNKED))
    edited = world.check(CheckRequest(text="Good morning! \U0001f64f " + DEBUNKED + " \U0001f525"))
    assert first.family and edited.family
    assert first.family.family_id == edited.family.family_id


def test_unmatched_alarmist_message_is_not_a_confident_verdict(world: Pipeline) -> None:
    rec = world.check(
        CheckRequest(
            text="URGENT!!! The Chennai office announced on 5 March 2026 that all citizens "
            "must share this immediately!"
        )
    )
    assert rec.evidence.fact_check == "none"
    print("alarmist unmatched:", rec.verdict, round(rec.p_true, 3), rec.evidence)
    assert rec.verdict == "unverified"
    assert rec.what_if


def test_lookalike_link_forces_low_source(world: Pipeline) -> None:
    rec = world.check(CheckRequest(text="Claim your prize at https://new5.example/now today"))
    # news.example is trusted in the fixture; new5.example is a 5-for-s look-alike of it
    assert rec.lookalikes and rec.lookalikes[0].kind == "lookalike"
    assert rec.evidence.source_cred == "low"


def test_input_validation(world: Pipeline) -> None:
    with pytest.raises(InputError) as e1:
        world.check(CheckRequest(text="   "))
    assert e1.value.code == "empty_text"
    with pytest.raises(InputError) as e2:
        world.check(CheckRequest(text="a" * 6000))
    assert e2.value.code == "message_too_long"
    with pytest.raises(InputError) as e3:
        world.check(
            CheckRequest(text="Dies ist ein ziemlich langer deutscher Satz über das Wetter heute")
        )
    assert e3.value.code == "unsupported_language"


class RecordingTranslator:
    def __init__(self) -> None:
        self.args: list[str] = []

    def translate(self, text: RedactedText, source: Language) -> str:
        self.args.append(str(text))
        return "free recharge for everyone"


def test_privacy_invariant_marker_and_phone(
    world: Pipeline, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    translator: Translator = RecordingTranslator()
    pipeline = Pipeline(
        retriever=world.retriever(db.connect(tmp_path / "verity.db")), translator=translator
    )
    text = f"Urgent forward {MARKER}: call {PHONE} or pay rahul@okaxis to win free recharge today"
    with caplog.at_level(logging.DEBUG):
        rec = pipeline.check(CheckRequest(text=text))
        # a Tamil message containing the phone number must reach the translator redacted
        pipeline.check(CheckRequest(text=f"இந்த செய்தியை அனைவருக்கும் பகிருங்கள் {PHONE} இலவச ரீசார்ஜ்"))
    assert rec.redactions == {"PHONE": 1, "UPI": 1}
    dbfile = (tmp_path / "verity.db").read_bytes()
    for secret in (MARKER, PHONE, "rahul"):
        assert secret.encode() not in dbfile, secret
        assert secret not in caplog.text, secret
        assert secret not in " ".join(translator.args), secret  # type: ignore[attr-defined]
        assert secret not in rec.model_dump_json() or secret == MARKER
    assert translator.args and "[PHONE]" in translator.args[0]  # type: ignore[attr-defined]


def test_untranslated_indic_message_skips_retrieval(world: Pipeline) -> None:
    rec = world.check(CheckRequest(text="இந்த செய்தியை அனைவருக்கும் பகிருங்கள் இலவச ரீசார்ஜ் கிடைக்கும்"))
    assert rec.evidence.fact_check == "none" and rec.evidence.corroboration == "no"
    assert rec.matches == []


# ---------------- API ----------------
def test_api_endpoints(world: Pipeline) -> None:
    client = TestClient(create_app(world))
    ok = client.post("/check", json={"text": DEBUNKED})
    assert ok.status_code == 200 and ok.json()["verdict"] == "likely_false"
    for bad in ({"text": ""}, {}, {"text": "x", "extra": 1}, {"text": "a" * 6000}):
        r = client.post("/check", json=bad)
        assert r.status_code == 422 and "code" in r.json()["error"], bad
    assert client.post("/check", json={"text": "x" * 6000}).json()["error"]["code"] == (
        "message_too_long"
    )

    h = client.get("/health").json()
    assert h["factchecks"] == 1 and h["headlines"] == 1 and h["domains"] == 2

    body = {
        "message_hash": ok.json()["message_hash"],
        "verdict": "likely_false",
        "user_label": "right",
    }
    assert client.post("/feedback", json=body).json() == {"ok": True}
    assert client.post("/feedback", json={**body, "user_label": "maybe"}).status_code == 422
    assert client.post("/feedback", json={"verdict": "x"}).status_code == 422
    with db.session() as conn:
        rows = db.list_feedback(conn)
    assert len(rows) == 1 and rows[0].message_hash == ok.json()["message_hash"]


def test_chain_message_call_to_action_does_not_hide_the_claim(world: Pipeline) -> None:
    from tests.conftest import DEBUNKED

    from verity.schemas import CheckRequest

    message = f"{DEBUNKED}. Forward this to 10 people to stay safe!"
    record = world.check(CheckRequest(text=message))
    assert record.matches and record.claim.text.startswith(DEBUNKED[:20])
    assert record.verdict == "likely_false"
