"""Phase 4 — build the stratified eval question set from real corpus data.

Stratified across domain x task_type. fix_generation only applies to
n8n / github_actions (api_errors has no structured corpus to ground a fix
in — same constraint the Query Router enforces in production, see
retrieval/query_router.py's needs_fix_generation logic), so the design is
honestly 8 strata, not 9:

  n8n:          factual_lookup, error_diagnosis, fix_generation
  github_actions: factual_lookup, error_diagnosis, fix_generation
  api_errors:   factual_lookup, error_diagnosis

factual_lookup and error_diagnosis items are sampled programmatically from
real ingested content (doc pages, accepted-answer forum/SE threads) so
gold answers are genuine text, not invented. fix_generation items are
hand-curated (curated_fix_generation.py) because they need a coherent
natural-language task description paired with a real corrected snippet —
that pairing can't be sampled mechanically without risking a mismatched
or fabricated gold answer.

Output: eval/question_set.jsonl
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from curated_fix_generation import FIX_GENERATION_ITEMS

random.seed(42)  # reproducible sampling

N_FACTUAL_PER_DOMAIN = 8
N_ERROR_DIAGNOSIS_PER_DOMAIN = 8


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(l) for l in path.open(encoding="utf-8") if l.strip()]


def sample_factual_n8n_docs(n: int) -> list[dict]:
    chunks = load_jsonl(Path("data/processed/n8n/prose_chunks.jsonl"))
    # Prefer integration/node reference pages — self-contained, single clear topic per chunk.
    candidates = [c for c in chunks if c["metadata"].get("section") == "integrations" and c["metadata"]["chunk_index"] == 0]
    picked = random.sample(candidates, min(n, len(candidates)))
    items = []
    for c in picked:
        title = c["metadata"]["title"]
        items.append(
            {
                "domain": "n8n",
                "task_type": "factual_lookup",
                "query": f"What does the {title.replace(' documentation', '')} do in n8n?",
                "gold_answer": c["text"].split("\n\n", 1)[-1][:800],
                "source_url": c["metadata"]["source_url"],
            }
        )
    return items


def sample_factual_github_actions(n: int) -> list[dict]:
    chunks = load_jsonl(Path("data/processed/github_actions/structured_chunks.jsonl"))
    # One question per distinct action seen in actions_used, paired with the job chunk using it.
    seen_actions = set()
    items = []
    random.shuffle(chunks)
    for c in chunks:
        for action in c["metadata"].get("actions_used", []):
            action_name = action.split("@")[0]
            if action_name in seen_actions or len(items) >= n:
                continue
            seen_actions.add(action_name)
            items.append(
                {
                    "domain": "github_actions",
                    "task_type": "factual_lookup",
                    "query": f"In this GitHub Actions job, what is the `{action_name}` step doing and how is it configured?",
                    "gold_answer": c["text"][:600],
                    "source_url": c["metadata"]["source_url"],
                    "note": "Gold answer is real usage context from an ingested job chunk, not an authoritative action description (action READMEs weren't ingested — see ATTRIBUTIONS.md/CLAUDE.md for corpus scope).",
                }
            )
        if len(items) >= n:
            break
    return items


def sample_factual_api_errors(n: int) -> list[dict]:
    chunks = load_jsonl(Path("data/processed/api_errors/mdn_status_chunks.jsonl"))
    first_chunks = [c for c in chunks if c["metadata"]["chunk_index"] == 0]
    picked = random.sample(first_chunks, min(n, len(first_chunks)))
    items = []
    for c in picked:
        code = c["metadata"]["status_code"]
        items.append(
            {
                "domain": "api_errors",
                "task_type": "factual_lookup",
                "query": f"What does HTTP status code {code} mean?",
                "gold_answer": c["text"].split("\n\n", 1)[-1][:800],
                "source_url": c["metadata"]["source_url"],
            }
        )
    return items


def sample_error_diagnosis_n8n(n: int) -> list[dict]:
    chunks = load_jsonl(Path("data/processed/n8n/forum_chunks.jsonl"))
    accepted = [c for c in chunks if c["metadata"]["has_accepted_answer"]]
    picked = random.sample(accepted, min(n, len(accepted)))
    items = []
    for c in picked:
        text = c["text"]
        question_part = text.split("## Accepted answer")[0].replace("## Question", "").strip()
        answer_part = text.split("## Accepted answer", 1)[-1].strip()
        items.append(
            {
                "domain": "n8n",
                "task_type": "error_diagnosis",
                "query": c["metadata"]["title"],
                "context_note": question_part[:500],
                "gold_answer": answer_part[:800],
                "source_url": c["metadata"]["source_url"],
            }
        )
    return items


def sample_error_diagnosis_from_se(domain: str, tags: set[str], n: int) -> list[dict]:
    chunks = load_jsonl(Path("data/processed/api_errors/stackexchange_chunks.jsonl"))
    candidates = [c for c in chunks if c["metadata"]["has_accepted_answer"] and set(c["metadata"]["tags"]) & tags]
    picked = random.sample(candidates, min(n, len(candidates)))
    items = []
    for c in picked:
        text = c["text"]
        answer_part = text.split("## Accepted answer", 1)[-1].strip()
        items.append(
            {
                "domain": domain,
                "task_type": "error_diagnosis",
                "query": c["metadata"]["title"],
                "gold_answer": answer_part[:800],
                "source_url": c["metadata"]["source_url"],
            }
        )
    return items


def main() -> None:
    items: list[dict] = []
    items += sample_factual_n8n_docs(N_FACTUAL_PER_DOMAIN)
    items += sample_factual_github_actions(N_FACTUAL_PER_DOMAIN)
    items += sample_factual_api_errors(N_FACTUAL_PER_DOMAIN)
    items += sample_error_diagnosis_n8n(N_ERROR_DIAGNOSIS_PER_DOMAIN)
    items += sample_error_diagnosis_from_se("github_actions", {"github-actions"}, N_ERROR_DIAGNOSIS_PER_DOMAIN)
    items += sample_error_diagnosis_from_se("api_errors", {"rest", "http", "http-status-codes"}, N_ERROR_DIAGNOSIS_PER_DOMAIN)
    items += FIX_GENERATION_ITEMS

    for i, item in enumerate(items):
        item["id"] = f"eval-{i:03d}"

    out_path = Path("eval/question_set.jsonl")
    with out_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    by_stratum: dict[str, int] = {}
    for item in items:
        key = f"{item['domain']}/{item['task_type']}"
        by_stratum[key] = by_stratum.get(key, 0) + 1

    print(f"Built {len(items)} eval questions -> {out_path}")
    for k, v in sorted(by_stratum.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
