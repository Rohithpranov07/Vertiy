"""Stage 1: language detection and translation to English."""

import logging

from verity.clients.translate import Translator, get_translator
from verity.errors import ExternalServiceError
from verity.lang.detect import detect_language
from verity.schemas import PreparedText, RedactedText

log = logging.getLogger(__name__)


def prepare(text: RedactedText, translator: Translator | None = None) -> PreparedText:
    """Detect the language and, for Tamil/Hindi, translate to English.

    English never touches a translation service. Any translation failure (including
    no provider configured) yields english == original and translation_ok == False.
    """
    language = detect_language(str(text))
    if language == "en":
        return PreparedText(
            original=str(text), language="en", english=str(text), translation_ok=True
        )
    active = translator if translator is not None else get_translator()
    if active is not None:
        try:
            english = active.translate(text, language)
        except ExternalServiceError as exc:
            log.warning("translation failed: %s", exc.code)
        else:
            if english.strip():
                return PreparedText(
                    original=str(text), language=language, english=english, translation_ok=True
                )
    return PreparedText(
        original=str(text), language=language, english=str(text), translation_ok=False
    )


__all__ = ["detect_language", "prepare"]
