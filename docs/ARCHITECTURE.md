# Architecture

```
 Browser (React, GitHub Pages)
   │  POST /api/ask/stream  (server-sent events)
   ▼
 FastAPI ── Container (built once at startup, shared by all requests)
   │          ├─ Retriever ── Embedder (Ollama | Gemini) ── FAISS index (data/index/)
   │          │              └─ Reranker (optional, fastembed/ONNX)
   │          ├─ GraphStore (NetworkX, built in memory from corpus/)
   │          ├─ LLM (Gemini | Ollama | none)
   │          └─ RAGPipeline (+ answer cache)
   ├─ /api/ask, /api/ask/stream
   ├─ /api/graph, /api/graph/nodes/{id}/related
   ├─ /api/classify, /api/abs-checklist, /api/tkdl-pointer
   └─ /api/health, /api/corpus/stats
```

## Request flow

1. **Embed once.** The question is embedded a single time (cached per question text), even
   when both jurisdictions are requested.
2. **Search.** FAISS returns every document ranked by cosine similarity. With 45 documents an
   exact flat index costs well under a millisecond; switch to HNSW past ~100k chunks.
3. **Split by jurisdiction.** The ranking is partitioned into India and International, and the
   top 5 of each are kept. The two are never merged.
4. **Rerank (optional).** If `RERANKER_MODEL` is set, a cross-encoder rescores the top
   candidates. Off by default; see the benchmarks below.
5. **Confidence.** The best score decides `high`, `medium` or `low`. `low` means the assistant
   declines without calling the LLM. Thresholds are model-specific and tuned with the eval.
6. **Stream.** The `sources` event (citations, confidence, related documents) is sent before
   generation starts, so the UI shows sources immediately. Text then arrives as `delta`
   events. For "Both", the two jurisdictions generate concurrently and their events interleave.
7. **Cite-check.** The model sees only the retrieved documents, numbered `[1]..[n]`, and is
   told to cite every factual sentence. Any `[n]` outside that range is removed before the
   final `done` event, so the UI cannot show a citation to something that wasn't retrieved.
8. **Fallback.** If the LLM fails (bad key, quota, network), the answer falls back to quoting
   the source summaries, marked `extractive (fallback)`. Fallback answers are not cached.
9. **Cache.** Successful answers are cached in memory by normalised question, jurisdiction and
   language, so a repeated question returns instantly with no LLM cost.

`POST /api/ask` runs the same stream to completion and returns one JSON object. The eval and
tests use it.

### Stream protocol

```
event: sources  data: {"jurisdiction":"india","confidence":"high","abstained":false,"citations":[...],"related":[...]}
event: delta    data: {"jurisdiction":"india","text":"Section 3(p) excludes "}
event: done     data: {"jurisdiction":"india","answer":"<final, cite-checked text>","generated_by":"gemini:gemini-flash-latest"}
event: end      data: {"latency_ms":1840}
```

## Models and benchmarks

Measured on this corpus with `python -m eval.run_eval` (28 answerable questions including 4 in
Hindi, 7 off-topic), on a 16-core CPU with no GPU:

| Embeddings | Reranker | Top-1 | Top-5 | Off-topic declined | Separation* | Retrieval latency |
|---|---|---|---|---|---|---|
| **embeddinggemma** (default) | none | 25/28 | 28/28 | 7/7 | 0.48 vs 0.16 | ~150 ms |
| embeddinggemma | MiniLM-L6 cross-encoder | 22/28 | 26/28 | 7/7 | overlapping | +850 ms |
| embeddinggemma | jina multilingual v2 | 27/28 | 28/28 | 7/7 | clean | +6.5 s |
| qwen3-embedding:0.6b | none | 27/28 | 28/28 | 2/7 at default threshold | 0.54 vs 0.51 | ~240 ms |
| nomic-embed-text | none | 16/28 | 25/28 | — | overlapping | ~110 ms |

\* Lowest score of an answerable question vs. highest score of an off-topic one. A wide gap
is what makes abstention reliable.

Conclusions behind the defaults:

- **embeddinggemma** is multilingual, small (300M parameters) and fast on CPU, and separates
  answerable from off-topic questions by a wide margin.
- **The MiniLM cross-encoder makes results worse** here: it is English-only, so every Hindi
  question fails, and it adds ~0.85 s per query on CPU. The jina multilingual reranker is
  slightly better than no reranker but far too slow on CPU. The reranker stays pluggable for
  a GPU deployment or a larger corpus.
- The `dengcao/Qwen3-Embedding-8B` Ollama build is packaged as a completion-only model and
  rejects embedding requests; use the official `qwen3-embedding:*` tags instead.

To try another model, set `EMBEDDING_MODEL` and its prefixes in `backend/.env`, run
`make eval`, and copy the suggested threshold into `CONFIDENCE_ABSTAIN`.

## Running models locally

Everything model-related sits behind two small interfaces: `Embedder` (`retrieval/embeddings.py`)
and `LLM` (`llm/base.py`). To run fully offline, set `LLM_PROVIDER=ollama` and
`OLLAMA_LLM_MODEL` to any chat model you've pulled (e.g. `qwen3:8b`, `gemma3:12b`). Nothing
else changes. Note that small models (under ~4B parameters) follow the citation format
unreliably, and CPU-only generation takes tens of seconds per answer.

## Knowledge graph

`knowledge/graph.py` builds a NetworkX multigraph at startup (a few milliseconds):

- **document** nodes, one per corpus entry;
- **regime**, **jurisdiction** and **category** nodes, derived automatically from the corpus
  and the classifier tree so they can't drift out of sync;
- **institution** nodes and document-to-document relations (`SUPPORTS`, `ENFORCES`,
  `ANALOGOUS_TO`, ...), hand-authored in `corpus/graph_edges.json`.

After retrieval, documents linked to the top two hits by an answer-relevant relation are
returned as "Also relevant". This surfaces requirements that apply together but share no
wording with the question.

## Guided tools

- **Formulation classifier** (`domain/classifier.py`): a stateless yes/no decision tree. The
  client sends all answers so far; the server returns the next question or the result.
- **ABS checklist** (`domain/abs_checklist.py`): turns six facts into the access-and-benefit-
  sharing duties that likely apply, each with its corpus sources.
- **Prior-art pointer** (`domain/tkdl.py`): TKDL is only open to patent examiners, so this
  explains that and links to public patent databases. It does not pretend to search TKDL.

## Configuration

All settings live in `core/config.py` and are read from `backend/.env`; see
`backend/.env.example`. The important ones: `LLM_PROVIDER`, `GEMINI_API_KEY`, `GEMINI_MODEL`,
`EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `CONFIDENCE_HIGH`, `CONFIDENCE_ABSTAIN`,
`RERANKER_MODEL`, `CORS_ORIGINS`.

## Scaling notes

- The backend is stateless apart from the in-memory answer cache, so it scales horizontally.
  Each instance loads the index (~140 KB) at startup.
- With hosted Gemini models (`EMBEDDING_PROVIDER=gemini`), an instance needs no GPU and no
  model files, which suits free and small hosting tiers.
- Past a few thousand documents: chunk long statutes, move to a FAISS HNSW index, and build
  the index in CI rather than at startup.
