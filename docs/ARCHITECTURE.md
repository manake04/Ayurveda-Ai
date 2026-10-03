# Architecture

```
 Browser (React, GitHub Pages)
   │  POST /api/ask/stream  (server-sent events)
   ▼
 FastAPI ── Container (built once at startup, shared by all requests)
   │          ├─ Retriever ── Embedder (Ollama | Gemini) ── FAISS index (data/index/)
   │          │              └─ Reranker (optional, fastembed/ONNX)
   │          ├─ GraphStore (NetworkX, built in memory from corpus/)
   │          ├─ LLMs, in fallback order (Gemini → Ollama qwen3.5)
   │          ├─ RAGPipeline (+ deep-research agent, answer cache)
   │          ├─ BhashiniTranslator (optional)
   │          └─ Store (SQLite: audit log, consents, escalations)
   ├─ /api/ask, /api/ask/stream
   ├─ /api/graph, /api/graph/nodes/{id}/related
   ├─ /api/classify, /api/abs-checklist, /api/tkdl-pointer
   ├─ /api/sources, /api/connectors, /api/consents, /api/escalations
   ├─ /api/privacy/activity  (GET = see my data, DELETE = erase it)
   └─ /api/health, /api/config, /api/corpus/stats
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
8. **Fallback.** Gemini first retries brief failures (429/5xx such as 503 "model is
   experiencing high demand") after 1 s and 3 s. Then models are tried in order
   (`LLM_PROVIDER`, then `LLM_FALLBACK_PROVIDER`). If
   one fails before writing anything, the next one answers. If one fails part-way through, the
   answer switches to quoting the source summaries (`extractive (fallback)`) rather than
   splicing two models' text together. Fallback answers are not cached.
9. **Cache.** Successful answers are cached in memory by normalised question, jurisdiction and
   language, so a repeated question returns instantly with no LLM cost.

`POST /api/ask` runs the same stream to completion and returns one JSON object. The eval and
tests use it.

### Stream protocol

```
event: plan     data: {"steps":[{"question":"...","jurisdictions":["india"]}, ...]}   (deep research only)
event: step     data: {"index":0,"found":{"india":5}}                                 (deep research only)
event: sources  data: {"jurisdiction":"india","confidence":"high","abstained":false,"citations":[...],"related":[...]}
event: delta    data: {"jurisdiction":"india","text":"Section 3(p) excludes "}
event: done     data: {"jurisdiction":"india","answer":"<final, cite-checked text>","generated_by":"gemini:gemini-flash-latest"}
event: end      data: {"latency_ms":1840}
```

## Deep research (agentic mode)

`rag/agent.py`, enabled per question with `mode: "agentic"` ("Deep research" in the UI):

1. **Plan.** One JSON-schema call (`LLM.complete_json`, same fallback order; for Ollama the
   schema is also spelled out in the prompt, since qwen3.5 ignores Ollama's `format`) splits the
   question into at most `AGENTIC_MAX_STEPS` self-contained English sub-questions, each tagged
   with its jurisdictions. A one-step plan, or a failed plan, falls back to standard mode.
2. **Retrieve.** All sub-questions are embedded in one batch call, then searched separately.
3. **Merge.** Per jurisdiction, the confident hits of every sub-question are unioned, keeping
   the best score per document and which sub-question found it, capped at
   `AGENTIC_MAX_SOURCES`.
4. **Answer.** The normal generator writes each jurisdiction's answer, listing only the
   sub-questions tagged with that jurisdiction and marking each source with the part(s) it
   serves. Citation checking, abstention, graph
   expansion and caching all work unchanged.

## Privacy, audit and consent (DPDP)

`store.py` keeps three SQLite tables, all keyed by an anonymous per-browser session id (the
`X-Session-Id` header, a random UUID in localStorage; no accounts):

- **audit_events**: one row per answered question with jurisdiction, mode, language,
  confidence, the model that answered and latency. The question is stored as a SHA-256
  fingerprint and a length, not as text, unless `AUDIT_STORE_QUERY_TEXT=true`.
- **consents**: every grant or withdrawal for a paid database (Manupatra, SCC Online). No paid
  connector is integrated yet; when one is, it must check this table for the session first.
- **escalations**: questions the user chose to send to a human facilitator, with optional
  contact details, only after an explicit consent checkbox.

Users can see everything stored for their browser and delete it (`/api/privacy/activity`).
Rows older than `AUDIT_RETENTION_DAYS` are purged at startup.

## Escalation to a human

Answers marked "Partial match" or declined show "Ask a human IP facilitator". The dialog
creates a ticket (`ESC-XXXXXX`) and, if `ESCALATION_WEBHOOK_URL` is set, POSTs it there (a
helpdesk, Slack or Teams webhook). `ESCALATION_NAME`, `ESCALATION_EMAIL` and `ESCALATION_URL`
add a direct contact; without them the dialog links to IP India.

## Languages and Bhashini

English and Hindi are answered by the LLM directly (`language: auto | en | hi`). When
`BHASHINI_USER_ID`, `BHASHINI_API_KEY` and `BHASHINI_PIPELINE_ID` are set, 11 more Indian
languages appear in the answer-language menu. For those, the question is translated to English,
answered normally, and the final answer is translated back (it arrives whole rather than
streamed). The client follows Bhashini's documented two-step ULCA flow (pipeline config, then
compute). It is covered by mocked tests only, so verify it with real credentials before relying
on it.

## Models and benchmarks

Measured on this corpus with `python -m eval.run_eval` (28 answerable questions including 4 in
Hindi, 7 off-topic), on a 16-core CPU with no GPU:

| Embeddings | Reranker | Top-1 | Top-5 | Off-topic declined | Separation* | Retrieval latency |
|---|---|---|---|---|---|---|
| embeddinggemma | none | 25/28 | 28/28 | 7/7 | 0.48 vs 0.16 | ~150 ms |
| embeddinggemma | MiniLM-L6 cross-encoder | 22/28 | 26/28 | 7/7 | overlapping | +850 ms |
| embeddinggemma | jina multilingual v2 | 27/28 | 28/28 | 7/7 | clean | +6.5 s |
| **qwen3-embedding:8b-q8_0** (default) | none | 26/28 | 28/28 | 1/7 at default threshold | 0.64 vs 0.59 | ~3.5 s (11 s max) |
| qwen3-embedding:0.6b | none | 27/28 | 28/28 | 2/7 at default threshold | 0.54 vs 0.51 | ~240 ms |
| nomic-embed-text | none | 16/28 | 25/28 | — | overlapping | ~110 ms |

\* Lowest score of an answerable question vs. highest score of an off-topic one. A wide gap
is what makes abstention reliable.

Current default: **Qwen3-Embedding-8B**, chosen for its top-1 accuracy. Its costs on CPU are
the ~3.5 s per query and the narrow off-topic margin, which makes abstention more fragile than
with embeddinggemma. On a GPU the latency cost largely disappears.

- **embeddinggemma** is multilingual, small (300M parameters) and fast on CPU, and separates
  answerable from off-topic questions by a wide margin. It's the recommended switch if speed
  matters more than the last point of accuracy.
- **The MiniLM cross-encoder makes results worse** here: it is English-only, so every Hindi
  question fails, and it adds ~0.85 s per query on CPU. The jina multilingual reranker is
  slightly better than no reranker but far too slow on CPU. The reranker stays pluggable for
  a GPU deployment or a larger corpus.
- **Qwen3-Embedding-8B** ranks one more question correctly, but on CPU it takes ~3.5 s per
  query (23x slower) and leaves only a thin margin between answerable and off-topic
  questions, which makes abstention fragile. Worth revisiting on a GPU. Note that the
  `dengcao/Qwen3-Embedding-8B` Ollama build is packaged as completion-only and rejects
  embedding requests; use the official `qwen3-embedding:8b-q8_0` tag.

To try another model, set `EMBEDDING_MODEL` and its prefixes in `backend/.env`, run
`make eval`, and copy the suggested threshold into `CONFIDENCE_ABSTAIN`.

## Running models locally

Everything model-related sits behind two small interfaces: `Embedder` (`retrieval/embeddings.py`)
and `LLM` (`llm/base.py`). To run fully offline, set `LLM_PROVIDER=ollama` and
`OLLAMA_LLM_MODEL` to any chat model you've pulled. Ollama requests always send `think: false`
and `keep_alive: OLLAMA_KEEP_ALIVE` (30 min by default, so large models stay loaded).

On this project's 16-core CPU without a GPU, `qwen3.5` (9.7B, Q4) generates about 4 tokens/s,
so a full answer takes 1-2 minutes. Holding the 8B embedding model (~9.6 GB) and qwen3.5
(~6.6 GB) in memory together needs ~17 GB of free RAM. Small models (under ~4B parameters)
follow the citation format unreliably.

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

- Apart from the in-memory answer cache, the only state is the SQLite store. For more than
  one instance, point the store at a shared database (it's a small module with one class).
  Each instance loads the FAISS index at startup.
- With hosted Gemini models (`EMBEDDING_PROVIDER=gemini`), an instance needs no GPU and no
  model files, which suits free and small hosting tiers.
- Past a few thousand documents: chunk long statutes, move to a FAISS HNSW index, and build
  the index in CI rather than at startup.
