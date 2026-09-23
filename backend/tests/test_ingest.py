"""Tests for the corpus ingestion & verification pipeline (app/ingest/*).

All offline: every fetch is a fake that reads from tests/fixtures/ingest/.
"""
import json
from datetime import date
from pathlib import Path

import pytest

from app import config
from app.corpus_loader import load_corpus
from app.ingest import extract, report, scaffold, writer
from app.ingest.fetch import FetchResult, extract_text
from app.ingest.sources import SOURCE_REGISTRY, get_source, source_for_url
from app.ingest.verify import verify_entry

FIX = Path(__file__).parent / "fixtures" / "ingest"
TODAY = date(2026, 9, 7)


# ---------- fake fetcher ----------

def _result(raw: bytes, url: str, *, status: int = 200, content_type: str = "text/html; charset=utf-8") -> FetchResult:
    return FetchResult(
        url=url,
        status=status,
        content_type=content_type,
        raw=raw,
        fetched_at="2026-09-07T00:00:00+00:00",
        from_cache=False,
        error=None if status else "connection refused",
    )


def fetcher_for(mapping):
    """mapping: url -> (fixture filename | bytes | ('status', int))."""
    def _fetch(url: str) -> FetchResult:
        spec = mapping.get(url, ("status", 404))
        if isinstance(spec, tuple) and spec[0] == "status":
            return _result(b"", url, status=spec[1])
        if isinstance(spec, bytes):
            return _result(spec, url)
        data = (FIX / spec).read_bytes()
        ct = "application/pdf" if spec.endswith(".pdf") else "text/html; charset=utf-8"
        return _result(data, url, content_type=ct)
    return _fetch


# ---------- source registry ----------

def test_every_source_has_the_required_fields():
    for sid, src in SOURCE_REGISTRY.items():
        assert src.id == sid
        assert src.name and src.display_name and src.homepage
        assert src.jurisdiction in ("India", "International")
        assert src.fetch_kind in ("html", "pdf", "not_automatable")
        assert src.default_instrument_type in (
            "statute", "rule", "treaty", "regulation", "registry", "guidance"
        )
        assert src.locator_help
        if not src.automatable:
            assert src.access_notes, f"{sid}: a not_automatable source must explain why"


def test_registry_matches_the_existing_corpus():
    """Every hand-curated entry's host resolves to a registered source, and its
    source_name follows that source's naming convention — so the registry and the
    corpus can't drift apart."""
    docs = load_corpus(config.CORPUS_DIR)
    unknown_host = [(d["id"], d["source_url"]) for d in docs if source_for_url(d["source_url"]) is None]
    assert not unknown_host, f"corpus entries with no registered source host: {unknown_host}"

    name_drift = [
        (d["id"], d["source_name"])
        for d in docs
        if not source_for_url(d["source_url"]).name_matches(d["source_name"])
    ]
    assert not name_drift, f"source_name does not match its source's convention: {name_drift}"


def test_source_for_url_resolves_hosts():
    assert source_for_url("https://www.indiacode.nic.in/handle/123456789/1388").id == "india-code"
    assert source_for_url("https://example.com/whatever") is None


# ---------- extraction ----------

def test_html_extraction_drops_script_and_style():
    result = _result((FIX / "india_code_patents.html").read_bytes(), "u")
    extracted = extract_text(result)
    assert extracted.ok
    assert "traditional knowledge" in extracted.text
    assert "analytics beacon" not in extracted.text


def test_find_excerpt_locates_the_cited_clause():
    text = extract_text(_result((FIX / "india_code_patents.html").read_bytes(), "u")).text
    excerpt = extract.find_excerpt(text, "Section 3(p)")
    assert excerpt is not None
    assert "traditional knowledge" in excerpt
    assert extract.excerpt_present(text, excerpt)


def test_excerpt_present_detects_drift():
    text = extract_text(_result((FIX / "india_code_patents.html").read_bytes(), "u")).text
    assert not extract.excerpt_present(text, "a completely different sentence about trademark dilution")


def test_pdf_extraction_reads_body_text():
    pytest.importorskip("pypdf")
    result = _result((FIX / "sample_rule.pdf").read_bytes(), "u", content_type="application/pdf")
    extracted = extract_text(result)
    assert extracted.parser == "pypdf"
    assert "safety and effectiveness" in extracted.text


def test_unparseable_pdf_is_flagged_not_crashed():
    extracted = extract_text(_result(b"%PDF-1.4 not really a pdf", "u", content_type="application/pdf"))
    assert not extracted.ok
    assert extracted.parser == "pdf-unparsed"


# ---------- verify ----------

