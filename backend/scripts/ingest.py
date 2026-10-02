#!/usr/bin/env python
"""Corpus ingestion & verification CLI.

    cd backend
    python scripts/ingest.py sources [--markdown]
    python scripts/ingest.py verify [--stale-days 180] [--json PATH] [--fail-on unreachable,excerpt_drift]
    python scripts/ingest.py scaffold --source india-code --locator 123456789/1388 \
        --regime patent --id in-patents-example [--title ...] [--citation "Section 3(p)"] [--write]
    python scripts/ingest.py refresh-verified [--stale-days 180]

`scaffold --write` and `refresh-verified` change corpus/*.json — rerun
`python scripts/build_index.py` and `python scripts/build_graph.py` afterwards.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.ingest import report as report_mod  # noqa: E402
from app.ingest import scaffold as scaffold_mod  # noqa: E402
from app.ingest import writer as writer_mod  # noqa: E402
from app.ingest.sources import SOURCE_REGISTRY, registry_markdown  # noqa: E402

_STATUS_ORDER = ["ok", "stale", "unverifiable", "excerpt_drift", "unreachable"]


def cmd_sources(args: argparse.Namespace) -> int:
    if args.markdown:
        print(registry_markdown())
        return 0
    print(f"{'id':<16} {'jurisdiction':<14} {'fetch':<16} name")
    print("-" * 78)
    for src in SOURCE_REGISTRY.values():
        print(f"{src.id:<16} {src.jurisdiction:<14} {src.fetch_kind:<16} {src.name}")
        if src.access_notes:
            print(f"{'':<16} └─ {src.access_notes}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    rep = report_mod.verify_corpus(config.CORPUS_DIR, stale_days=args.stale_days)
    out_path = Path(args.json) if args.json else config.VERIFY_REPORT_PATH
    rep.write(out_path)

    print(f"Verified {rep.total} corpus entries (stale threshold: {args.stale_days} days)")
    for status in _STATUS_ORDER:
        n = rep.counts.get(status, 0)
        if n:
            print(f"  {status:<14} {n}")
    for r in rep.results:
        if r["status"] not in ("ok",):
            print(f"    [{r['status']}] {r['id']}: {r['detail'] or r['source_url']}")
    print(f"Report written to {out_path}")

    fail_on = {s.strip() for s in (args.fail_on or "").split(",") if s.strip()}
    if fail_on and any(rep.counts.get(s, 0) for s in fail_on):
        print(f"FAIL: one or more entries in {sorted(fail_on)}", file=sys.stderr)
        return 1
    return 0


def cmd_scaffold(args: argparse.Namespace) -> int:
    try:
        entry = scaffold_mod.scaffold_entry(
            args.source,
            args.locator,
            regime=args.regime,
            id_slug=args.id,
            jurisdiction=args.jurisdiction,
            title=args.title,
            instrument=args.instrument,
            citation=args.citation,
            instrument_type=args.instrument_type,
        )
    except (scaffold_mod.ScaffoldError, KeyError) as exc:
        print(f"scaffold failed: {exc}", file=sys.stderr)
        return 1

    missing = scaffold_mod.missing_required_fields(entry)
    print(json.dumps(entry, indent=2, ensure_ascii=False))
    if missing:
        print(f"\n! incomplete — fill these before relying on the entry: {missing}", file=sys.stderr)

    if not args.write:
        print("\n(dry run — pass --write to add this to the corpus)", file=sys.stderr)
        return 0

    wr = writer_mod.upsert_entries([entry], config.CORPUS_DIR, force=args.force)
    if wr.skipped_protected:
        print(f"\nskipped (protected, use --force): {wr.skipped_protected}", file=sys.stderr)
        return 1
    print(
        f"\nwrote {wr.files_written}: added={wr.added} updated={wr.updated}\n"
        "Now run:  python scripts/build_index.py && python scripts/build_graph.py",
        file=sys.stderr,
    )
    return 0


def cmd_refresh_verified(args: argparse.Namespace) -> int:
    rep = report_mod.verify_corpus(config.CORPUS_DIR, stale_days=args.stale_days)
    ok_ids = [r["id"] for r in rep.results if r["status"] == "ok"]
    stale_ids = [r["id"] for r in rep.results if r["status"] == "stale"]
    changed = writer_mod.bump_last_verified(ok_ids + stale_ids, config.CORPUS_DIR)
    print(f"{len(ok_ids) + len(stale_ids)} entries verified clean; bumped last_verified on {len(changed)}")
    if changed:
        print("  " + ", ".join(changed))
        print("Now run:  python scripts/build_index.py && python scripts/build_graph.py")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_sources = sub.add_parser("sources", help="list the source registry")
    p_sources.add_argument("--markdown", action="store_true", help="emit docs/SOURCES.md body")
    p_sources.set_defaults(func=cmd_sources)

    p_verify = sub.add_parser("verify", help="re-check every entry's source_url")
    p_verify.add_argument("--stale-days", type=int, default=180)
    p_verify.add_argument("--json", help="report output path (default: data/ingest/verify_report.json)")
    p_verify.add_argument("--fail-on", help="comma-separated statuses that should exit non-zero")
    p_verify.set_defaults(func=cmd_verify)

    p_scaffold = sub.add_parser("scaffold", help="build a corpus entry from a source locator")
    p_scaffold.add_argument("--source", required=True, choices=sorted(SOURCE_REGISTRY))
    p_scaffold.add_argument("--locator", required=True, help="handle id, CELEX id, or full URL")
    p_scaffold.add_argument("--regime", required=True)
    p_scaffold.add_argument("--id", required=True, help="stable corpus id slug")
    p_scaffold.add_argument("--jurisdiction", choices=["India", "International"])
    p_scaffold.add_argument("--title")
    p_scaffold.add_argument("--instrument")
    p_scaffold.add_argument("--citation")
    p_scaffold.add_argument("--instrument-type", dest="instrument_type")
    p_scaffold.add_argument("--write", action="store_true", help="write into corpus/*.json")
    p_scaffold.add_argument("--force", action="store_true", help="overwrite a curated entry")
    p_scaffold.set_defaults(func=cmd_scaffold)

    p_refresh = sub.add_parser("refresh-verified", help="bump last_verified on entries that check out")
    p_refresh.add_argument("--stale-days", type=int, default=180)
    p_refresh.set_defaults(func=cmd_refresh_verified)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
