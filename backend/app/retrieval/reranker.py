"""Optional cross-encoder reranker (ONNX via fastembed -- no PyTorch).

Off by default: on this corpus the English-only MiniLM cross-encoder lowered top-1
accuracy (it can't read Hindi queries) and added ~0.8 s per query on CPU. To try it:
`pip install fastembed`, set RERANKER_MODEL (e.g. `Xenova/ms-marco-MiniLM-L-6-v2`) and
compare with `python -m eval.run_eval`.
"""

from typing import Protocol


class Reranker(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...


class CrossEncoderReranker:
    def __init__(self, model_name: str):
        from fastembed.rerank.cross_encoder import TextCrossEncoder  # heavy import, only if used

        self.model_name = model_name
        self._model = TextCrossEncoder(model_name)

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in self._model.rerank(query, texts)]
