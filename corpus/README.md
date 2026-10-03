# Corpus

A hand-curated set of 45 provisions (26 India, 19 international) that every answer is grounded
in. Each entry is one retrievable unit: a statute section, rule, treaty article or registry.

| File | Contents |
|---|---|
| `india.json` | Indian statutes, rules and regulations |
| `international.json` | Treaties and export-market regimes |
| `graph_edges.json` | Hand-authored knowledge-graph links (institutions, doc-to-doc relations) |

## Entry schema

```jsonc
{
  "id": "in-patents-3p",                 // unique, stable slug
  "jurisdiction": "India",               // "India" | "International"
  "regime": "patent",                    // patent | gi | trademark | design | copyright | plant_variety |
                                         // biodiversity_abs | drug_regulatory | advertising |
                                         // food_cosmetic | data_protection | treaty | market_access
  "title": "Traditional-knowledge bar on patentability",
  "instrument": "Patents Act, 1970",
  "citation": "Section 3(p)",            // exact section / article / rule
  "instrument_type": "statute",          // statute | rule | treaty | regulation | registry | guidance
  "summary": "Plain-language explanation and why it matters for Ayurveda.",
  "source_url": "https://...",           // official or authoritative source
  "source_name": "India Code",
  "last_verified": "2026-09-06",         // last checked against the source
  "tags": ["traditional knowledge", "novelty bar"],
  "full_text_excerpt": "..."             // optional, see below
}
```

## Rules for contributors

- **Never fabricate authority.** Every entry must link to an official or authoritative source.
- **Verbatim text only from a live source.** `full_text_excerpt` holds the exact operative
  wording, copied from the primary source (or a verified mirror) at the time of writing. If it
  can't be verified, leave the field out; never reconstruct wording from memory.
- **Keep it current.** Update `last_verified` whenever an entry is re-checked.
- **Graph edges** in `graph_edges.json` must reference existing ids; the tests fail otherwise.
  Regime, jurisdiction and category links are derived automatically.

The FAISS index rebuilds itself on the next API start after any change here. Run `make eval`
afterwards to check retrieval quality.
