# Architecture

```
                          ┌────────────────────────────────────┐
                          │            React frontend            │
                          │       (Vite + Tailwind, :5173)       │
                          │                                       │
                          │  Ask (standard + agentic mode) ·      │
                          │  Knowledge graph · Classify · ABS ·   │
                          │  TKDL pointer · Connectors            │
                          └──────────────────┬────────────────────┘
                                             │ REST / JSON (fetch)
                          ┌──────────────────▼────────────────────┐
                          │            FastAPI backend              │
                          │                (:8000)                  │
                          │                                          │
                          │  /ask            -> rag.py               │
                          │  /ask/agentic    -> agent.py -> rag.py   │
                          │  /graph/*        -> graph.py             │
                          │  /classify       -> classifier.py        │
                          │  /abs-helper     -> abs_helper.py        │
                          │  /tkdl-pointer   -> tkdl.py               │
                          │  /connectors     -> connectors.py         │
                          │  /audit/recent   -> audit.py               │
                          └──┬──────────────┬──────────────┬──────────┘
                             │              │              │
              ┌──────────────▼───┐  ┌───────▼────────┐  ┌──▼──────────────────┐
              │   VectorStore     │  │   GraphStore    │  │   Optional LLM       │
              │ TF-IDF (sklearn), │  │ NetworkX+JSON,  │  │ (Anthropic/OpenAI)   │
              │ + optional dense  │  │ backend/data/   │  │ only if API key      │
              │ re-rank (RRF)     │  │ graph/graph.json│  │ configured; falls    │
              │ backend/data/     │  └────────▲────────┘  │ back to extractive   │
              │ index/            │           │           └──────────────────────┘
              └────────▲──────────┘  ┌────────┴───────────┐
                       │             │ corpus/graph_edges.json │
              ┌────────┴───────┐    │ hand-authored institution │
              │ /corpus/*.json  │◄──┤ + doc-to-doc relations;    │
              │ curated, cited, │    │ regime/jurisdiction/       │
              │ version-tracked │    │ category edges auto-derived│
              └────────────────┘    └────────────────────────────┘
```

## Request flow for `/ask` (standard mode)

1. The frontend sends `{ query, jurisdiction, language }`.
2. `rag.answer_for_jurisdiction` asks the `VectorStore` for the top-k corpus chunks whose
   TF-IDF vector is closest (cosine similarity) to the query, filtered to the chosen
   jurisdiction (India / International / both — kept as two separate result blocks when
   "both" is chosen, never merged into one undifferentiated answer). If a dense embedding
   index has been built (see below), the candidate pool is re-ranked via Reciprocal Rank
   Fusion, but the *score* used for confidence bucketing always stays the original TF-IDF
   score.
3. The top similarity score is bucketed into a confidence level (`high` / `medium` /
   `low`). Below the low threshold, the assistant **abstains** rather than answering --
   this is the safe-abstention behaviour the problem statement asks the system to be
   evaluable on.
4. If no LLM key is configured (the default), the answer is assembled directly from
   the retrieved chunks' own summaries -- nothing is generated that isn't already sourced.
   If a key is configured, an LLM synthesises a more fluent answer but is instructed to
   use *only* the retrieved context and cite every claim by chunk id; a network/LLM
   failure falls back to the extractive answer so a demo never goes blank.
5. Every citation returned to the frontend carries `source_url`, `source_name` and
   `last_verified` -- the "never fabricate authority" requirement is enforced structurally:
   the app cannot emit a citation object that wasn't actually retrieved from the corpus.
6. `rag.graph_expand` takes the top-2 retrieved documents and asks the `GraphStore` for
   1-hop neighbours connected by an "answer-relevant" relation (e.g. `SUPPORTS`,
   `ENFORCES`, `ANALOGOUS_TO`) -- these come back as `graph_related` items, rendered
   distinctly from direct citations, so a requirement that shares no vocabulary with the
   query (but is known to apply alongside it) still has a chance to surface.
7. The call is written to the local audit log (`backend/data/audit_log.jsonl`).

## Request flow for `/ask/agentic`

`app/agent.py` sits in front of the same `rag.answer_for_jurisdiction` used by standard
`/ask` -- it only decides *how many* lookups to run and *what to ask each one*, never
generates answer text itself:

1. **Jurisdiction planning**: if the caller asked for `"both"`, both jurisdictions are
   always planned as separate steps. If a single jurisdiction was requested but the
   *other* one also scores confidently (above the standard absolute confidence threshold)
   against the same query, a step for it is added too -- this is genuine automatic
   cross-jurisdiction detection, not just honoring an explicit "both" request.
