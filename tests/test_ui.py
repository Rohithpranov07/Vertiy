import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from components import api
from components.format import (
    network_dot,
    reason_line,
    redaction_notice,
    safe_link,
    signed_points,
    verdict_card_html,
    what_if_sentence,
)
from verity.schemas import (
    ClaimRecord,
    Evidence,
    FamilyInfo,
    HealthResponse,
    LookalikeFlag,
    Match,
    Passport,
    Reason,
    VerdictRecord,
    WhatIf,
)

# SYNTHETIC FIXTURE: made-up verdict records.


UI_APP = Path(__file__).resolve().parents[1] / "ui" / "app.py"


def record(verdict: str = "likely_false", p_true: float = 0.09) -> VerdictRecord:
    fc = "refuted" if verdict == "likely_false" else "none"
    return VerdictRecord(
        verdict=verdict,  # type: ignore[arg-type]
        p_true=p_true,
        claim=ClaimRecord(text="Lemon water cures diabetes.", entities=[], numbers=[], links=[]),
        matches=[Match(publisher="Pub", rating="refuted", url="http://f.example/1", similarity=0.8)]
        if fc == "refuted"
        else [],
        reasons=[Reason(node="fact_check", state=fc, shift=-0.62 if fc == "refuted" else 0.0)],
        what_if=[WhatIf(node="corroboration", state="yes", p_true=0.35)],
        reply_card="Hi, I checked this message ...",
        message_hash="hash123",
        evidence=Evidence(
            source_cred="unknown",
            fact_check=fc,
            corroboration="no",  # type: ignore[arg-type]
            sensational="high",
            specifics="no",
        ),
        redactions={"PHONE": 1},
        lookalikes=[
            LookalikeFlag(
                domain="thehlndu.com", lookalike_of="thehindu.com", distance=1, kind="lookalike"
            )
        ],
        family=FamilyInfo(family_id="fam-1", hamming=3, linked_rating="refuted", source="variant"),
        passport=Passport(
            passport_id="pid",
            index_version="i" * 64,
            cpt_version="c" * 64,
            threshold=0.75,
            created_at="2026-10-29T10:00:00Z",
        ),
    )


def test_formatters() -> None:
    assert signed_points(-0.62) == "-62 pts" and signed_points(0.0) == "0 pts"
    assert "towards false" in reason_line(Reason(node="fact_check", state="refuted", shift=-0.6))
    assert "35%" in what_if_sentence(WhatIf(node="corroboration", state="yes", p_true=0.35), 0.09)
    assert safe_link("javascript:alert(1)") is None and safe_link("https://a.example/x")
    assert "1 phone number" in (redaction_notice({"PHONE": 1}) or "")
    assert redaction_notice({}) is None


@pytest.mark.parametrize("verdict", ["likely_false", "unverified", "likely_true"])
def test_cards_never_use_bare_fake_or_real(verdict: str) -> None:
    html = verdict_card_html(record(verdict))
    assert not re.search(r"\b(fake|real)\b", html, re.IGNORECASE)
    dot = network_dot(record(verdict).evidence, 0.09, record(verdict).verdict)
    assert "claim_true" in dot and dot.count("->") == 5


def run_app(monkeypatch: pytest.MonkeyPatch, result: object) -> AppTest:
    def fake_check(text: str, url: str | None) -> VerdictRecord:
        if isinstance(result, Exception):
            raise result
        assert isinstance(result, VerdictRecord)
        return result

    monkeypatch.setattr(api, "post_check", fake_check)
    monkeypatch.setattr(
        api,
        "get_health",
        lambda: HealthResponse(
            factchecks=3, headlines=2, domains=1, last_refresh="2026-10-29T10:00:00Z"
        ),
    )
    at = AppTest.from_file(str(UI_APP), default_timeout=20).run()
    at.text_area[0].set_value("some message")
    next(b for b in at.button if b.label == "Check").click().run()
    return at


