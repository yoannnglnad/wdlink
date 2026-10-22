"""Sentence embeddings with an in-memory cache (contexts and candidate cards repeat a lot)."""

import numpy as np
from sentence_transformers import SentenceTransformer

from wdlink import config


class Embedder:
    def __init__(self, model_name: str = config.EMBEDDING_MODEL):
        self.model = SentenceTransformer(model_name)
        self.cache: dict[str, np.ndarray] = {}

    def encode(self, texts: list[str]) -> np.ndarray:
        missing = [t for t in dict.fromkeys(texts) if t not in self.cache]
        if missing:
            vectors = self.model.encode(
                missing, batch_size=config.EMBEDDING_BATCH, normalize_embeddings=True
            )
            self.cache.update(zip(missing, vectors, strict=True))
        return np.stack([self.cache[t] for t in texts]) if texts else np.zeros((0, 0))

    def similarity(self, a: str, b: str) -> float:
        va, vb = self.encode([a, b])
        return float(np.dot(va, vb))
