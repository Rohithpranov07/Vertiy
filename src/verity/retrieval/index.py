"""TF-IDF index over (id, text) pairs: scikit-learn vectoriser + cosine similarity."""

import pickle
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from verity.errors import ModelError


class TfidfIndex:
    def __init__(self, ids: list[int], vectorizer: TfidfVectorizer, matrix: object) -> None:
        self.ids = ids
        self._vec = vectorizer
        self._matrix = matrix

    @classmethod
    def build(cls, docs: list[tuple[int, str]]) -> "TfidfIndex":
        ordered = sorted(docs)
        vec = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), sublinear_tf=True)
        if not ordered:
            return cls([], vec, None)
        matrix = vec.fit_transform([t for _, t in ordered])
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