def test_likely_false_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    at = run_app(monkeypatch, record())
    assert not at.exception
    shown = " ".join(m.value for m in at.markdown)
    assert "Likely false" in shown and "9%" in shown
    assert "Privacy shield removed 1 phone number" in shown
    assert "looks like thehindu.com" in shown and "Warning" in shown
    assert "Rumour family" in shown and "edited copy" in shown
    assert "Rated refuted" in shown and "-62 pts" in shown
    labels = [b.label for b in at.button]
    assert labels[-3:] == ["Check", "Yes", "No"] and "Water and heart attacks" in labels


def test_unverified_screen(monkeypatch: pytest.MonkeyPatch) -> None:
    at = run_app(monkeypatch, record("unverified", 0.4))
    assert not at.exception and "Unverified" in " ".join(m.value for m in at.markdown)


@pytest.mark.parametrize(
    ("err", "needle"),
    [
        (api.ApiError("x", "unsupported_language"), "English, Tamil and Hindi"),
        (api.ApiError("Could not reach the VERITY service", "unreachable"), "Could not reach"),
    ],
)
def test_error_screens(monkeypatch: pytest.MonkeyPatch, err: Exception, needle: str) -> None:
    at = run_app(monkeypatch, err)
    assert needle in " ".join(m.value for m in at.markdown)
    assert not at.exception


def test_feedback_tap_calls_api(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        api, "post_feedback", lambda h, v, label: sent.append((h, v, label)) or True
    )
    at = run_app(monkeypatch, record())
    next(b for b in at.button if b.label == "Yes").click().run()
    assert sent == [("hash123", "likely_false", "right")]
    assert "feedback was recorded" in " ".join(m.value for m in at.markdown)


def test_html_builders_escape_untrusted_text() -> None:
    from components.format import claim_html, lookalike_text, matches_html, warning_html

    evil = "<script>alert(1)</script>"
    rec = record().model_copy(
        update={
            "matches": [
                Match(publisher=evil, rating="refuted", url="javascript:alert(1)", similarity=0.5),
                Match(
                    publisher="ok",
                    rating="refuted",
                    url='http://x.example/"onmouseover="x',
                    similarity=0.4,
                ),
            ]
        }
    )
    out = (
        matches_html(rec)
        + claim_html(evil)
        + warning_html(lookalike_text("lookalike", evil, evil, 1))
    )
    assert "<script>" not in out and "javascript:" not in out
    assert 'href="http://x.example/&quot;onmouseover=&quot;x"' in out


def test_new_cards_render_and_escape() -> None:
    from components.cards import (
        bento_html,
        history_rows_html,
        history_tiles_html,
        metrics_html,
        passport_html,
        privacy_html,
        radar_tiles_html,
        signals_html,
        stat_tiles_html,
        steps_html,
    )
    from components.examples import EXAMPLES
    from verity.schemas import RadarItem

    rec = record()
    assert "9%" in metrics_html(rec) and "Edited copy" in metrics_html(rec)
    assert "Phone numbers" in privacy_html({"PHONE": 1})
    assert "Nothing in this message needed removing" in privacy_html({})
    assert "pid" in passport_html(rec.passport) and "0.75" in passport_html(rec.passport)
    assert "no fact-check found" not in signals_html(rec) and "alarming wording" in signals_html(
        rec
    )
    health = HealthResponse(factchecks=2662, headlines=0, domains=0, last_refresh=None)
    assert "2,662" in stat_tiles_html(health) and "Never" in stat_tiles_html(health)
    assert bento_html().count('class="c ') == 5 and steps_html().count('class="s"') == 4
    evil = "<img src=x onerror=alert(1)>"
    items = [
        {
            "hash": "h",
            "claim": evil,
            "verdict": "unverified",
            "p_true": 0.4,
            "matches": 0,
            "time": "10:00",
        }
    ]
    assert "<img" not in history_rows_html(items) and "1" in history_tiles_html(items)
    radar = [
        RadarItem(
            family_id="f",
            keywords=["k"],
            recent=5,
            previous=1,
            surge=2.5,
            linked_url="http://x.example/a",
        )
    ]
    assert "2.50x" in radar_tiles_html(radar)
    assert len(EXAMPLES) == 8 and all(e.text.strip() for e in EXAMPLES)
