import httpx
import pytest

from verity.clients.translate import HostedTranslator
from verity.config import load_settings
from verity.errors import ExternalServiceError, InputError
from verity.lang import prepare
from verity.lang.detect import detect_language
from verity.schemas import Language, RedactedText

# SYNTHETIC FIXTURE: made-up sentences and a fake translator.
TA = "இந்த செய்தியை அனைவருக்கும் பகிருங்கள் இலவச ரீசார்ஜ் கிடைக்கும்"
HI = "इस संदेश को सभी को भेजें मुफ्त रिचार्ज मिलेगा आज ही"
EN = "Share this message with everyone because free recharge is available today"


class FakeTranslator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Language]] = []

    def translate(self, text: RedactedText, source: Language) -> str:
        self.calls.append((str(text), source))
        return f"translated:{source}"


class FailingTranslator:
    def translate(self, text: RedactedText, source: Language) -> str:
        raise ExternalServiceError("down", code="translation_unavailable")


def test_detection() -> None:
    assert detect_language(EN) == "en"
    assert detect_language(TA) == "ta"
    assert detect_language(HI) == "hi"


def test_unsupported_language_raises() -> None:
    with pytest.raises(InputError) as ei:
        detect_language("Dies ist ein ziemlich langer deutscher Satz über das Wetter heute")
    assert ei.value.code == "unsupported_language"
    with pytest.raises(InputError):
        detect_language("12345 !!!")


def test_english_never_translates() -> None:
    fake = FakeTranslator()
    p = prepare(RedactedText(EN), fake)
    assert p.language == "en" and p.english == EN and p.translation_ok and fake.calls == []


@pytest.mark.parametrize(("text", "lang"), [(TA, "ta"), (HI, "hi")])
def test_indic_translated(text: str, lang: str) -> None:
    fake = FakeTranslator()
    p = prepare(RedactedText(text), fake)
    assert p.language == lang and p.original == text
    assert p.english == f"translated:{lang}" and p.translation_ok


def test_failure_and_no_provider_degrade() -> None:
    p = prepare(RedactedText(TA), FailingTranslator())
    assert p.translation_ok is False and p.english == TA
    # default settings: provider "none"
    q = prepare(RedactedText(HI))
    assert q.translation_ok is False and q.english == HI and q.language == "hi"


def test_hosted_translator_contract() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(200, json={"translatedText": "hello", "detectedLanguage": None})

    tr = HostedTranslator(
        "http://lt.example/",
        "SECRET",
        settings=load_settings({}),
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    assert tr.translate(RedactedText(TA), "ta") == "hello"
    req = seen[0]
    assert str(req.url) == "http://lt.example/translate" and "SECRET" not in str(req.url)
    body = req.content.decode()
    assert "source=ta" in body and "target=en" in body and "api_key=SECRET" in body


def test_short_english_is_not_rejected() -> None:
    assert detect_language("Indian PM is muslim") == "en"


def test_english_with_foreign_looking_names_is_accepted() -> None:
    assert detect_language("PM Modi evades question on petrol price hike") == "en"
    assert (
        detect_language("Hindu girls kidnapped from elevator by Muslim men in Bangalore, Karnataka")
        == "en"
    )
    with pytest.raises(InputError):
        detect_language(
            "Rastislav Iliev a Peter Visolajský hovoria o nebezpečenstve vakcín proti covidu"
        )


def test_english_headline_with_connectives_is_accepted() -> None:
    assert (
        detect_language("Israel president urges against new vote despite inconclusive result")
        == "en"
    )
