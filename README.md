# IP-SAKTI Sahayak

[![CI/CD](https://github.com/manake04/Ayurveda-Ai/actions/workflows/ci.yml/badge.svg)](https://github.com/manake04/Ayurveda-Ai/actions/workflows/ci.yml)

**A source-cited AI assistant for intellectual-property and regulatory questions about
Ayurvedic products, covering Indian and international regimes.**

Built for Smart India Hackathon 2026, problem statement 26045.

- **Cited answers.** Every answer is generated from a curated corpus of statutes, rules and
  treaties, with numbered citations linking to the primary source. If nothing relevant is
  found, the assistant declines instead of guessing.
- **India and International kept separate.** Choose India, International or Both. Both shows
  two independent answers, never a merged one.
- **Deep research.** For multi-part questions, the model first splits the question into
  sub-questions, searches each one, then answers part by part with citations.
- **Multilingual.** Ask in English or Hindi and get the answer in the same language. Other
  Indian languages go through Bhashini translation when credentials are configured.
- **Human escalation.** Low-confidence and declined answers offer a hand-off to a human IP
  facilitator, with explicit consent and a ticket number.
- **Privacy by design (DPDP).** Anonymous per-browser sessions; the audit log keeps a
  fingerprint of each question, not its text; users can view and delete their records;
  paid databases can only ever be used with logged, revocable consent.
- **Guided tools.** A formulation classifier (classical, proprietary, phytopharmaceutical,
  Ayurveda Aahara...), an access-and-benefit-sharing checklist, a prior-art search guide,
  links to the official databases, and a browsable knowledge graph of how the laws connect.

> Information, not legal advice. Verify against the cited source and consult a registered
> IP professional before acting.

## Quick start

Requires Python 3.11+, Node 18+ and [Ollama](https://ollama.com).

```bash
make setup            # venv + pip, npm install, backend/.env, pulls the Ollama models
# add your key from https://aistudio.google.com/apikey to backend/.env:  GEMINI_API_KEY=...
make api              # API on http://127.0.0.1:8000   (terminal 1)
make web              # UI  on http://localhost:5173   (terminal 2)
```

Models (all configurable in `backend/.env`):

| Role | Default | Notes |
|---|---|---|
| Answers | Gemini `gemini-flash-latest`, thinking off | |
| Fallback answers | Ollama `qwen3.5:latest`, thinking off | used if Gemini fails before answering |
| Embeddings | Ollama `qwen3-embedding:8b-q8_0` | ~3.5 s per query on CPU; `embeddinggemma` is ~150 ms |

The first API start embeds the corpus and writes the FAISS index to `backend/data/index/`;
later starts load it instantly. The index rebuilds itself if the corpus or the embedding model
changes. With no LLM available at all, the app still answers by quoting source summaries.

Other tasks: `make test`, `make lint`, `make eval`, `make build`. Run `make` to list them.

## How it works

```
question ─► embed (Ollama) ─► FAISS search ─► split by jurisdiction ─► confidence check
                                                                         │
                                       low ◄──────────────────────────────┤
                                  "no reliable source"                    │ ok
                                                                          ▼
           UI ◄── SSE: sources first, then answer text ◄── Gemini (or local Ollama model)
                                                           sees only the numbered sources
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design, the configuration
options and the model benchmarks behind the defaults.

| Layer | Choice |
|---|---|
| UI | React 18, Vite, Tailwind CSS, streamed over server-sent events |
| API | FastAPI, async, one process |
| Answers | Gemini, falling back to a local Ollama model (both with thinking off) |
| Embeddings | Ollama (`qwen3-embedding:8b-q8_0`), or Gemini embeddings for hosted deployments |
| Vector search | FAISS (exact inner product over normalised vectors) |
| Reranker | Optional cross-encoder via fastembed/ONNX, off by default (see benchmarks) |
| Knowledge graph | NetworkX, built in memory at startup from `corpus/` |
| Audit / consent / escalations | SQLite (`backend/data/app.db`), stdlib only |
| Translation | Bhashini ULCA pipeline (optional) |

## Project layout

```
backend/
  app/
    main.py            FastAPI app factory; all routes live under /api
    core/              settings (.env) and the service container built at startup
    api/routes/        ask (JSON + streaming), graph, tools, health
    rag/               the pipeline (retrieve → generate → cite), deep-research agent, prompts
    retrieval/         corpus loading, embedders, FAISS store, retriever, reranker
    llm/               Gemini and Ollama clients behind one interface, fallback order
    i18n/              answer languages and the Bhashini translator
    store.py           audit log, consents, escalations (SQLite)
    knowledge/         knowledge graph
    domain/            classifier tree, ABS checklist, TKDL pointer, source registry
    schemas/           request/response models
  tests/               run without any model or API key (fake embedder + LLM)
  eval/                retrieval and abstention eval against the real models
frontend/src/
  components/          chat, tools, graph, layout, ui
  hooks/useChat.js     conversation state + streaming
  lib/                 API client, EN/HI strings
corpus/                curated documents (india.json, international.json) + graph edges
```

## Evaluation

```bash
make eval                     # retrieval accuracy, abstention, score ranges, latency
cd backend && .venv/bin/python -m eval.run_eval --llm   # also checks generated citations
```

The eval set (`backend/eval/eval_set.jsonl`) has 28 answerable questions, 4 of them in Hindi,
7 off-topic ones the assistant must decline, and 3 multi-part questions for deep research
(run with `--llm`). Results for each embedding model are in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#models-and-benchmarks).

## Deployment

One GitHub Actions workflow lints and tests the backend, builds the UI, and on `main`
publishes it to GitHub Pages. One-time setup:

1. **Pages:** Settings → Pages → Source: **GitHub Actions**.
2. **API on Render:** New → Blueprint → this repo (`render.yaml`). Set `GEMINI_API_KEY` in the
   Render dashboard, and `CORS_ORIGINS` to your Pages origin (`https://<user>.github.io`).
   Render can't run Ollama, so the hosted API uses Gemini embeddings; run `make eval` locally
   with the same settings to pick its confidence thresholds.
3. **Connect them:** Settings → Secrets and variables → Actions → Variables:
   `VITE_API_BASE_URL` = the Render URL. Re-run the workflow.

Render's free tier sleeps after 15 minutes idle, so the first request after a pause takes
30-60 s. A paid instance or an uptime ping on `/api/health` avoids that.

## License

MIT. Corpus entries summarise public government and treaty texts; see each entry's
`source_url`.
