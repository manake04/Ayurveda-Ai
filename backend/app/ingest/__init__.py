"""Corpus ingestion & verification pipeline.

Grows and maintains the curated corpus (`corpus/*.json`) from the same open,
authoritative public sources it already cites — TKDL, India Code, the IP India
databases, the National Biodiversity Authority / ABS portal, the e-Gazette, WIPO,
WTO and EUR-Lex.

Two jobs:

* **scaffold** — turn a source id + a document locator into a corpus entry
  (`scaffold.scaffold_entry`) and, optionally, write it straight into
  `corpus/india.json` / `corpus/international.json` (`writer.upsert_entries`).
* **verify** — re-check every existing entry's `source_url` for reachability and
  for drift of its `full_text_excerpt` / `citation` against the live page
  (`verify.verify_entry`, `report.verify_corpus`).

Anti-fabrication discipline (see `corpus/SCHEMA.md`) is kept structurally:
machine-created entries are tagged ``review_status="unreviewed"``; a
``full_text_excerpt`` is only ever written when the exact wording is confirmed
present in the live fetch, never synthesised; and sources that genuinely cannot
be queried programmatically (TKDL, InPASS) are marked ``not_automatable`` rather
than faked.
"""