def _entry(**over):
    base = {
        "id": "in-test",
        "regime": "patent",
        "jurisdiction": "India",
        "citation": "Section 3(p)",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/1388",
        "last_verified": "2026-09-01",
        "full_text_excerpt": "(p) an invention which, in effect, is traditional knowledge or which is an "
        "aggregation or duplication of known properties of traditionally known component or components.",
    }
    base.update(over)
    return base


def test_verify_ok():
    f = fetcher_for({_entry()["source_url"]: "india_code_patents.html"})
    r = verify_entry(_entry(), fetcher=f, today=TODAY, stale_days=180)
    assert r.status == "ok"
    assert r.checks["excerpt_present"] is True


def test_verify_stale():
    f = fetcher_for({_entry()["source_url"]: "india_code_patents.html"})
    r = verify_entry(_entry(last_verified="2025-01-01"), fetcher=f, today=TODAY, stale_days=180)
    assert r.status == "stale"
    assert r.staleness_days > 180


def test_verify_unreachable():
    f = fetcher_for({_entry()["source_url"]: ("status", 404)})
    r = verify_entry(_entry(), fetcher=f, today=TODAY)
    assert r.status == "unreachable"
    assert r.checks["reachable"] is False


def test_verify_excerpt_drift():
    f = fetcher_for({_entry()["source_url"]: "india_code_patents.html"})
    drifted = _entry(full_text_excerpt="The Registrar shall maintain a register of authorised users in Chennai.")
    r = verify_entry(drifted, fetcher=f, today=TODAY)
    assert r.status == "excerpt_drift"


def test_verify_not_automatable_source_is_unverifiable_never_ok():
    entry = _entry(source_url="http://www.tkdl.res.in/tkdl/langdefault/common/Abouttkdl.asp")
    r = verify_entry(entry, fetcher=fetcher_for({}), today=TODAY)
    assert r.status == "unverifiable"


def test_verify_pdf_without_body_is_unverifiable():
    url = "https://cdsco.gov.in/x/rules.pdf"
    f = fetcher_for({url: b"%PDF-1.4 garbage"})
    r = verify_entry(_entry(source_url=url), fetcher=f, today=TODAY)
    assert r.status == "unverifiable"


def test_verify_corpus_report_shape():
    rep = report.verify_corpus(config.CORPUS_DIR, fetcher=fetcher_for({}), today=TODAY)
    assert rep.total == len(load_corpus(config.CORPUS_DIR))
    assert sum(rep.counts.values()) == rep.total
    # nothing resolves against an empty fetcher, so every entry is unreachable/unverifiable
    assert set(rep.counts) <= {"unreachable", "unverifiable"}
    assert rep.has_failures


def test_verify_corpus_writes_report(tmp_path):
    rep = report.verify_corpus(config.CORPUS_DIR, fetcher=fetcher_for({}), today=TODAY)
    out = rep.write(tmp_path / "verify_report.json")
    reloaded = json.loads(out.read_text())
    assert reloaded["total"] == rep.total


# ---------- scaffold ----------

_HTML_URL = "https://www.indiacode.nic.in/handle/123456789/9999"


def _scaffold(**kw):
    f = fetcher_for({_HTML_URL: "india_code_patents.html"})
    defaults = dict(
        source_id="india-code",
        locator="123456789/9999",
        regime="patent",
        id_slug="in-scaffold-test",
        fetcher=f,
        today=TODAY,
    )
    defaults.update(kw)
    return scaffold.scaffold_entry(**defaults)


def test_scaffold_produces_all_required_fields():
    entry = _scaffold(citation="Section 3(p)")
    assert not scaffold.missing_required_fields(entry)
    assert entry["last_verified"] == "2026-09-07"
    assert entry["review_status"] == "unreviewed"
    assert entry["provenance"]["source_id"] == "india-code"
    assert entry["source_name"].startswith("India Code")


def test_scaffold_without_citation_is_reported_incomplete():
    entry = _scaffold()
    assert "citation" in scaffold.missing_required_fields(entry)


def test_scaffold_includes_verified_excerpt_only():
    with_cite = _scaffold(citation="Section 3(p)")
    assert "full_text_excerpt" in with_cite
    assert extract.excerpt_present(
        extract_text(_result((FIX / "india_code_patents.html").read_bytes(), "u")).text,
        with_cite["full_text_excerpt"],
    )

    no_match = _scaffold(citation="Section 999")
    assert "full_text_excerpt" not in no_match


def test_scaffold_refuses_not_automatable_source():
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.scaffold_entry(
            "tkdl", "anything", regime="patent", id_slug="x", fetcher=fetcher_for({}), today=TODAY
        )


def test_scaffold_unknown_source():
    with pytest.raises(KeyError):
        get_source("not-a-source")