2. **Regime planning**: within each planned jurisdiction, `VectorStore.top_regimes` looks
   at which distinct legal regimes appear among the top hits, using a *relative* threshold
   (a regime counts if it scores at least a fraction of the query's own top score) rather
   than the standard absolute bar -- a compound query's relevance to any one regime is
   naturally lower than a single-topic query's relevance to its one topic, so a fixed
   absolute cutoff under-detects compound questions. Two or more qualifying regimes means
   one focused retrieval step per regime instead of one blended lookup.
3. Each planned step runs through the exact same grounded retrieval + graph-expansion path
   as standard `/ask`, so it inherits the same "never cite what wasn't retrieved"
   guarantee and the same confidence/abstention behaviour per step (a step can itself
   abstain if its regime-restricted search doesn't clear the absolute confidence bar, even
   though that regime was detected as one of the query's top themes by the more lenient
   relative threshold used for planning -- this is intentional: planning and answering use
   different, purpose-appropriate thresholds).
4. A final cross-cutting graph pass expands the *union* of every step's citations one hop
   further, so a requirement linked to any step's findings (not just the top hit of one of
   them) still has a chance to surface.
5. The response carries `plan_summary` (a human-readable one-line explanation), `steps`
   (the ordered plan with each step's reasoning), and `sections` (one grounded,
   independently-confidenced answer per step) -- the frontend's `AgenticTrace` component
   renders the plan, and each section reuses the same `JurisdictionAnswerBlock` component
   standard mode uses.

See `app/agent.py`'s module docstring for exactly where a future LLM-backed planner would
replace `build_plan`'s rule-based body without changing this response shape at all.

## Knowledge graph (`app/graph.py`)

A `GraphStore` wraps a `networkx.MultiDiGraph`, persisted as node-link JSON
(`backend/data/graph/graph.json`) -- no graph database server to run. Four node types:

- **document** -- one per corpus entry, carrying its title/jurisdiction/regime/source URL.
- **regime**, **jurisdiction**, **category** -- concept nodes *auto-derived* at build time
  from the corpus itself and from `classifier.TREE`'s leaves, so they cannot drift out of
  sync with either as the corpus grows.
- **institution** -- administering bodies (NBA, CDSCO, FSSAI, WIPO, CCPA), hand-authored
  in `corpus/graph_edges.json` alongside genuinely judgment-call document-to-document
  relations (`SUPPORTS`, `ENFORCES`, `ANALOGOUS_TO`, `UMBRELLA_OVER`, etc.) that a human
  had to decide, not derive.

`GraphStore.build()` raises immediately if `graph_edges.json` references an unknown corpus
id, so a typo in the hand-authored file fails fast rather than silently producing a
dangling edge; `tests/test_graph.py` also checks referential integrity directly. The
frontend's **Knowledge graph** tab (`GraphExplorer.jsx`) is a from-scratch force-directed
canvas renderer -- deliberately not a charting library dependency, since the graph is small
enough (a few hundred nodes/edges) that a plain O(n²) repulsion simulation is fast, and
keeping it dependency-free keeps the visualisation fully auditable.

## Corpus ingestion & verification (`app/ingest/`, `scripts/ingest.py`)

The curated corpus is grown and maintained from the same open, authoritative public sources
it cites. `app/ingest/` is a small, dependency-light package driven by the
`scripts/ingest.py` CLI (alongside `build_index.py` / `build_graph.py`); two read-only
endpoints (`GET /corpus/sources`, `GET /corpus/verify`) expose its state to the running
backend without ever doing network I/O in a request.

```
                 scripts/ingest.py
     ┌───────────────┬───────────────┬────────────────────┐
   sources         verify          scaffold            refresh-verified
     │               │               │                        │
 sources.py     report.py ─┐   scaffold.py ─┐             writer.py
 (registry)     verify.py  │   extract.py   │        (bump last_verified
     │               │     │   fetch.py     │         on entries that pass)
     │          fetch.py   │        │        │
     │        (requests +  │   writer.py ────┘
     │         disk cache) │   (upsert into corpus/*.json;
     │               │     │    never clobbers a curated entry
     ▼               ▼     ▼    without --force)
  docs/SOURCES.md   data/ingest/verify_report.json  →  GET /corpus/verify
```

- **`sources.py`** — a registry of ~19 primary sources (India Code, e-Gazette, IP India,
  NBA/ABS, CDSCO, FSSAI, DPIIT, WIPO, WTO, CBD, EUR-Lex, WHO, UPOV, …). Each says how to turn
  a short locator into a canonical `source_url`, what `source_name` convention its entries
  follow (kept consistent with the existing corpus so the two can't drift — enforced by
  `tests/test_ingest.py`), and its `fetch_kind`: `html`, `pdf`, or `not_automatable`.
