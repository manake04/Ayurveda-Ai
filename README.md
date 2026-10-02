# IP-SAKTI Sahayak

[![CI/CD](https://github.com/manake04/Ayurveda-Ai/actions/workflows/ci.yml/badge.svg)](https://github.com/manake04/Ayurveda-Ai/actions/workflows/ci.yml)

**A multilingual, RAG-based, source-cited AI assistant for Intellectual Property and
regulatory guidance in Ayurveda — across national and international regimes.**

Built for **Smart India Hackathon 2026 — Problem Statement ID 26045**.

**Live demo:** https://manake04.github.io/Ayurveda-Ai/ (frontend, GitHub Pages) — talks to
the backend deployed on Render. See [Deployment](#deployment) below for how both pieces are
wired together and how to point the demo at your own backend.

> This is Stage 1 (citation-grounded retrieval) **and** Stage 2 (knowledge graph +
> agentic orchestration) of the problem statement's staged build: "a citation-grounded
> retrieval MVP first, then the graph and agentic layers, then paid-source connectors and
> the full multilingual and voice experience." Stage 3 (paid-source connectors) and Stage
> 4 (full multilingual/voice) remain ahead — see [`docs/ROADMAP.md`](docs/ROADMAP.md) for
> the full staging plan.

## What it does

- **Answers IP/regulatory questions about Ayurveda with mandatory source citations.**
  Every answer is grounded in a curated corpus of statutes, rules, treaties and
  regulations — never generated from an LLM's unsourced prior knowledge. If nothing
  relevant is found, the assistant **abstains** rather than guessing.
- **Keeps India and International answers explicitly separate** via a jurisdiction
  toggle (India / International / Both — shown as two clearly separated blocks, never
  merged).
- **Plans multi-step, compound questions in "agentic mode"** — a rule-based (no LLM key
  required) planner that splits a question spanning multiple jurisdictions and/or legal
  regimes into a small sequence of grounded retrieval steps, each still cited exactly like
  a standard answer. See `backend/app/agent.py`.
- **Expands answers through a knowledge graph** — a lightweight, embedded graph
  (NetworkX + JSON, no server) connects corpus documents to shared regimes, jurisdictions,
  formulation categories and administering institutions, surfacing genuinely related
  requirements that share no vocabulary with the query. Browsable in the frontend's
  **Knowledge graph** tab. See `backend/app/graph.py`.
- **Classifies a formulation first**, because IP posture in Ayurveda depends on drug
  classification: classical/generic medicine, patent-or-proprietary medicine,
  phytopharmaceutical, new/non-classical drug, Ayurveda-Aahar/nutraceutical, or cosmetic
  — each with its own regulatory requirement and IP/ABS posture.
- **Helps with Access-and-Benefit-Sharing (ABS) compliance** via a guided checklist.
- **Points to TKDL and public prior-art search tools** (TKDL itself isn't publicly
  queryable, so this is an honest pointer, not a fake live search).
- **Shows a confidence indicator** on every answer and an **escalate-to-human-facilitator**
  option when confidence is low.
- **Carries a standing "information, not legal advice" disclaimer**, a local audit log,
  and an explicit-consent pattern for (future) paid-source connectors.
- **Ships English + Hindi UI strings** now, with a guarded integration point for full
  Bhashini-powered multilingual retrieval later (Stage 4).

## Quick start

Requires Python 3.10+ and Node.js 18+.

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # works out of the box with everything blank
python scripts/build_index.py   # builds the TF-IDF retrieval index from /corpus
python scripts/build_graph.py   # builds the knowledge graph from /corpus + graph_edges.json
uvicorn app.main:app --reload   # serves http://127.0.0.1:8000
```

Run the tests and eval harness any time:

```bash
python -m pytest tests/ -v
python eval/run_eval.py
```

#### Optional: dense multilingual retrieval upgrade

The MVP's default retrieval (TF-IDF) works fully offline with zero extra downloads. If you
want the multilingual/semantic-similarity upgrade, install the separate extra and build the
embedding index (first run downloads a ~470MB model):

```bash
pip install -r requirements-dense.txt
python scripts/build_dense_index.py
```

The backend picks up a built dense index automatically on next start — no code or config
changes needed — and re-ranks TF-IDF's own candidates via Reciprocal Rank Fusion rather
than replacing it, so the tuned confidence/abstention thresholds stay valid either way. See
`backend/app/vectorstore.py` and `backend/app/embeddings.py`. This is genuinely optional:
everything above (including all tests and the eval harness) passes without it.

### 2. Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env            # points at http://127.0.0.1:8000 by default
npm run dev                     # serves http://127.0.0.1:5173
```

Open http://127.0.0.1:5173 — the header shows the live corpus document count once it can
reach the backend, confirming the two are talking to each other.

### 3. (Optional) Plug in a real LLM

The MVP works fully offline/free by default (extractive, citation-only answers — see
`backend/app/rag.py`). To upgrade answer fluency, add `ANTHROPIC_API_KEY` or
`OPENAI_API_KEY` to `backend/.env` and restart the backend. This never changes *what* is
retrieved or cited — only how the grounded answer is phrased.

## Project layout

```
ip-sakti-sahayak-mvp/
├── corpus/                     # curated, version-tracked source-of-truth documents
│   ├── SCHEMA.md
│   ├── india.json              # 26 India-jurisdiction entries
│   ├── international.json      # 19 international-jurisdiction entries
│   └── graph_edges.json        # hand-authored institution + doc-to-doc graph relations
├── backend/                    # FastAPI + TF-IDF retrieval + graph + agentic + classifier/ABS/TKDL/audit
│   ├── app/
│   │   ├── vectorstore.py      # TF-IDF retrieval (+ optional dense re-ranking)
│   │   ├── embeddings.py       # optional dense multilingual embedding index
│   │   ├── graph.py            # NetworkX + JSON knowledge graph
│   │   ├── agent.py            # rule-based agentic planner (no LLM required)
│   │   ├── rag.py              # citation-grounded retrieval + answer synthesis
│   │   └── ingest/             # corpus ingestion & verification pipeline
│   │       ├── sources.py      # registry of authoritative public sources
│   │       ├── fetch.py        # cached, polite fetch + HTML/PDF text extraction
│   │       ├── scaffold.py     # source locator -> corpus entry (review_status=unreviewed)
│   │       ├── writer.py       # merge into corpus/*.json (won't clobber curated entries)
│   │       └── verify.py       # re-check each entry's source_url for drift
│   ├── scripts/
│   │   ├── build_index.py
│   │   ├── build_graph.py
│   │   ├── build_dense_index.py   # optional
│   │   └── ingest.py           # sources / verify / scaffold / refresh-verified
│   ├── requirements.txt
│   ├── requirements-dense.txt  # optional extra, not installed by default
│   ├── requirements-ingest.txt # optional extra (HTML/PDF parsing), not installed by default
│   ├── tests/                  # incl. test_graph.py, test_agent.py, test_ingest.py
│   └── eval/                   # citation-correctness, safe-abstention & agentic-planning harness
├── frontend/                    # React + Vite + Tailwind UI
│   └── src/
│       └── components/
│           ├── ChatWindow.jsx      # standard + agentic-mode toggle
│           ├── AgenticTrace.jsx    # renders the planner's step-by-step reasoning
│           ├── GraphExplorer.jsx   # force-directed knowledge-graph browser (Knowledge graph tab)
│           └── RelatedCitationCard.jsx  # graph-surfaced "also related" citations
└── docs/
    ├── ARCHITECTURE.md
    ├── ROADMAP.md
    └── SOURCES.md               # generated: the corpus source registry
```

## Maintaining the corpus

The corpus is grown and maintained from the same open, authoritative public sources it cites
(TKDL, India Code, IP India, NBA/ABS, e-Gazette, WIPO, WTO, EUR-Lex, …). See
[`docs/SOURCES.md`](docs/SOURCES.md) for the full registry.

```bash
cd backend
pip install -r requirements-ingest.txt         # optional: HTML/PDF parsing (falls back to stdlib without it)

python scripts/ingest.py sources               # list the source registry
python scripts/ingest.py verify --stale-days 180   # re-check every entry's source_url; writes data/ingest/verify_report.json
python scripts/ingest.py scaffold --source india-code --locator 123456789/1388 \
    --regime patent --id in-patents-example --citation "Section 3(p)" --write
python scripts/build_index.py && python scripts/build_graph.py   # rebuild after any --write
```

Scaffolded entries are tagged `review_status: "unreviewed"` and need a human to tighten the
title/summary before they are trusted; a `full_text_excerpt` is only ever written when the
exact wording is confirmed present in the live fetch. Sources that can't honestly be queried
by a script (TKDL, the captcha-gated IP India search) are marked `not_automatable`. The
verification report is also served read-only at `GET /corpus/verify`.

## Important caveats (read before a live demo)

- The corpus is a **hand-curated set of 45 documents** (26 India + 19 international), not
  a complete legal database — see `corpus/SCHEMA.md` for what a production corpus would
  need (full statutory text at scale, case law, a legal-review sign-off workflow). Automated
  `last_verified` drift checking now exists (`python scripts/ingest.py verify`, see
  "Maintaining the corpus" above), but the legal-review sign-off on top of its report does
  not. A subset of entries carry a verbatim
  `full_text_excerpt` that was live-fetched and confirmed during authoring — see
  `SCHEMA.md`'s anti-fabrication note on why that field is populated selectively rather
  than backfilled from training-data recall.
- The knowledge graph's regime/jurisdiction/formulation-category edges are auto-derived
  from the corpus and the classifier tree (so they can't drift out of sync), but
  `corpus/graph_edges.json`'s institution links and document-to-document relations are
  hand-authored and should be reviewed like any other curated content.
- The agentic planner is **rule-based, not an LLM**, by design (no API key required). It
  decomposes compound questions using score-based signals (cross-jurisdiction confidence,
  regime diversity) — see `backend/app/agent.py`'s module docstring for exactly where an
  LLM-backed planner would plug in later without changing the API shape.
- This is **information, not legal advice** — the app says so on every screen, and so
  does this README.
- TKDL cannot be queried live (it's not public); the TKDL panel is an honest pointer to
  what TKDL is plus real public prior-art search tools, not a live TKDL search.
- Default retrieval is TF-IDF (sparse/lexical), not a neural embedding model — a
  deliberate choice for reliability and zero-dependency-download reasons; see
  `backend/app/vectorstore.py`'s docstring. The optional dense-retrieval upgrade above
  narrows that gap for multilingual/semantic queries without touching the default path.

## Evaluation

```bash
cd backend && python eval/run_eval.py
```

On the current 21-case gold set (18 standard + 3 agentic-mode cases): **100% citation
correctness** (15/15), **100% safe abstention** (3/3), and on the agentic dimensions,
**100% step-count accuracy** (2/2), **100% citation coverage** (2/2) and **100%
full-abstention correctness** (1/1). See `docs/ROADMAP.md` for what's still needed to
evaluate answer accuracy and multilingual quality at scale.

## Deployment

A single GitHub Actions pipeline (`.github/workflows/ci.yml`, workflow name "CI/CD") handles
both verification and the frontend deploy, as three jobs in one run:

- **`backend`** — installs deps, builds the retrieval index + knowledge graph, runs
  `pytest` and the eval harness. The eval harness's exit code now actually reflects
  pass/fail (a prior version always exited 0, so a citation/abstention regression could
  silently pass CI) and its results table is written to the run's job summary.
- **`frontend`** — installs deps and runs `npm run build` **once**, with the GitHub Pages
  base path and `VITE_API_BASE_URL` baked in; the built `dist/` is uploaded as a Pages
  artifact on every run (PRs included, so a broken build is visible before merge), and
  its size is written to the job summary.
- **`deploy`** — only on a push to `main` (never on PRs), publishes the artifact `frontend`
  already built to GitHub Pages. It doesn't rebuild anything — reusing that one build is
  what keeps this to a single `npm ci`/`npm run build` per run instead of two.

Runs on `main`/PRs auto-cancel a superseded run of themselves (`concurrency:`), so a quick
burst of pushes doesn't queue up redundant runners.

The FastAPI backend needs an actual server process, which GitHub Actions runners don't
provide long-term — it's deployed separately to Render's free tier using the
[`render.yaml`](render.yaml) blueprint in this repo. One-time setup to reproduce or fork this:

1. **Backend → Render:** on [render.com](https://render.com), "New +" → "Blueprint" → point
   it at this repo. Render reads `render.yaml` and provisions the FastAPI service
   automatically (installs deps, builds the index/graph, starts `uvicorn`). Copy the
   resulting `https://<service>.onrender.com` URL.
2. Update `render.yaml`'s `CORS_ORIGINS` (or set it directly in the Render dashboard) to
   include your GitHub Pages origin, e.g. `https://<you>.github.io`.
3. **Frontend → GitHub Pages:** in this repo's Settings → Pages, set Source to "GitHub
   Actions" (one-time — the pipeline's `deploy` job also passes `enablement: true`, which
   turns this on automatically on its first successful run if you skip the manual step).
   In Settings → Secrets and variables → Actions → Variables, add `VITE_API_BASE_URL` =
   your Render URL from step 1, then push to `main` (or re-run the workflow from the
   Actions tab) so the frontend rebuilds against that API URL and republishes.

Note the free tiers of both services: Render's free web service spins down after inactivity
(the first request after idling can take ~30-50s to cold-start), and GitHub Pages is static
hosting with no backend of its own. Fine for a hackathon demo; call this out if judges hit a
slow first load.

## License

MIT — built as a hackathon MVP; see individual corpus entries for the (unmodified)
government/treaty source material they summarise, which remains public-domain government
and treaty text.
