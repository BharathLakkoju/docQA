"""Phase 4 — run the 61-question stratified eval set against the real,
deployed retrieval + generation pipeline (agents.pipeline.handle_query),
not a mocked or simplified reimplementation, per INSTRUCTIONS.md Phase 4
step 3. Scores retrieval and generation SEPARATELY:

  - Retrieval:  ContextualPrecision, ContextualRecall (DeepEval)
  - Generation: Faithfulness, AnswerRelevancy (DeepEval)
  - Fix-generation items additionally get a parse-pass-rate — did the
    final returned snippet pass actionlint/the n8n schema — which is a
    code-specific check DeepEval/RAGAS don't natively cover.

Writes per-question results incrementally (one line per question, flushed
immediately) so an interrupted run loses at most the in-flight question,
not the whole batch — free-tier judge calls are the bottleneck here and
re-doing completed work would waste them. Re-running with the same
--out-dir skips questions already present in per_question.jsonl.

Reports real numbers, including mediocre ones, per CLAUDE.md's "no
fabricated/massaged eval results" rule.

Run as: python eval/run_eval.py [--limit N] [--out-dir eval/results]
"""
from __future__ import annotations

import argparse
import functools
import json
import sys
import time
from pathlib import Path
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.pipeline import handle_query  # noqa: E402
from deepeval.metrics import (  # noqa: E402
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase  # noqa: E402
from deepeval_models import get_judge_model  # noqa: E402

print = functools.partial(print, flush=True)  # noqa: A001 — this file's stdout is often redirected to a log file


def load_questions(path: Path, limit: int | None) -> list[dict]:
    items = [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]
    return items[:limit] if limit else items


def load_completed_ids(per_question_path: Path) -> set[str]:
    if not per_question_path.exists():
        return set()
    ids = set()
    for line in per_question_path.open(encoding="utf-8"):
        line = line.strip()
        if line:
            ids.add(json.loads(line)["id"])
    return ids


# Cap on chunks (and chars/chunk) shown to the judge for scoring — NOT a
# retrieval-quality change, retrieval itself still ran at its real top_k.
# A synthetic single-chunk test scored correctly in ~9s; the same metric
# against a real 8-10 chunk context reliably produced malformed JSON from
# the free judge model, burning minutes in DeepEval's own retries. This is
# a documented, honest limitation of a free small model as judge, not
# something to hide — see ATTRIBUTIONS.md / README eval caveats.
JUDGE_CONTEXT_MAX_CHUNKS = 5
JUDGE_CONTEXT_MAX_CHARS = 600


def score_qa_item(judge, item: dict, result) -> dict:
    all_chunks = (result.structured_chunks or []) + (result.prose_chunks or [])
    context_texts = [c.text[:JUDGE_CONTEXT_MAX_CHARS] for c in all_chunks[:JUDGE_CONTEXT_MAX_CHUNKS]]
    answer = result.answer

    tc = LLMTestCase(
        input=item["query"],
        actual_output=answer.answer,
        retrieval_context=context_texts or ["(no context retrieved)"],
        expected_output=item.get("gold_answer", ""),
    )

    scores: dict[str, float | None] = {}
    for name, metric_cls in [
        ("context_precision", ContextualPrecisionMetric),
        ("context_recall", ContextualRecallMetric),
        ("faithfulness", FaithfulnessMetric),
        ("answer_relevancy", AnswerRelevancyMetric),
    ]:
        try:
            metric = metric_cls(model=judge)
            metric.measure(tc, _show_indicator=False)
            scores[name] = metric.score
        except Exception as e:  # a single flaky judge call must not kill the whole eval run
            print(f"    [metric error] {name}: {e}", file=sys.stderr)
            scores[name] = None

    scores["declined"] = answer.declined
    return scores


def score_fix_item(item: dict, result) -> dict:
    fix = result.fix
    if fix is None:
        # The router disagreed with this item's curated task_type and sent
        # it down the Answer Generator path instead — a real routing
        # defect (see retrieval/query_router.py's FIX_MARKERS regression
        # tests), not something to paper over with a fabricated score.
        return {
            "parse_pass_rate": 0.0,
            "attempts": 0,
            "validator_errors": [
                f"router misclassified as {result.router.task_type} (needs_fix_generation="
                f"{result.router.needs_fix_generation}) — never reached the Fix Agent"
            ],
        }
    return {
        "parse_pass_rate": 1.0 if fix.validated else 0.0,
        "attempts": fix.attempts,
        "validator_errors": fix.validator_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="eval/question_set.jsonl")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out-dir", default="eval/results")
    args = parser.parse_args()

    questions = load_questions(Path(args.questions), args.limit)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_question_path = out_dir / "per_question.jsonl"

    completed_ids = load_completed_ids(per_question_path)
    if completed_ids:
        print(f"Resuming: {len(completed_ids)} questions already scored in {per_question_path}, skipping those.")

    judge = get_judge_model()

    with per_question_path.open("a", encoding="utf-8") as out_f:
        for i, item in enumerate(questions, start=1):
            if item["id"] in completed_ids:
                continue

            print(f"[{i}/{len(questions)}] {item['domain']}/{item['task_type']}: {item['query'][:70]}")
            t0 = time.time()
            try:
                result = handle_query(item["query"])
            except Exception as e:
                print(f"  [pipeline error] {e}", file=sys.stderr)
                record = {**item, "error": str(e)}
                out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
                out_f.flush()
                continue
            elapsed = time.time() - t0

            record = {"id": item["id"], "domain": item["domain"], "task_type": item["task_type"], "elapsed_sec": elapsed}
            if item["task_type"] == "fix_generation":
                record["scores"] = score_fix_item(item, result)
            else:
                record["scores"] = score_qa_item(judge, item, result)

            out_f.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_f.flush()
            print(f"  done in {elapsed:.1f}s -> {record['scores']}")

    per_question = [json.loads(l) for l in per_question_path.open(encoding="utf-8") if l.strip()]
    aggregate = build_aggregate(per_question)
    aggregate_path = out_dir / "aggregate.json"
    aggregate_path.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")

    print(f"\nPer-question results -> {per_question_path}")
    print(f"Aggregate results    -> {aggregate_path}")
    print(json.dumps(aggregate, indent=2))


def build_aggregate(per_question: list[dict]) -> dict:
    qa_records = [r for r in per_question if r.get("task_type") != "fix_generation" and "scores" in r]
    fix_records = [r for r in per_question if r.get("task_type") == "fix_generation" and "scores" in r]

    def avg(records: list[dict], key: str) -> float | None:
        vals = [r["scores"][key] for r in records if r["scores"].get(key) is not None]
        return round(mean(vals), 3) if vals else None

    aggregate = {
        "total_questions": len(per_question),
        "errored_questions": sum(1 for r in per_question if "error" in r),
        "qa_metrics": {
            "n": len(qa_records),
            "context_precision": avg(qa_records, "context_precision"),
            "context_recall": avg(qa_records, "context_recall"),
            "faithfulness": avg(qa_records, "faithfulness"),
            "answer_relevancy": avg(qa_records, "answer_relevancy"),
            "decline_rate": round(mean([1.0 if r["scores"]["declined"] else 0.0 for r in qa_records]), 3) if qa_records else None,
        },
        "fix_generation_metrics": {
            "n": len(fix_records),
            "parse_pass_rate": avg(fix_records, "parse_pass_rate"),
            "avg_attempts": avg(fix_records, "attempts"),
        },
        "by_domain": {},
    }

    for domain in ("n8n", "github_actions", "api_errors"):
        domain_qa = [r for r in qa_records if r["domain"] == domain]
        domain_fix = [r for r in fix_records if r["domain"] == domain]
        aggregate["by_domain"][domain] = {
            "context_precision": avg(domain_qa, "context_precision"),
            "context_recall": avg(domain_qa, "context_recall"),
            "faithfulness": avg(domain_qa, "faithfulness"),
            "answer_relevancy": avg(domain_qa, "answer_relevancy"),
            "parse_pass_rate": avg(domain_fix, "parse_pass_rate") if domain_fix else None,
        }

    return aggregate


if __name__ == "__main__":
    main()
