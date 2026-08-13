"""Local-embedding policy→industry linking (optional, lazy-loaded).

Uses a local multilingual sentence-transformer to map policy text to industry
index names via cosine similarity.  This is the *association layer* for
policy-level event studies; it never feeds a strategy ranker.

The model is loaded lazily and cached to ``data/ai_corpus/embeddings/`` so the
120MB download happens once.  When the model is unavailable (offline / not
installed), callers should fall back to ``link_policy_events(model=None)``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


class EmbeddingLinker:
    """Lazy wrapper around a sentence-transformers model with a disk cache."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        *,
        cache_dir: str | Path = "data/ai_corpus/embeddings",
        root: Path | None = None,
    ) -> None:
        self.model_name = model_name
        self.cache_path = Path(cache_dir)
        if root is not None and not self.cache_path.is_absolute():
            self.cache_path = root / self.cache_path
        self._model = None
        self._cache: dict[str, list[float]] = {}

    def _load_cache(self) -> None:
        cache_file = self.cache_path / f"{self.model_name}.json"
        if cache_file.is_file():
            try:
                self._cache = json.loads(cache_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save_cache(self) -> None:
        self.cache_path.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_path / f"{self.model_name}.json"
        cache_file.write_text(
            json.dumps(self._cache, ensure_ascii=False), encoding="utf-8"
        )

    def _ensure_model(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self._load_cache()
        return self._model

    @property
    def available(self) -> bool:
        try:
            import sentence_transformers  # noqa: F401

            return True
        except ImportError:
            return False

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts to vectors, using the disk cache when possible."""
        if not self.available:
            raise RuntimeError(
                "sentence-transformers is not installed; use link_policy_events(model=None)"
            )
        model = self._ensure_model()
        if not self._cache:
            self._load_cache()
        vectors: list[list[float]] = []
        for text in texts:
            key = text.strip()
            if key in self._cache:
                vectors.append(self._cache[key])
            else:
                vec = model.encode([key])[0].tolist()
                self._cache[key] = vec
                vectors.append(vec)
        if texts:
            self._save_cache()
        return vectors
