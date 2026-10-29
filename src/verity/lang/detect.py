"""Language detection: Tamil, Hindi, English only. Deterministic."""

import re

from langdetect.detector_factory import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

from verity.errors import InputError
from verity.schemas import Language

DetectorFactory.seed = 0  # documented way to make langdetect deterministic

_TAMIL = (0x0B80, 0x0BFF)
_DEVANAGARI = (0x0900, 0x097F)
_SHORT_WORDS = 8  # below this many words langdetect is not trusted for Latin script
_ENGLISH_SHARE = 0.1  # share of words that are English function words
_ENGLISH_WORDS = frozenset(
    "the of and to is was are for by from with that this on at it he she they will has have "
    "not be said as than but or who which its their his her were been after before over into "
    "about during also more what when where how why against despite under between through while "
    "because since until upon without within among across could would should might these those "
    "there them your our new says say in".split()
)
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


def _is_latin(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and sum(c.isascii() for c in letters) / len(letters) >= _SCRIPT_SHARE


def _looks_english(text: str) -> bool:
    """Function-word check for English that langdetect mislabels (names, short claims)."""
    words = re.findall(r"[a-z']+", text.lower())
    hits = sum(w in _ENGLISH_WORDS for w in words)
    return hits >= 1 and hits / max(1, len(words)) >= _ENGLISH_SHARE


def detect_language(text: str) -> Language:
    by_script = _script_language(text)
    if by_script is not None:
        return by_script
    try:
        code = detect(text)
    except LangDetectException as exc:
        raise InputError("could not detect a language", code="unsupported_language") from exc
    if code == "en" or (
        _is_latin(text) and (len(text.split()) < _SHORT_WORDS or _looks_english(text))
    ):
        # langdetect is unreliable on very short text ("Indian PM is muslim" -> not English);
        # short Latin-script text is treated as English, the only supported Latin language.
        return "en"
    raise InputError(
        f"unsupported language {code!r}; use en, ta or hi", code="unsupported_language"
    )
