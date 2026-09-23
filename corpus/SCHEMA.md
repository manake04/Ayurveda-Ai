# Corpus document schema

Every corpus entry is a single retrievable "chunk" describing one provision, treaty article, rule, or
registry/record. The RAG pipeline embeds the `title` + `summary` + `tags` and returns the full object
as a citation when it is retrieved.

```jsonc
{
  "id": "in-patents-3p",              // stable slug, unique across the whole corpus
  "jurisdiction": "India",             // "India" | "International"
  "regime": "patent",                  // patent | gi | trademark | design | copyright | plant_variety |
                                        // biodiversity_abs | drug_regulatory | advertising |
                                        // food_cosmetic | data_protection | treaty | market_access
  "title": "Traditional-knowledge bar on patentability",
  "instrument": "Patents Act, 1970",   // name of the statute / treaty / rules
  "citation": "Section 3(p)",          // precise section / article / rule number
  "instrument_type": "statute",        // statute | rule | treaty | regulation | registry | guidance
  "summary": "Plain-language explanation of what this provision says and why it matters for Ayurveda IP.",
  "source_url": "https://...",         // official / primary source the user can open to verify
  "source_name": "India Code (Ministry of Law & Justice)",
  "last_verified": "2026-09-01",       // date this MVP corpus entry was last checked against the source
  "tags": ["traditional knowledge", "novelty bar", "classical formulation"],
  "full_text_excerpt": "...",          // OPTIONAL. Only present when the exact wording was fetched
                                        // and confirmed against a primary/authoritative source in the
                                        // same session that added it -- never a reconstruction from
                                        // memory. If it can't be verified live, this field is omitted
                                        // rather than filled with an approximate quote. See "Verbatim
                                        // excerpts" below.
  "review_status": "curated",          // OPTIONAL. Absent or "curated"/"verified" => hand-reviewed
                                        // content (the default for every entry authored by hand).
                                        // "unreviewed" => produced by the ingestion pipeline
                                        // (scripts/ingest.py scaffold) and NOT yet checked by a human.
  "provenance": { ... }                // OPTIONAL. Present on machine-scaffolded entries: how the
                                        // entry was produced (source id, locator, fetch timestamp,
                                        // parser, whether the summary is extractive or LLM-written).
}
```

## Verbatim excerpts (`full_text_excerpt`)

A handful of the highest-traffic entries carry a `full_text_excerpt` -- the actual operative
sentence(s) of the statute/treaty, not a paraphrase. These were added by fetching the live primary
source (or, where the primary site blocked automated access, a verified secondary mirror such as
WIPO's own treaty-text pages or Indian Kanoon) and copying the exact wording, specifically so the
assistant can show a user the real clause instead of a summary of it. This is deliberately not done
for every entry: writing a "verbatim" field from training-data recall instead of a live-verified
fetch would be exactly the kind of fabricated authority this project exists to avoid, so an entry
without this field should be read as "summarised, not literally quoted" rather than as missing
data.

## Ingestion pipeline (`scripts/ingest.py`)

The corpus can be grown and maintained from the same open, authoritative sources it cites —
see [`docs/SOURCES.md`](../docs/SOURCES.md) for the source registry and
[`docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md)'s "Corpus ingestion & verification" section
for the flow. Two operations:

- **`scaffold`** turns a source id + a document locator into an entry and (with `--write`)
  adds it to `india.json` / `international.json`, tagged `review_status: "unreviewed"`. The
  machine fills `source_url`, `source_name`, `last_verified`, and best-effort
  `title` / `summary` / `tags`; a human is expected to tighten these before the entry is
  trusted. A `full_text_excerpt` is only written when the operative sentence for the cited
  provision is found **literally** in the live fetch — the anti-fabrication rule above is
  enforced by code, not just convention.
- **`verify`** re-checks every entry's `source_url`: reachable? does any `full_text_excerpt`
  still appear on the page? is `last_verified` within the staleness threshold? It writes a
  report to `backend/data/ingest/verify_report.json` (served read-only at `GET /corpus/verify`)
  and can exit non-zero in CI. `refresh-verified` bumps `last_verified` on entries that pass.

Sources that cannot honestly be queried by a script — TKDL (shared with examiners under
NDA) and the captcha-gated IP India search front-ends (InPASS, GI/TM/Design registers) — are
marked `not_automatable`: `scaffold` refuses them and `verify` reports them as
`unverifiable` rather than inventing a result.

## Notes on this MVP corpus

- This is a **hand-curated corpus of 45 entries** (26 India + 19 international), not a complete legal
  database. It exists to
  prove the retrieval-augmented, citation-grounded architecture end-to-end. Before any real deployment,
  every entry must be re-verified against the live primary source and the corpus must be expanded to
  full statutory/treaty text with a proper legal-review sign-off workflow (see `docs/ROADMAP.md`).
- Every entry carries a `source_url` pointing to an official or authoritative source so a user (or a
  reviewer) can always check the assistant's claim against the primary text — this is what "never
  fabricate authority" means operationally in this codebase.
- `last_verified` is what lets the corpus be "version-tracked": `scripts/ingest.py verify` re-checks
  each `source_url` (reachability + `full_text_excerpt` drift + staleness against a threshold) and
  writes a report; run it on a schedule / in CI (`--fail-on unreachable,excerpt_drift`) to surface
  drifted entries for legal review before the assistant keeps citing them. A full legal-review
  sign-off workflow on top of that report is still future work.
- `graph_edges.json` alongside `india.json`/`international.json` is a separate, non-document file: it
  hand-authors the knowledge graph's institution links and document-to-document relations (regime,
  jurisdiction and formulation-category edges are auto-derived from these corpus files instead, so they
  can't drift out of sync). See `docs/ARCHITECTURE.md`'s "Knowledge graph" section and
  `backend/app/graph.py`.
