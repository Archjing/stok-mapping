"""oMLX (Apple Silicon MLX) embedding linker — HTTP client, no torch.

Talks to a local oMLX server's OpenAI-compatible ``POST /v1/embeddings`` endpoint
over HTTP, so the heavy model runs on the Mac host and this VM only sends text
and receives vectors.  Exposes the same ``encode(list[str]) -> list[list[float]]``
interface as ``EmbeddingLinker``, so ``link_policy_events(model=...)`` works
unchanged.

Config via environment variables (no secrets in code):
- ``OMLX_API_KEY``  (required) — Bearer token
- ``OMLX_BASE_URL`` (default ``http://172.16.10.254:8000``)
- ``OMLX_EMBEDDING_MODEL`` (default ``mlx-community/bge-m3-mlx-fp16``)
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

DEFAULT_BASE_URL = os.environ.get("OMLX_BASE_URL", "http://172.16.10.254:8000")
DEFAULT_MODEL = os.environ.get("OMLX_EMBEDDING_MODEL", "mlx-community/bge-m3-mlx-fp16")


class OmlxEmbeddingLinker:
    """HTTP client for an oMLX embedding model with a disk cache."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        cache_dir: str | Path = "data/ai_corpus/embeddings",
        root: Path | None = None,
        timeout: int = 60,
    ) -> None:
        self.api_key = api_key or os.environ.get("OMLX_API_KEY", "")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.cache_path = Path(cache_dir)
        if root is not None and not self.cache_path.is_absolute():
            self.cache_path = root / self.cache_path
        self._cache: dict[str, list[float]] = {}
        self._load_cache()

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _load_cache(self) -> None:
        cache_file = self.cache_path / "omlx_embeddings.json"
        if cache_file.is_file():
            try:
                self._cache = json.loads(cache_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._cache = {}

    def _save_cache(self) -> None:
        self.cache_path.mkdir(parents=True, exist_ok=True)
        cache_file = self.cache_path / "omlx_embeddings.json"
        cache_file.write_text(
            json.dumps(self._cache, ensure_ascii=False), encoding="utf-8"
        )

    def _embed_remote(self, texts: list[str]) -> list[list[float]]:
        if not self.api_key:
            raise RuntimeError("OMLX_API_KEY is not set")
        resp = requests.post(
            f"{self.base_url}/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        payload: dict[str, Any] = resp.json()
        data = payload.get("data", [])
        data = sorted(data, key=lambda d: d.get("index", 0))
        return [list(d["embedding"]) for d in data]

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts to vectors, using the disk cache when possible."""
        if not texts:
            return []
        missing = [t for t in texts if t.strip() not in self._cache]
        if missing:
            vectors = self._embed_remote(missing)
            for text, vec in zip(missing, vectors):
                self._cache[text.strip()] = vec
            self._save_cache()
        return [self._cache[t.strip()] for t in texts]
