"""Embedding providers. Both return L2-normalised float32 matrices."""

import logging
from collections import OrderedDict
from typing import Protocol

import httpx
import numpy as np

from app.core.config import Settings

log = logging.getLogger(__name__)


class Embedder(Protocol):
    name: str

    async def embed_documents(self, texts: list[str]) -> np.ndarray: ...

    async def embed_query(self, text: str) -> np.ndarray: ...


def _normalise(vectors: np.ndarray) -> np.ndarray:
    vectors = np.asarray(vectors, dtype="float32")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return vectors / np.clip(norms, 1e-12, None)


class _QueryCache:
    """Small LRU so repeated questions don't pay for a second embedding call."""

    def __init__(self, size: int = 512):
        self._size = size
        self._data: OrderedDict[str, np.ndarray] = OrderedDict()

    def get(self, key: str):
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return None

    def put(self, key: str, value: np.ndarray) -> None:
        self._data[key] = value
        self._data.move_to_end(key)
        if len(self._data) > self._size:
            self._data.popitem(last=False)


class OllamaEmbedder:
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.name = f"ollama:{settings.embedding_model}"
        self._model = settings.embedding_model
        self._url = settings.ollama_base_url.rstrip("/") + "/api/embed"
        self._query_prefix = settings.embedding_query_prefix
        self._doc_prefix = settings.embedding_document_prefix
        self._client = client
        self._cache = _QueryCache()

    async def _embed(self, texts: list[str]) -> np.ndarray:
        resp = await self._client.post(self._url, json={"model": self._model, "input": texts}, timeout=600)
        if resp.status_code == 404:
            raise RuntimeError(f"Ollama model '{self._model}' not found. Run: ollama pull {self._model}")
        if resp.status_code != 200:
            # e.g. 501 "this model does not support embeddings" for a chat-only model
            raise RuntimeError(f"Ollama could not embed with '{self._model}': {resp.text[:200]}")
        return _normalise(resp.json()["embeddings"])

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        batches = [texts[i : i + 16] for i in range(0, len(texts), 16)]
        out = [await self._embed([self._doc_prefix + t for t in batch]) for batch in batches]
        return np.vstack(out)

    async def embed_query(self, text: str) -> np.ndarray:
        cached = self._cache.get(text)
        if cached is None:
            cached = (await self._embed([self._query_prefix + text]))[0]
            self._cache.put(text, cached)
        return cached


class GeminiEmbedder:
    """Hosted embeddings for deployments where running Ollama isn't practical."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        if not settings.gemini_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY")
        self.name = f"gemini:{settings.embedding_model}"
        self._model = settings.embedding_model
        self._url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{settings.embedding_model}:batchEmbedContents"
        )
        self._headers = {"x-goog-api-key": settings.gemini_api_key}
        self._client = client
        self._cache = _QueryCache()

    async def _embed(self, texts: list[str], task_type: str) -> np.ndarray:
        requests = [
            {
                "model": f"models/{self._model}",
                "content": {"parts": [{"text": t}]},
                "taskType": task_type,
            }
            for t in texts
        ]
        resp = await self._client.post(
            self._url, json={"requests": requests}, headers=self._headers, timeout=120
        )
        resp.raise_for_status()
        return _normalise([e["values"] for e in resp.json()["embeddings"]])

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        batches = [texts[i : i + 50] for i in range(0, len(texts), 50)]
        return np.vstack([await self._embed(b, "RETRIEVAL_DOCUMENT") for b in batches])

    async def embed_query(self, text: str) -> np.ndarray:
        cached = self._cache.get(text)
        if cached is None:
            cached = (await self._embed([text], "RETRIEVAL_QUERY"))[0]
            self._cache.put(text, cached)
        return cached


def create_embedder(settings: Settings, client: httpx.AsyncClient) -> Embedder:
    if settings.embedding_provider == "gemini":
        return GeminiEmbedder(settings, client)
    return OllamaEmbedder(settings, client)
