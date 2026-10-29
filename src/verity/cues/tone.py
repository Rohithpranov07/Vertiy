"""Sensational-tone cue: 0.5 * naive-Bayes score + 0.5 * style score vs TONE_THRESHOLD."""

import logging
import pickle
import re
from functools import lru_cache
from pathlib import Path

from verity.config import get_settings
from verity.schemas import ToneState

log = logging.getLogger(__name__)

_LEXICON = Path(__file__).resolve().parents[3] / "data" / "tone_lexicon.txt"
MODEL_FILE = "tone_model.pkl"

# style-score structure: weights sum to 1; each component saturates at its cap
W_LEXICON, W_EXCLAIM, W_CAPS = 0.5, 0.25, 0.25
CAP_LEXICON_HITS, CAP_EXCLAMATIONS, CAP_UPPER_RATIO = 2, 3, 0.3
NB_WEIGHT = 0.5


@lru_cache(maxsize=1)
def _lexicon() -> tuple[re.Pattern[str], ...]:
    terms = [
        t.strip().lower()
        for t in _LEXICON.read_text(encoding="utf-8").splitlines()
        if t.strip() and not t.startswith("#")
    ]
    return tuple(re.compile(rf"(?<!\w){re.escape(t)}(?!\w)", re.IGNORECASE) for t in terms)


def style_score(text: str) -> float:
    """Score in [0, 1] from lexicon hits, exclamation marks and upper-case ratio."""
    hits = sum(1 for p in _lexicon() if p.search(text))
    exclaims = text.count("!")
    letters = [c for c in text if c.isalpha()]
    upper = sum(c.isupper() for c in letters) / len(letters) if letters else 0.0
    score = (
        W_LEXICON * min(hits / CAP_LEXICON_HITS, 1.0)
        + W_EXCLAIM * min(exclaims / CAP_EXCLAMATIONS, 1.0)
        + W_CAPS * min(upper / CAP_UPPER_RATIO, 1.0)
    )
    return min(max(score, 0.0), 1.0)


@lru_cache(maxsize=4)
def _load_model(path: str) -> tuple[object, object] | None:
    p = Path(path)
    if not p.exists():
        return None
    with p.open("rb") as fh:
        loaded: tuple[object, object] = pickle.load(fh)  # noqa: S301 - our own artifact
    return loaded


_warned = False


def reset_model_cache() -> None:
    global _warned
    _warned = False
    _load_model.cache_clear()


def nb_score(text: str, model_path: Path | None = None) -> float | None:
    """P(false-style) from the trained naive Bayes model, or None if no model exists."""
    path = model_path or (get_settings().index_dir / MODEL_FILE)
    model = _load_model(str(path))
    if model is None:
        return None
    vectorizer, nb = model
    x = vectorizer.transform([text])  # type: ignore[attr-defined]
    classes = list(nb.classes_)  # type: ignore[attr-defined]
    proba = nb.predict_proba(x)[0]  # type: ignore[attr-defined]
    return float(proba[classes.index("false")])


def tone_score(text: str, model_path: Path | None = None) -> float:
    style = style_score(text)
    nb = nb_score(text, model_path)
    if nb is None:
        global _warned
        if not _warned:
            log.warning("no trained tone model; using the style score alone")
            _warned = True
        return style
    return NB_WEIGHT * nb + (1 - NB_WEIGHT) * style


def tone(text: str, model_path: Path | None = None) -> ToneState:
    return "high" if tone_score(text, model_path) >= get_settings().tone_threshold else "low"
