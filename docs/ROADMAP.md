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
      note). A legal-review sign-off workflow and automated `last_verified` drift
      checking against each `source_url` remain future work at larger scale.
- [x] (Stretch, delivered ahead of Stage 4) Optional dense multilingual retrieval
      re-ranking (`requirements-dense.txt`, `scripts/build_dense_index.py`) -- an
      opt-in upgrade layered onto the existing `VectorStore` interface via Reciprocal
      Rank Fusion, with zero effect on the default TF-IDF-only path when not installed.
      This narrows (but doesn't replace) the multilingual retrieval gap Stage 4 below
      still needs to close for languages TF-IDF handles poorly.

## Stage 2.5 -- Generative answers and semantic retrieval (this branch)
- [x] Replaced TF-IDF with dense embeddings (`embeddinggemma` via Ollama, or Gemini
      embeddings when hosted) and a FAISS index that rebuilds itself when the corpus or
      model changes.
- [x] Gemini answer generation, streamed to the UI, with citation numbers checked against
      the retrieved sources. A local Ollama model can be swapped in with one setting.
- [x] Hindi questions answered in Hindi (multilingual embeddings + language-aware prompt).
- [x] Replaced the earlier stubs with working implementations: an LLM-planned deep-research
      mode (sub-questions retrieved separately, answered part by part), a SQLite audit log
      that stores question fingerprints rather than text, logged and revocable consent for
      paid databases, "see / delete my data", escalation tickets to a human facilitator, and
      a Bhashini translation client for languages beyond English and Hindi.
- [x] Gemini answers with a local Ollama model (qwen3.5) as automatic fallback, thinking off
      on both.
- [x] Rebuilt the frontend: streaming chat with inline citation chips, light/dark themes,
      English/Hindi UI, mobile layout.

## Stage 3 -- Paid-source connectors
- Real integrations for the user's own subscriptions (e.g. Manupatra, SCC Online). The
  consent check they must pass already exists (`store.consents`).
- Encrypt the SQLite store at rest and move it to a managed database for multi-instance
  deployments.

## Stage 4 -- More languages and voice
- Verify the Bhashini client against live credentials; translate UI strings and source
  summaries as well as answers.
- Voice input/output via Bhashini's ASR/TTS pipelines.
- A parallel multilingual gold set in the eval.

## Corpus gaps found in testing
- **EU trade marks (EUIPO / EU Trade Mark Regulation).** Questions about registering a brand
  in the EU find only the Madrid System and the EU herbal-medicines directive, both below
  the confidence threshold, so the assistant correctly declines. Add a live-verified entry.

## Evaluation, ongoing
- **Citation correctness and safe abstention:** `make eval`, 35 cases including Hindi
  questions and off-topic questions in both languages.
- **Generated-answer citations:** `python -m eval.run_eval --llm` checks that the answer
  actually cites an expected source.
- **Answer accuracy:** needs legal review of generated answers or a larger gold set with
  reference answers.
