from verity.extract import extract_claim
from verity.schemas import PreparedText

# SYNTHETIC FIXTURE: made-up messages.


def _p(text: str) -> PreparedText:
    return PreparedText(original=text, language="en", english=text, translation_ok=True)


def test_number_bearing_claim_beats_greeting() -> None:
    r = extract_claim(
        _p("Good morning friends! Govt gives Rs 5000 free to every family. Have a nice day")
    )
    assert "5000" in r.claim.text
    assert any("5000" in n for n in r.claim.numbers)


def test_links_extracted_including_bare_domains() -> None:
    r = extract_claim(_p("Claim now at https://pib-gov.in/offer. Or visit bit.ly/abc123, thanks!"))
    assert r.claim.links == ["https://pib-gov.in/offer", "bit.ly/abc123"]
    assert r.signals.has_link


def test_no_sentence_input() -> None:
    r = extract_claim(_p("   "))
    assert r.claim.text == "" and r.claim.entities == [] and r.claim.links == []
    assert not any(r.signals.model_dump().values())


def test_signals_and_entities() -> None:
    r = extract_claim(_p("Narendra Modi announced a new scheme in Chennai on 5 March 2026."))
    assert r.signals.has_person_org and r.signals.has_date and r.signals.has_place
    assert "Narendra Modi" in r.claim.entities and not r.signals.has_link


def test_deterministic_and_tie_goes_to_longer() -> None:
    msg = "Free cure. Free cure for all people today."
    a, b = extract_claim(_p(msg)), extract_claim(_p(msg))
    assert a == b and a.claim.text == "Free cure for all people today."


def test_call_to_action_is_never_preferred_over_the_rumour() -> None:
    from verity.extract import ranked_sentences
    from verity.schemas import PreparedText

    text = (
        "WhatsApp will become chargeable and your account will be deactivated at 6PM. "
        "Forward this to 10 people to stay free!"
    )
    ranked = ranked_sentences(
        PreparedText(original=text, english=text, language="en", translation_ok=True)
    )
    assert ranked[0].startswith("WhatsApp will become chargeable")