def test_scaffold_raises_on_fetch_failure():
    with pytest.raises(scaffold.ScaffoldError):
        scaffold.scaffold_entry(
            "india-code", "123456789/1", regime="patent", id_slug="x",
            fetcher=fetcher_for({}), today=TODAY,
        )


# ---------- writer ----------

@pytest.fixture
def tmp_corpus(tmp_path):
    india = [
        {
            "id": "in-existing-curated",
            "jurisdiction": "India",
            "regime": "patent",
            "title": "An existing hand-curated entry",
            "instrument": "Patents Act, 1970",
            "citation": "Section 3(p)",
            "instrument_type": "statute",
            "summary": "Curated.",
            "source_url": "https://www.indiacode.nic.in/handle/123456789/1388",
            "source_name": "India Code – The Patents Act, 1970",
            "last_verified": "2026-01-01",
            "tags": ["x"],
        }
    ]
    (tmp_path / "india.json").write_text(json.dumps(india, indent=2), encoding="utf-8")
    (tmp_path / "international.json").write_text("[]", encoding="utf-8")
    return tmp_path


def _new_entry(**over):
    e = {
        "id": "in-new-machine",
        "jurisdiction": "India",
        "regime": "gi",
        "title": "A scaffolded entry",
        "instrument": "GI Act, 1999",
        "citation": "Section 11",
        "instrument_type": "statute",
        "summary": "Machine summary.",
        "source_url": "https://www.indiacode.nic.in/handle/123456789/1889",
        "source_name": "India Code – GI Act, 1999",
        "last_verified": "2026-09-07",
        "tags": ["gi"],
        "review_status": "unreviewed",
    }
    e.update(over)
    return e


def test_writer_adds_new_entry_to_the_right_file(tmp_corpus):
    rep = writer.upsert_entries([_new_entry()], tmp_corpus)
    assert rep.added == ["in-new-machine"]
    assert "india.json" in rep.files_written
    reloaded = load_corpus(tmp_corpus)
    assert {d["id"] for d in reloaded} == {"in-existing-curated", "in-new-machine"}


def test_writer_will_not_clobber_a_curated_entry(tmp_corpus):
    collision = _new_entry(id="in-existing-curated", jurisdiction="India")
    rep = writer.upsert_entries([collision], tmp_corpus)
    assert rep.skipped_protected == ["in-existing-curated"]
    assert not rep.changed
    assert load_corpus(tmp_corpus)[0]["summary"] == "Curated."  # unchanged


def test_writer_force_overrides_protection(tmp_corpus):
    collision = _new_entry(id="in-existing-curated", summary="Overwritten.")
    rep = writer.upsert_entries([collision], tmp_corpus, force=True)
    assert rep.updated == ["in-existing-curated"]
    assert load_corpus(tmp_corpus)[0]["summary"] == "Overwritten."


def test_writer_updates_an_unreviewed_entry_without_force(tmp_corpus):
    writer.upsert_entries([_new_entry()], tmp_corpus)
    rep = writer.upsert_entries([_new_entry(summary="v2")], tmp_corpus)
    assert rep.updated == ["in-new-machine"]
    assert next(d for d in load_corpus(tmp_corpus) if d["id"] == "in-new-machine")["summary"] == "v2"


def test_writer_rejects_unknown_jurisdiction(tmp_corpus):
    with pytest.raises(ValueError):
        writer.upsert_entries([_new_entry(jurisdiction="Mars")], tmp_corpus)


def test_writer_output_is_valid_loadable_json(tmp_corpus):
    writer.upsert_entries([_new_entry()], tmp_corpus)
    raw = json.loads((tmp_corpus / "india.json").read_text())
    assert isinstance(raw, list) and len(raw) == 2


def test_bump_last_verified(tmp_corpus):
    changed = writer.bump_last_verified(["in-existing-curated"], tmp_corpus, today=TODAY)
    assert changed == ["in-existing-curated"]
    assert load_corpus(tmp_corpus)[0]["last_verified"] == "2026-09-07"
    # idempotent
    assert writer.bump_last_verified(["in-existing-curated"], tmp_corpus, today=TODAY) == []


# ---------- corpus structural guard ----------

def test_existing_corpus_entries_are_well_formed():
    required = (
        "id", "jurisdiction", "regime", "title", "instrument", "citation",
        "instrument_type", "summary", "source_url", "source_name", "last_verified", "tags",
    )
    for doc in load_corpus(config.CORPUS_DIR):
        missing = [k for k in required if k not in doc]
        assert not missing, f"{doc.get('id')}: missing {missing}"
        assert doc["source_url"].startswith("http")
        date.fromisoformat(doc["last_verified"])  # raises if malformed
