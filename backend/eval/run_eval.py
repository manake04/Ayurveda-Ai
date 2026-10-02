"""Retrieval quality and abstention eval, plus latency.

    python -m eval.run_eval              # uses the models configured in .env
    python -m eval.run_eval --llm        # also generate answers and check their [n] citations

Exits non-zero if any case fails, so it can gate CI or a model change. It also prints the
score range of answerable vs. off-topic questions and a suggested abstention threshold,
since those thresholds are specific to each embedding model.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.container import Container
from app.schemas.ask import AskRequest

EVAL_SET = Path(__file__).resolve().parent / "eval_set.jsonl"


async def main(with_llm: bool) -> int:
    settings = get_settings()
    if not with_llm:
        settings = settings.model_copy(update={"llm_provider": "none", "answer_cache_size": 0})
    c = await Container.create(settings)
    cases = [json.loads(line) for line in EVAL_SET.read_text(encoding="utf-8").splitlines() if line.strip()]

    failures, hit1, hitk, latencies = 0, 0, 0, []
    pos_scores, neg_scores = [], []
    for case in cases:
        jur = case["jurisdiction"]
        t = time.perf_counter()
        result = (await c.retriever.retrieve(case["query"], [jur]))[jur]
        latencies.append((time.perf_counter() - t) * 1000)
        ids = [d["id"] for d, _ in result.hits]
        top = result.hits[0][1] if result.hits else float("-inf")

        if case["expect_abstain"]:
            neg_scores.append(top)
            ok = result.abstained
            detail = f"abstained={ok} top={top:.3f}"
        else:
            pos_scores.append(top)
            expected = set(case["expected_citation_ids"])
            hit1 += bool(ids[:1] and ids[0] in expected)
            hitk += bool(expected & set(ids))
            ok = bool(expected & set(ids)) and not result.abstained
            detail = f"top={ids[:1]} ({top:.3f}) expected one of {sorted(expected)}"
            if ok and with_llm:
                answer = (await c.pipeline.answer(AskRequest(query=case["query"], jurisdiction=jur))).answers[
                    0
                ]
                cited = {cit.id for cit in answer.citations if f"[{cit.ref}]" in answer.answer}
                ok = bool(expected & cited)
                detail += f" | answer cites {sorted(cited)} via {answer.generated_by}"
        failures += not ok
        print(f"[{'PASS' if ok else 'FAIL'}] {case['query'][:60]:60} {detail}")

    n_pos = len(pos_scores)
    print("\n--- Summary ---")
    print(
        f"Models:            embeddings={c.retriever.embedder.name} reranker={settings.reranker_model or 'off'}"
    )
    print(f"Top-1 accuracy:    {hit1}/{n_pos}")
    print(f"Top-{settings.top_k} recall:     {hitk}/{n_pos}")
    print(
        f"Abstention:        {sum(1 for s in neg_scores if s < (settings.rerank_confidence_abstain if settings.reranker_model else settings.confidence_abstain))}/{len(neg_scores)} off-topic questions declined"
    )
    print(
        f"Score ranges:      answerable min {min(pos_scores):.3f} / median {statistics.median(pos_scores):.3f}; off-topic max {max(neg_scores):.3f}"
    )
    if min(pos_scores) > max(neg_scores):
        print(f"Suggested abstain threshold: {(min(pos_scores) + max(neg_scores)) / 2:.3f}")
    else:
        print("Warning: answerable and off-topic score ranges overlap.")
    print(f"Retrieval latency: median {statistics.median(latencies):.0f} ms, max {max(latencies):.0f} ms")
    print(f"\n{failures} failure(s)")
    await c.close()
    return failures


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", action="store_true", help="also generate and check answers")
    args = parser.parse_args()
    sys.exit(1 if asyncio.run(main(args.llm)) else 0)
