"""TF-IDF index over (id, text) pairs: scikit-learn vectoriser + cosine similarity."""

import pickle
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from verity.errors import ModelError


def _vectorizer(stop_words: str | None) -> TfidfVectorizer:
    """Stop words are dropped: shared function words ("the", "is", "in") made unrelated claims
    look similar and produced wrong matches (swept on held-out published fact-checks)."""
    return TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), sublinear_tf=True, stop_words=stop_words
    )


class TfidfIndex:
    def __init__(self, ids: list[int], vectorizer: TfidfVectorizer, matrix: object) -> None:
        self.ids = ids
        self._vec = vectorizer
        self._matrix = matrix

    @classmethod
    def build(cls, docs: list[tuple[int, str]]) -> "TfidfIndex":
        ordered = sorted(docs)
        vec = _vectorizer(stop_words="english")
        if not ordered:
            return cls([], vec, None)
        texts = [t for _, t in ordered]
        try:
            matrix = vec.fit_transform(texts)
        except ValueError:  # every document is only stop words: keep them rather than fail
            vec = _vectorizer(stop_words=None)
            matrix = vec.fit_transform(texts)
        return cls([i for i, _ in ordered], vec, matrix)

    def __len__(self) -> int:
        return len(self.ids)

    def search(self, query: str, k: int) -> list[tuple[int, float]]:
        """Top-k best-first: descending cosine similarity, ties by ascending id."""
        if not self.ids or self._matrix is None or not query.strip():
            return []
        q = self._vec.transform([query])
        # rows are L2-normalised, so the dot product is the cosine similarity
        sims = np.asarray((self._matrix @ q.T).todense()).ravel()
        ranked = sorted(zip(self.ids, sims.tolist(), strict=True), key=lambda t: (-t[1], t[0]))
        return [(i, s) for i, s in ranked[:k] if s > 0.0]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            pickle.dump((self.ids, self._vec, self._matrix), fh)

    @classmethod
    def load(cls, path: Path) -> "TfidfIndex":
        if not path.exists():
            raise ModelError(f"index not found: {path}", code="index_missing")
        with path.open("rb") as fh:
            ids, vec, matrix = pickle.load(fh)  # noqa: S301 - our own artifact under INDEX_DIR
        return cls(ids, vec, matrix)
