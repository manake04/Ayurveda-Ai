#!/usr/bin/env python
"""Evaluation harness for IP-SAKTI Sahayak's retrieval/citation/abstention quality.

Checks the things the problem statement calls out as evaluable:
  1. Citation correctness -- does the top retrieved citation match what we expect?
  2. Safe abstention -- does the assistant correctly decline out-of-scope queries?
  3. (v2) For "mode": "agentic" cases -- does the rule-based planner decompose a compound,
     multi-jurisdiction/multi-regime question into the expected number of steps, and does
     the union of citations across all its sections still contain what we expect? Agentic
     abstention means *every* planned section abstained (a fully out-of-scope compound
     question), not just one.
  4. (Answer accuracy and multilingual quality are noted as TODOs -- see docs/ROADMAP.md;
     they need either human graders or a larger gold set than an MVP ships with.)

Usage:
    cd backend && python eval/run_eval.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config  # noqa: E402
from app.agent import run_agentic  # noqa: E402
from app.graph import GraphStore  # noqa: E402
from app.rag import answer_for_jurisdiction  # noqa: E402
from app.vectorstore import VectorStore  # noqa: E402


def _run_standard_case(store, case) -> tuple[bool, str]:
    result = answer_for_jurisdiction(store, case["query"], case["jurisdiction"], config.TOP_K)
    got_ids = {c.id for c in result.citations}

    if case["expect_abstain"]:
        ok = result.abstained
        detail = f"abstained={result.abstained} confidence={result.confidence}"
    else:
        expected = set(case["expected_citation_ids"])
        ok = bool(expected & got_ids)
        detail = f"expected one of {expected}, got {got_ids or '{}'}"
    return ok, detail


def _run_agentic_case(store, graph_store, case) -> list[tuple[bool, str]]:
    """An agentic case can check several things at once (step count, citation coverage,
    full-abstention) -- each becomes its own (ok, detail) result so the summary counts
    stay meaningful per-dimension rather than collapsing into one pass/fail."""
    result = run_agentic(store, graph_store, case["query"], case["jurisdiction"], config.TOP_K)
    got_ids = {c.id for section in result.sections for c in section.citations}
    all_abstained = all(section.abstained for section in result.sections)
    results = []

    if "min_steps" in case or "max_steps" in case:
        lo = case.get("min_steps", 0)
        hi = case.get("max_steps", float("inf"))
        ok = lo <= len(result.steps) <= hi
        results.append(("steps", ok, f"{len(result.steps)} step(s) (expected {lo}-{hi})"))

    if case.get("expect_abstain"):
        results.append(("abstain", all_abstained, f"all_sections_abstained={all_abstained}"))
    elif "expect_all_of" in case:
        expected_all = set(case["expect_all_of"])
        ok = expected_all.issubset(got_ids)
        results.append(("citation", ok, f"expected ALL of {expected_all}, got {got_ids or '{}'}"))
    elif "expected_citation_ids" in case:
        expected = set(case["expected_citation_ids"])
        ok = bool(expected & got_ids)
        results.append(("citation", ok, f"expected one of {expected}, got {got_ids or '{}'}"))

    return results


def main():
    store = VectorStore()
    store.build(config.CORPUS_DIR, config.INDEX_DIR)

    graph_store = GraphStore()
    try:
        graph_store.load(config.GRAPH_DIR)
    except FileNotFoundError:
        graph_store.build(config.CORPUS_DIR, config.GRAPH_EDGES_PATH, config.GRAPH_DIR)

    eval_path = Path(__file__).resolve().parent / "eval_set.jsonl"
    cases = [json.loads(line) for line in eval_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    tallies = {}  # dimension -> [n_correct, n_total]

    def record(dimension, ok):
        n_correct, n_total = tallies.get(dimension, [0, 0])
        tallies[dimension] = [n_correct + int(ok), n_total + 1]

    print(f"Running {len(cases)} eval cases...\n")
    for case in cases:
        mode = case.get("mode", "standard")
        label = "agentic" if mode == "agentic" else ("abstain" if case.get("expect_abstain") else "citation")

        if mode == "agentic":
            for dimension, ok, detail in _run_agentic_case(store, graph_store, case):
                status = "PASS" if ok else "FAIL"
                print(f"[{status}] (agentic/{dimension}) '{case['query'][:60]}' -> {detail}")
                record(f"agentic_{dimension}", ok)
        else:
            ok, detail = _run_standard_case(store, case)
            status = "PASS" if ok else "FAIL"
            print(f"[{status}] ({label}) '{case['query'][:60]}' -> {detail}")
            record(label, ok)

    print("\n--- Summary ---")
    dimension_labels = {
        "citation": "Citation correctness",
        "abstain": "Safe abstention",
        "agentic_steps": "Agentic step-count accuracy",
        "agentic_citation": "Agentic citation coverage",
        "agentic_abstain": "Agentic full-abstention correctness",
    }
    for dimension, (n_correct, n_total) in tallies.items():
        label = dimension_labels.get(dimension, dimension)
        print(f"{label + ':':<40} {n_correct}/{n_total} ({100 * n_correct / n_total:.0f}%)")


if __name__ == "__main__":
    main()
