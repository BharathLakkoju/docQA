"""Phase 1a — chunk the ScraperNode/awesome-n8n-templates GitHub mirror
(MIT licensed) for extra volume and category diversity beyond the official
template API pull.

Samples up to --per-category workflows from each category directory
(deterministic, sorted order — not random — so re-runs are reproducible)
rather than ingesting all ~8,700, to keep the corpus size proportionate to
what a portfolio-scale Pinecone free-tier index should hold. This is a
documented, honest subsample, not the full mirror.

Input:  data/raw/n8n/awesome-n8n-templates/templates/<category>/<slug>/workflow.json
Output: appends to data/processed/n8n/structured_chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from node_chunking import chunk_workflow

SOURCE = "awesome_n8n_templates_mirror"
LICENSE = "MIT (ScraperNode/awesome-n8n-templates); underlying workflows belong to original template authors"
REPO_URL = "https://github.com/ScraperNode/awesome-n8n-templates"


def iter_category_dirs(templates_root: Path):
    for category_dir in sorted(templates_root.iterdir()):
        if category_dir.is_dir():
            yield category_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-dir", default="data/raw/n8n/awesome-n8n-templates")
    parser.add_argument("--out-file", default="data/processed/n8n/structured_chunks.jsonl")
    parser.add_argument("--per-category", type=int, default=30, help="max workflows sampled per category dir")
    args = parser.parse_args()

    templates_root = Path(args.repo_dir) / "templates"
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0
    total_templates = 0
    per_category_counts: dict[str, int] = {}

    with out_file.open("a", encoding="utf-8") as out:
        for category_dir in iter_category_dirs(templates_root):
            category = category_dir.name
            workflow_files = sorted(category_dir.glob("*/workflow.json"))[: args.per_category]
            per_category_counts[category] = len(workflow_files)

            for wf_path in workflow_files:
                try:
                    inner = json.loads(wf_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as e:
                    print(f"  [skip] {wf_path}: {e}", file=sys.stderr)
                    continue
                if not inner.get("nodes"):
                    continue

                slug = wf_path.parent.name  # e.g. "3108-seo-keyword-analysis-and-filter"
                template_id = f"mirror-{slug}"
                template_name = inner.get("name") or slug
                source_url = f"{REPO_URL}/tree/main/templates/{category}/{slug}"

                chunks = chunk_workflow(
                    inner, template_id, template_name, [category], SOURCE, source_url, LICENSE
                )
                if not chunks:
                    continue
                total_templates += 1
                for chunk in chunks:
                    out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    total_chunks += 1

    print(f"Sampled {total_templates} mirror templates across {len(per_category_counts)} categories")
    for cat, n in sorted(per_category_counts.items()):
        print(f"  {cat}: {n}")
    print(f"Appended {total_chunks} node chunks -> {out_file}")


if __name__ == "__main__":
    main()
