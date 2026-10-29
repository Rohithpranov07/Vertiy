"""Language detection: Tamil, Hindi, English only. Deterministic."""

from langdetect.detector_factory import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

from verity.errors import InputError
from verity.schemas import Language

DetectorFactory.seed = 0  # documented way to make langdetect deterministic

_TAMIL = (0x0B80, 0x0BFF)
_DEVANAGARI = (0x0900, 0x097F)
_SCRIPT_SHARE = 0.5  # share of letters in one script that decides the language


def _script_language(text: str) -> Language | None:
    """Script check first: short Indic messages are often mis-labelled by langdetect
    (e.g. Hindi as Marathi/Nepali). Devanagari is therefore treated as Hindi."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return None
    tamil = sum(_TAMIL[0] <= ord(c) <= _TAMIL[1] for c in letters)
    deva = sum(_DEVANAGARI[0] <= ord(c) <= _DEVANAGARI[1] for c in letters)
    if tamil / len(letters) >= _SCRIPT_SHARE:
        return "ta"
    if deva / len(letters) >= _SCRIPT_SHARE:
        return "hi"
    return None


def detect_language(text: str) -> Language:
    by_script = _script_language(text)
    if by_script is not None:
        return by_script
    try:
        code = detect(text)
    except LangDetectException as exc:
        raise InputError("could not detect a language", code="unsupported_language") from exc
    if code == "en":
        return "en"
    raise InputError(
        f"unsupported language {code!r}; use en, ta or hi", code="unsupported_language"
    )
