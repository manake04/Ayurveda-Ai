# Corpus document schema

Every corpus entry is a single retrievable "chunk" describing one provision, treaty article, rule, or
registry/record. The RAG pipeline embeds the title, instrument, citation, summary, excerpt and tags
(`backend/app/retrieval/corpus.py:document_text`) and returns the full object
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
  "full_text_excerpt": "..."           // OPTIONAL. Only present when the exact wording was fetched
                                        // and confirmed against a primary/authoritative source in the
                                        // same session that added it -- never a reconstruction from
                                        // memory. If it can't be verified live, this field is omitted
                                        // rather than filled with an approximate quote. See "Verbatim
                                        // excerpts" below.
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

## Notes on this MVP corpus

- This is a **hand-curated corpus of 45 entries** (26 India + 19 international), not a complete legal
  database. It exists to
  prove the retrieval-augmented, citation-grounded architecture end-to-end. Before any real deployment,
  every entry must be re-verified against the live primary source and the corpus must be expanded to
  full statutory/treaty text with a proper legal-review sign-off workflow (see `docs/ROADMAP.md`).
- Every entry carries a `source_url` pointing to an official or authoritative source so a user (or a
  reviewer) can always check the assistant's claim against the primary text — this is what "never
  fabricate authority" means operationally in this codebase.
- `last_verified` is what lets the corpus be "version-tracked": a nightly/weekly job (not built in this
  MVP) would re-check each `source_url` and flag entries whose `last_verified` date has drifted too far,
  surfacing them for legal review before the assistant keeps citing them.
- `graph_edges.json` alongside `india.json`/`international.json` is a separate, non-document file: it
  hand-authors the knowledge graph's institution links and document-to-document relations (regime,
  jurisdiction and formulation-category edges are auto-derived from these corpus files instead, so they
  can't drift out of sync). See `docs/ARCHITECTURE.md`'s "Knowledge graph" section and
  `backend/app/graph.py`.
