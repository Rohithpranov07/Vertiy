"""Stage 2: isolate the checkable claim (spaCy + regex; no LLM, no network)."""

import re
from functools import lru_cache
from pathlib import Path

import spacy
from spacy.language import Language as SpacyModel

from verity.config import get_settings
from verity.errors import ModelError
from verity.schemas import ClaimRecord, ClaimSignals, ExtractedClaim, PreparedText

_TRIGGER_FILE = Path(__file__).resolve().parents[3] / "data" / "claim_triggers.txt"
_CTA_FILE = Path(__file__).resolve().parents[3] / "data" / "cta_phrases.txt"
_MODEL = "en_core_web_sm"

_NUMBER = re.compile(
    r"(?:(?:rs\.?|inr|₹|\$|usd)\s*)?\d[\d,]*(?:\.\d+)?"
    r"(?:\s*(?:%|lakh|lakhs|crore|crores|million|billion|thousand|k)\b)?",
    re.IGNORECASE,
)
_DATE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b",
    re.IGNORECASE,
)
_TLDS = "com|in|org|net|gov|edu|co|int|io|info|me|ly|gl|app|xyz|top|tk|cc|us|uk"
_URL = re.compile(
    r"https?://[^\s<>\"']+|www\.[^\s<>\"']+"
    rf"|(?<![@\w.-])(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+(?:{_TLDS})(?:/[^\s<>\"']*)?(?![\w@])",
    re.IGNORECASE,
)
_TRAILING = ".,;:!?)]}'\""
_PERSON_ORG = {"PERSON", "ORG"}
_DATE_LABELS = {"DATE", "TIME"}
_PLACE = {"GPE", "LOC", "FAC"}
_NUMERIC_LABELS = {"CARDINAL", "ORDINAL", "MONEY", "PERCENT", "QUANTITY", "DATE", "TIME"}


@lru_cache(maxsize=1)
def _nlp() -> SpacyModel:
    try:
        return spacy.load(_MODEL, disable=["lemmatizer"])
    except OSError as exc:
        raise ModelError(
            f"spaCy model {_MODEL} missing; run: python -m spacy download {_MODEL}",
            code="spacy_model_missing",
        ) from exc


@lru_cache(maxsize=1)
def _triggers() -> tuple[re.Pattern[str], ...]:
    words = [
        w.strip().lower()
        for w in _TRIGGER_FILE.read_text(encoding="utf-8").splitlines()
        if w.strip() and not w.startswith("#")
    ]
    return tuple(re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE) for w in words)


@lru_cache(maxsize=1)
def _ctas() -> tuple[re.Pattern[str], ...]:
    words = [
        w.strip().lower()
        for w in _CTA_FILE.read_text(encoding="utf-8").splitlines()
        if w.strip() and not w.startswith("#")
    ]
    return tuple(re.compile(rf"\b{re.escape(w)}\b", re.IGNORECASE) for w in words)


def _links(text: str) -> list[str]:
    out: list[str] = []
    for m in _URL.finditer(text):
        link = m.group(0).rstrip(_TRAILING)
        if link and link not in out:
            out.append(link)
    return out


def _numbers(text: str) -> list[str]:
    nums: list[str] = []
    for m in _NUMBER.finditer(text):
        n = m.group(0).strip().rstrip(",")
        if n and n not in nums:
            nums.append(n)
    return nums


def score_sentence(text: str, has_entity: bool) -> int:
    """Check-worthiness: +1 number, +1 named entity, +1 trigger word."""
    score = 1 if re.search(r"\d", text) else 0
    score += 1 if has_entity else 0
    score += 1 if any(p.search(text) for p in _triggers()) else 0
    if any(p.search(text) for p in _ctas()):
        score -= get_settings().claim_cta_penalty
    return score


def ranked_sentences(prepared: PreparedText) -> list[str]:
    """Every sentence of the message, most check-worthy first (ties: longer, then earlier)."""
    text = prepared.english.strip()
    doc = _nlp()(text) if text else None
    sents = [s for s in doc.sents if s.text.strip()] if doc is not None else []
    order = sorted(
        enumerate(sents),
        key=lambda t: (
            -score_sentence(t[1].text, bool(t[1].ents)),
            -len(t[1].text.strip()),
            t[0],
        ),
    )
    return [s.text.strip() for _, s in order]


def extract_claim(prepared: PreparedText) -> ExtractedClaim:
    """Extract the claim sentence plus entities, numbers, links and signals.

    The claim sentence is chosen by check-worthiness (ties: longer, then earlier).
    Entities, numbers, links and signals are taken from the whole message, since a
    link or date often sits outside the claim sentence.
    """
    text = prepared.english.strip()
    doc = _nlp()(text) if text else None
    sents = [s for s in doc.sents if s.text.strip()] if doc is not None else []

    if sents:
        best = max(
            enumerate(sents),
            key=lambda t: (
                score_sentence(t[1].text, bool(t[1].ents)),
                len(t[1].text.strip()),
                -t[0],
            ),
        )[1]
        claim_text = best.text.strip()
    else:
        claim_text = text[: get_settings().claim_max_chars]

    ents = list(doc.ents) if doc is not None else []
    entities: list[str] = []
    for e in ents:
        if e.label_ not in _NUMERIC_LABELS - _DATE_LABELS and e.text not in entities:
            entities.append(e.text.strip())
    labels = {e.label_ for e in ents}
    links = _links(text)
    signals = ClaimSignals(
        has_person_org=bool(labels & _PERSON_ORG),
        has_date=bool(labels & _DATE_LABELS) or bool(_DATE.search(text)),
        has_place=bool(labels & _PLACE),
        has_link=bool(links),
    )
    return ExtractedClaim(
        claim=ClaimRecord(text=claim_text, entities=entities, numbers=_numbers(text), links=links),
        signals=signals,
    )
