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
