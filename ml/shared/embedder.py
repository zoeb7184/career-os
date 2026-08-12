"""
ml/shared/embedder.py
──────────────────────
Shared embedding utility — uses fastembed (no PyTorch, ~50MB).
All ML nodes import from here. Never call the model directly.

Model: all-MiniLM-L6-v2 (384 dimensions, runs locally, zero API cost)
"""
from __future__ import annotations
import time
from functools import lru_cache
import numpy as np
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))
from app.logger import get_logger
from app.errors import ServiceUnavailableError

logger = get_logger("embedder")
VECTOR_DIM = 384


@lru_cache(maxsize=1)
def _load_model():
    try:
        from fastembed import TextEmbedding
        logger.info("Loading fastembed model: all-MiniLM-L6-v2")
        start = time.perf_counter()
        model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
        elapsed = round(time.perf_counter() - start, 1)
        logger.info(f"Embedding model loaded in {elapsed}s")
        return model
    except Exception as exc:
        raise ServiceUnavailableError("embedder", {"error": str(exc)})


class Embedder:
    def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            return [0.0] * VECTOR_DIM
        try:
            model = _load_model()
            vectors = list(model.embed([text]))
            return vectors[0].tolist()
        except Exception as exc:
            raise ServiceUnavailableError("embedder", {"error": str(exc)})

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        cleaned = [t.strip() if t and t.strip() else " " for t in texts]
        try:
            model = _load_model()
            vectors = list(model.embed(cleaned))
            return [v.tolist() for v in vectors]
        except Exception as exc:
            raise ServiceUnavailableError("embedder", {"error": str(exc)})

    def embed_chunks(self, text: str, chunk_size: int = 400, overlap: int = 50) -> list[list[float]]:
        words = text.split()
        if len(words) <= chunk_size:
            return [self.embed_text(text)]
        chunks = []
        for i in range(0, len(words), chunk_size - overlap):
            chunks.append(" ".join(words[i: i + chunk_size]))
        vectors = self.embed_batch(chunks)
        mean_vec = np.mean(vectors, axis=0).tolist()
        return [mean_vec]

    @staticmethod
    def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
        a, b = np.array(vec_a), np.array(vec_b)
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    return Embedder()
