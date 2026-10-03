"""Shared fixtures. Tests use deterministic fake models, so they need no Ollama or API key."""

import hashlib
import re
from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np
import pytest

from app.core.config import Settings
from app.knowledge.graph import GraphStore
from app.llm import LLMError
from app.rag.pipeline import RAGPipeline
from app.retrieval.corpus import load_corpus
from app.retrieval.retriever import Retriever
from app.retrieval.vector_store import VectorStore

ROOT = Path(__file__).resolve().parents[2]
CORPUS_DIR = ROOT / "corpus"
GRAPH_EDGES = CORPUS_DIR / "graph_edges.json"


class FakeEmbedder:
    """Hashed bag-of-words: similar wording -> similar vectors. Good enough to test plumbing."""

    name = "fake:bow"
    dim = 512

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype="float32")
        for token in re.findall(r"\w{3,}", text.lower()):
            v[int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim] += 1.0
        n = np.linalg.norm(v)
        return v / n if n else v

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts])

    async def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)

    async def embed_queries(self, texts: list[str]) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts])


class FakeLLM:
    def __init__(
        self,
        chunks=("Section 3(p) bars this ", "[1]. ", "Also see [9]."),
        fail=False,
        fail_after_first_chunk=False,
        plan=None,
        name="fake:llm",
    ):
        self.chunks, self.fail, self.fail_after_first_chunk = chunks, fail, fail_after_first_chunk
        self.plan, self.name = plan, name
        self.calls, self.prompts = 0, []

    async def stream(self, system: str, prompt: str) -> AsyncIterator[str]:
        self.calls += 1
        self.prompts.append((system, prompt))
        if self.fail:
            raise LLMError("quota exceeded")
        for i, chunk in enumerate(self.chunks):
            if i == 1 and self.fail_after_first_chunk:
                raise LLMError("connection dropped")
            yield chunk

    async def complete_json(self, system: str, prompt: str, schema: dict) -> dict:
        if self.fail or self.plan is None:
            raise LLMError("no plan")
        return self.plan


@pytest.fixture(scope="session")
def docs():
    return load_corpus(CORPUS_DIR)


@pytest.fixture(scope="session")
def settings():
    # Thresholds suited to the bag-of-words fake embedder.
    return Settings(_env_file=None, confidence_high=0.35, confidence_abstain=0.12, llm_provider="none")


@pytest.fixture(scope="session")
def embedder():
    return FakeEmbedder()


@pytest.fixture(scope="session")
async def store(docs, embedder):
    return await VectorStore.build(docs, embedder)


@pytest.fixture(scope="session")
def graph(docs):
    return GraphStore.build(docs, GRAPH_EDGES)


@pytest.fixture
def retriever(settings, store, embedder):
    return Retriever(settings, store, embedder)


@pytest.fixture
def make_pipeline(settings, retriever, graph):
    def _make(llm=None, translator=None):
        llms = llm if isinstance(llm, list) else ([llm] if llm else [])
        return RAGPipeline(settings, retriever, graph, llms, translator)

    return _make
