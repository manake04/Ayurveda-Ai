# IP-SAKTI Sahayak

[![CI/CD](https://github.com/manake04/Ayurveda-Ai/actions/workflows/ci.yml/badge.svg)](https://github.com/manake04/Ayurveda-Ai/actions/workflows/ci.yml)

A source-cited AI assistant for intellectual-property and regulatory questions about Ayurvedic
products, covering Indian and international regimes. Built for Smart India Hackathon 2026
(problem statement 26045, Ministry of Ayush).

> Information, not legal advice. Every answer links to the provision it relies on; verify it
> and consult a registered IP professional before acting.

## Features

- **Cited answers** grounded in a curated corpus of statutes, rules and treaties. If no source
  is relevant enough, the assistant declines instead of guessing.
- **India / International / Both**, always answered separately, never merged.
- **Deep research** splits multi-part questions into sub-questions, searches each, and answers
  part by part.
- **Multilingual**: English and Hindi natively; other Indian languages via Bhashini.
- **Guided tools**: formulation classifier, access-and-benefit-sharing checklist, prior-art
  guide, knowledge-graph explorer and links to official databases.
- **Human escalation** to an IP facilitator, with explicit consent.
- **Privacy by design (DPDP)**: anonymous sessions, no question text in the audit log,
  view/delete-my-data, logged consent for paid databases.

## Architecture

```
React UI ──SSE──► FastAPI ──► embed (Ollama) ──► FAISS search ──► confidence check
                     │                                                  │
                     │                    declined ◄──── low ──────────┤
                     ▼                                                  ▼ ok
              SQLite (audit,          Gemini ──fallback──► qwen3.5 (Ollama)
              consent, tickets)       sees only the numbered sources; citations are checked
```

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS |
| API | FastAPI (async, server-sent events) |
| LLM | Gemini `gemini-flash-latest`, fallback Ollama `qwen3.5` (thinking off) |
| Retrieval | Ollama `qwen3-embedding:8b-q8_0` + FAISS |
| Knowledge graph | NetworkX, built in memory from the corpus |
| Storage | SQLite (stdlib) for audit log, consents, escalations |

Design details, model benchmarks and the streaming protocol are in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Getting started

**Prerequisites:** Python 3.11+, Node 18+, [Ollama](https://ollama.com), and a
[Gemini API key](https://aistudio.google.com/apikey).

```bash
make setup                         # dependencies, backend/.env, Ollama models
# set GEMINI_API_KEY in backend/.env
make api                           # http://127.0.0.1:8000
make web                           # http://localhost:5173
```

The first start embeds the corpus into a FAISS index; it rebuilds automatically when the
corpus or embedding model changes.

## Configuration

All settings live in `backend/.env`; see [`backend/.env.example`](backend/.env.example).

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Required for Gemini answers |
| `LLM_PROVIDER`, `LLM_FALLBACK_PROVIDER` | `gemini`, `ollama` or `none` |
| `EMBEDDING_MODEL`, `CONFIDENCE_ABSTAIN` | Retrieval model and its decline threshold |
| `ESCALATION_EMAIL`, `ESCALATION_WEBHOOK_URL` | Where facilitator requests go |
| `BHASHINI_USER_ID`, `BHASHINI_API_KEY`, `BHASHINI_PIPELINE_ID` | Extra languages |

## Development

| Command | Description |
|---|---|
| `make test` | Backend tests (no models or keys needed) |
| `make lint` | Ruff lint and format check |
| `make eval` | Retrieval accuracy, abstention and latency on the eval set |
| `make build` | Production build of the UI |

```
backend/app/
  api/        HTTP routes          rag/        pipeline, deep-research agent, prompts
  core/       settings, startup    retrieval/  corpus, embeddings, FAISS, retriever
  llm/        Gemini, Ollama       knowledge/  knowledge graph
  domain/     classifier, ABS,     i18n/       languages, Bhashini
              TKDL, sources        store.py    audit, consent, escalations
frontend/src/ components, hooks, API client, EN/HI strings
corpus/       curated provisions (see corpus/README.md)
```

## Deployment

CI lints and tests the backend, builds the UI, and publishes it to GitHub Pages from `main`.

1. **Pages:** Settings → Pages → Source: *GitHub Actions*.
2. **API:** deploy to Render with [`render.yaml`](render.yaml). Set `GEMINI_API_KEY` and
   `CORS_ORIGINS`. The hosted API uses Gemini embeddings, as Render can't run Ollama.
3. **Connect:** add the repository variable `VITE_API_BASE_URL` with the API URL.

## Roadmap

- Verified corpus entries for missing regimes (e.g. EU trade marks / EUIPO)
- Paid-database connectors behind the existing consent check
- Live verification of Bhashini, then voice input and output
- Encrypted, shared storage for multi-instance deployments

## License

[MIT](LICENSE). Corpus entries summarise public government and treaty texts; see each
entry's `source_url`.
