# Staged build roadmap

The problem statement explicitly asks for a staged build. This repo now covers **Stage 1
and Stage 2**. Later stages are scoped here so the team can plan sprints/demos around
them.

## Stage 1 -- Citation-grounded retrieval MVP (this repo)
- [x] Curated, version-tracked starter corpus (~28 documents, India + International)
- [x] TF-IDF retrieval with jurisdiction filtering, confidence scoring, safe abstention
- [x] Extractive answers by default; pluggable LLM synthesis (Anthropic/OpenAI) when a
      key is configured, always grounded in retrieved chunks only
- [x] Formulation-classification decision tree (classical / proprietary / new drug /
      phytopharmaceutical / Ayurveda-Aahar / cosmetic)
- [x] ABS-compliance helper checklist
- [x] TKDL / public prior-art pointer
- [x] Local audit log; paid-connector consent pattern (stubbed, no real connector yet)
- [x] English + Hindi UI strings; jurisdiction toggle keeps India/International separate
- [x] Eval harness (citation correctness, safe abstention) + unit tests

## Stage 2 -- Knowledge graph + agentic orchestration (this repo, v2)
- [x] Model entities (documents, regimes, jurisdictions, formulation categories,
      administering institutions) and relationships (`SUPPORTS`, `ENFORCES`,
      `ANALOGOUS_TO`, `UMBRELLA_OVER`, etc.) in a lightweight embedded graph
      (NetworkX + JSON, `backend/app/graph.py`) rather than a standalone graph-DB server
      -- deliberately, to keep the MVP's zero-infrastructure deployment story intact; a
      server-backed graph DB (e.g. Neo4j) remains an option if the corpus grows enough
      to need one.
- [x] Introduce an agent loop (`backend/app/agent.py`, `POST /ask/agentic`) that plans a
      sequence of retrieval + graph-expansion steps for compound, multi-jurisdiction
      and/or multi-regime questions instead of a single retrieval pass, with the same
      "never answer without a retrieved source" guardrail carried through every step.
      Rule-based today (no LLM key required); the module docstring marks exactly where an
      LLM-backed planner would plug in later without changing the API response shape.
- [x] Frontend: a **Knowledge graph** tab (force-directed graph browser, click-to-inspect
      nodes) and an **agentic mode** toggle in the chat UI (renders the planner's
      step-by-step reasoning trace alongside grounded, cited answer sections).
- [x] Expand the corpus (16 → 26 India entries, 12 → 19 international entries; 45 total)
      with real quoted key-section text (`full_text_excerpt`) added to select entries,
      always from a live-verified fetch in the same authoring session -- never
      backfilled from training-data recall (see `corpus/SCHEMA.md`'s anti-fabrication
      note).
- [x] Corpus ingestion & verification pipeline (`backend/app/ingest/`,
      `backend/scripts/ingest.py`, `docs/SOURCES.md`): a registry of the authoritative
      public sources; `scaffold` to build a corpus entry from a source locator (written
      back tagged `review_status: "unreviewed"`, `full_text_excerpt` only on a verified
      live match); and `verify` -- **automated `last_verified` drift checking against each
      `source_url`** (reachability + excerpt-drift + staleness), with a report served at
      `GET /corpus/verify` and a CI-friendly `--fail-on` exit code. A legal-review
      sign-off workflow layered on top of that report remains future work.
- [x] (Stretch, delivered ahead of Stage 4) Optional dense multilingual retrieval
      re-ranking (`requirements-dense.txt`, `scripts/build_dense_index.py`) -- an
      opt-in upgrade layered onto the existing `VectorStore` interface via Reciprocal
      Rank Fusion, with zero effect on the default TF-IDF-only path when not installed.
      This narrows (but doesn't replace) the multilingual retrieval gap Stage 4 below
      still needs to close for languages TF-IDF handles poorly.

## Stage 3 -- Paid-source connectors
- Real integrations behind the existing consent pattern (`connectors.py`) for the user's
  own subscriptions (e.g. Manupatra, SCC Online, or an international patent-law database),
  gated by the same explicit-and-logged permission flow already built.
- Move the audit log from a local JSONL file to a proper encrypted, retention-limited
  store, with a data-subject access/delete flow aligned to the DPDP Act.

## Stage 4 -- Full multilingual & voice experience
- Stage 2 already delivered an *optional* dense multilingual retrieval re-ranker
  (`paraphrase-multilingual-MiniLM-L12-v2` via `requirements-dense.txt`) as a stretch
  goal -- but it re-ranks TF-IDF's own English-lexical candidate pool, so a query typed
  entirely in Hindi still depends on TF-IDF having found reasonable candidates first.
  Fully closing the gap means either replacing (not just re-ranking) the candidate
  generation step with the multilingual encoder for non-English queries, or a
  Bhashini-integrated embedding purpose-built for Indian languages.
- Wire up `translate_via_bhashini` for real (pipeline id/credentials), and extend the
  corpus's citation summaries to ship pre-translated or live-translated into Indian
  languages (Hindi, and others via Bhashini's language set).
- Add voice input/output via Bhashini's ASR/TTS pipelines.

## Evaluation, ongoing
The problem statement calls out four evaluable dimensions; this MVP covers the first two
end-to-end (now including agentic-mode planning) and stubs the other two:
- **Citation correctness** -- `backend/eval/run_eval.py` checks retrieved citations
  against a hand-labelled expected set (100% on the current 15-case standard-mode gold
  set).
- **Safe abstention** -- same harness, checked against 3 clearly out-of-scope queries
  (100% on the current set), plus a dedicated agentic-mode case checking that a fully
  out-of-scope *compound* question causes every planned section to abstain (100%).
- **Agentic planning quality** (v2 addition) -- two more eval dimensions specific to
  `/ask/agentic`: step-count accuracy (does the planner decompose a compound question into
  the expected number of steps, and *not* over-decompose a simple one?) and citation
  coverage across all planned sections (100% on both, on the current 2-case set).
- **Answer accuracy** -- needs either human legal review of generated answers or a much
  larger gold Q&A set with reference answers; out of scope for an MVP eval harness.
- **Multilingual quality** -- meaningful only once Stage 4's multilingual retrieval and
  Bhashini integration exist; track it with a parallel gold set once that lands.