- **`fetch.py`** — polite `requests` GETs (browser UA, timeout, retry) with a raw-response
  disk cache under `backend/data/ingest/cache/`. `extract_text` uses BeautifulSoup / `pypdf`
  from the optional `requirements-ingest.txt` extra when present, and falls back to a stdlib
  `html.parser` tag-stripper (HTML) or "unparsed" (PDF) otherwise.
- **`scaffold.py`** — fetches a source locator and builds a full corpus entry
  (`corpus/SCHEMA.md` shape). Machine-filled fields are marked `review_status: "unreviewed"`
  with a `provenance` block. A `full_text_excerpt` is included **only** when the operative
  sentence for the cited provision is found literally in the fetched page — the same
  anti-fabrication rule the hand-authored corpus follows, now enforced in code. If an API
  key is configured the summary is LLM-written but strictly grounded in the fetched text
  (same lazy-import + fallback pattern as `rag.py:_llm_answer`); otherwise it is extractive.
  `scaffold` refuses a `not_automatable` source outright.
- **`writer.py`** — merges scaffolded entries into `india.json` / `international.json` by
  jurisdiction, dedupes by `id`, and **refuses to overwrite a hand-curated entry**
  (`review_status` absent / `"curated"` / `"verified"`) unless `force=True`. After a write,
  rerun `build_index.py` and `build_graph.py`.
- **`verify.py` / `report.py`** — re-check every entry against its live `source_url`:
  `ok` / `stale` (past the staleness threshold) / `excerpt_drift` (the `full_text_excerpt`
  no longer appears) / `unreachable` (no 2xx, or a soft-404 body) / `unverifiable` (a PDF
  with no parser, or a `not_automatable` source — never a false `ok`). The report is written
  to `backend/data/ingest/verify_report.json`; `ingest.py verify --fail-on ...` exits
  non-zero for CI, and `refresh-verified` bumps `last_verified` on the entries that pass.

## Why TF-IDF instead of a neural embedding model as the *default*

See the docstring in `backend/app/vectorstore.py`. Short version: the corpus is small and
lexically distinctive (statute names, section numbers), so sparse retrieval is accurate,
free, fully offline after `pip install`, and auditable ("why was this the citation?" has
a literal keyword-overlap answer). `VectorStore` is a narrow interface
(`build`, `load`, `search`, `attach_dense`) specifically so a dense multilingual encoder
can be opportunistically layered on top (see `app/embeddings.py` and
`scripts/build_dense_index.py`) without touching `rag.py`, `agent.py`, `main.py`, or the
frontend -- when no dense index has been built, behaviour is byte-for-byte identical to
TF-IDF alone.

## Formulation classification flow

`backend/app/classifier.py` encodes the decision tree from the problem statement as a
small dict-based state machine (`TREE`), walked one yes/no question at a time by
`POST /classify`. Each leaf carries the regulatory requirement and the very different
IP/ABS posture for that category, plus the corpus ids that back it up.

## ABS helper

`backend/app/abs_helper.py` turns six yes/no facts about the user's situation into a
checklist of which Access-and-Benefit-Sharing duties are likely triggered (Biological
Diversity Act / NBA approval, patent source-disclosure, the 2023 AYUSH exemption, and the
international Nagoya Protocol / WIPO GRATK Treaty layers), each item linked to its
corpus citation.

## TKDL / prior-art pointer

TKDL is not a public API -- it is shared with patent examiners under non-disclosure
agreements. `backend/app/tkdl.py` is honest about that limit: it explains what TKDL is
and does, and hands back real, public complementary prior-art search links (Indian
Patent Office public search, Espacenet, Google Patents, WIPO PATENTSCOPE) a user can
actually run today.

## Privacy, audit & consent

- `backend/app/audit.py` appends a timestamped, redacted JSON line per substantive call
  to a local file -- a minimal, inspectable analogue of the transparency/consent posture
  the Digital Personal Data Protection Act, 2023 expects (see corpus id
  `in-dpdp-act-2023`). No data leaves the machine the backend runs on.
- `backend/app/connectors.py` implements the "use the user's own paid subscription only
  with explicit, logged permission" requirement as a consent-and-audit pattern (grant /
  revoke, both logged) ahead of any real paid connector being wired in.

## Multilingual delivery (staged)

`backend/app/i18n.py` ships English + Hindi UI strings now, and a guarded
`translate_via_bhashini` function that only activates once Bhashini credentials are
configured (see `.env.example`) -- consistent with the problem statement's own staging:
"a citation-grounded retrieval MVP first, ... then the full multilingual and voice
experience." See `docs/ROADMAP.md`.
