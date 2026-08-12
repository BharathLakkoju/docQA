"""agentic_ai domain — semantic chunking of Markdown/MDX prose docs across
six of the seven approved sources (see ATTRIBUTIONS.md's Agentic AI section
for the licensing rationale behind this source list).

Two of these sources are split by domain, not just by artifact_type:
`github-docs/content/actions` is real docs.github.com content for GitHub
Actions itself (fixing the pre-existing gap where github_actions had zero
prose corpus — see CLAUDE.md's original gap analysis) and is tagged
`domain: github_actions`, while everything else here is `domain: agentic_ai`.

Same windowing as ingestion/n8n/chunk_docs.py: common/prose_chunking.py's
~600-token / 100-token-overlap paragraph packing. source_url always points
at the real GitHub blob (not a guessed docs-site route) so every citation
is dereferenceable without risking a wrong rendered-site path.

Output:
  data/processed/github_actions/doc_prose_chunks.jsonl   (github_actions domain slice)
  data/processed/agentic_ai/doc_prose_chunks.jsonl        (agentic_ai domain slice)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agentic_ai.github_docs_liquid import load_variables, resolve as resolve_liquid  # noqa: E402
from common.chunk_ids import stable_chunk_id  # noqa: E402
from common.prose_chunking import pack_into_windows, parse_frontmatter, split_paragraphs  # noqa: E402

MDX_IMPORT_RE = re.compile(r"^import\s+.+\s+from\s+['\"].+['\"];?\s*$", re.MULTILINE)
JSX_TAG_RE = re.compile(r"</?[A-Z][A-Za-z]*[^>]*/?>")
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass
class DocSource:
    name: str
    domain: str
    root: Path
    pattern: str
    repo: str  # "org/repo" for the GitHub blob URL
    license: str
    exclude_substrings: tuple[str, ...] = ()
    liquid: bool = False  # github/docs' Liquid templating needs variable resolution, see github_docs_liquid.py
    exclude_files: tuple[str, ...] = ()  # relative paths with unresolvable {% for/case/assign %} data-table loops


SOURCES = [
    DocSource(
        name="github_docs_actions",
        domain="github_actions",
        root=Path("data/raw/agentic_ai/github-docs/content/actions"),
        pattern="**/*.md",
        repo="github/docs",
        license="CC-BY-4.0",
        liquid=True,
        exclude_files=("how-tos/manage-runners/self-hosted-runners/configure-the-application.md",),
    ),
    DocSource(
        name="github_docs_copilot",
        domain="agentic_ai",
        root=Path("data/raw/agentic_ai/github-docs/content/copilot"),
        pattern="**/*.md",
        repo="github/docs",
        license="CC-BY-4.0",
        liquid=True,
        exclude_files=(
            "reference/ai-models/model-comparison.md",
            "reference/ai-models/supported-models.md",
            "reference/copilot-billing/models-and-pricing.md",
            "reference/copilot-billing/request-based-billing-legacy/model-multipliers-for-annual-plans.md",
            "reference/copilot-feature-matrix.md",
        ),
    ),
    DocSource(
        name="mcp_docs",
        domain="agentic_ai",
        root=Path("data/raw/agentic_ai/mcp/docs"),
        pattern="**/*.mdx",
        repo="modelcontextprotocol/modelcontextprotocol",
        license="CC-BY-4.0",
        # Skip older dated spec-version snapshots (2024-11-05, 2025-03-26, ...) to
        # avoid indexing the same conceptual pages six times over; keep the latest
        # dated snapshot plus everything outside docs/docs/{date} (community, dev).
        exclude_substrings=("docs/2024-11-05", "docs/2025-03-26", "docs/2025-06-18", "docs/2025-11-25", "docs/draft"),
    ),
    DocSource(
        name="crewai_docs",
        domain="agentic_ai",
        root=Path("data/raw/agentic_ai/crewai/docs/edge/en"),
        pattern="**/*.mdx",
        repo="crewAIInc/crewAI",
        license="MIT",
    ),
    DocSource(
        name="openai_agents_sdk_docs",
        domain="agentic_ai",
        root=Path("data/raw/agentic_ai/openai-agents-python/docs"),
        pattern="**/*.md",
        repo="openai/openai-agents-python",
        license="MIT",
        # Real bug, caught by an eval question landing on a Korean-titled
        # chunk: docs/{ja,ko,zh}/ are full translations of the same English
        # docs, silently mixed into what was assumed to be an English-only
        # corpus (111 of 386 files, ~29%) — excluded. ref/ (239 files) is
        # mkdocstrings-generated API reference, same low-conceptual-density
        # reasoning as transformers/model_doc.
        exclude_substrings=("ja/", "ko/", "zh/", "ref/"),
    ),
    DocSource(
        name="autogen_docs",
        domain="agentic_ai",
        root=Path("data/raw/agentic_ai/autogen/python"),
        pattern="**/*.md",
        repo="microsoft/autogen",
        license="CC-BY-4.0",
    ),
    # --- Phase 9 additions (2026-08-12): OpenAI Codex, HuggingFace, LangChain ---
    DocSource(
        name="openai_codex_docs",
        domain="agentic_ai",
        root=Path("data/raw/agentic_ai/openai-codex/docs"),
        pattern="**/*.md",
        repo="openai/codex",
        license="Apache-2.0",
    ),
    DocSource(
        name="huggingface_hub_docs",
        domain="agentic_ai",
        root=Path("data/raw/agentic_ai/huggingface-hub-docs/docs/hub"),
        pattern="**/*.md",
        repo="huggingface/hub-docs",
        license="Apache-2.0",
    ),
    DocSource(
        name="huggingface_transformers_docs",
        domain="agentic_ai",
        root=Path("data/raw/agentic_ai/huggingface-transformers/docs/source/en"),
        pattern="**/*.md",
        repo="huggingface/transformers",
        license="Apache-2.0",
        # model_doc/ alone is 513 near-identical per-architecture reference pages
        # (BertConfig, BertModel, BertTokenizer, ...) — low conceptual density,
        # would dominate the corpus by sheer volume for little retrieval value.
        # internal/kernel_doc/serve-cli/community_integrations/reference are
        # similarly deep API-reference material, not conceptual guides. Kept:
        # top-level guides, tasks/ (fine-tuning, generation, ...), quantization/,
        # main_classes/ (Trainer, etc.) — the "how do I actually use this"
        # content, per the use case this source was added for.
        exclude_substrings=("model_doc/", "internal/", "kernel_doc/", "serve-cli/", "community_integrations/", "reference/"),
    ),
    DocSource(
        name="langchain_docs",
        domain="agentic_ai",
        root=Path("data/raw/agentic_ai/langchain-docs/src/oss"),
        pattern="**/*.mdx",
        repo="langchain-ai/docs",
        license="MIT",
        # python/integrations/ is hundreds of thin per-provider pages (same
        # low-density issue as transformers/model_doc); javascript/ duplicates
        # python/ for a language this project doesn't otherwise touch;
        # reference/contributing/openwiki are API reference / meta content,
        # not conceptual guides. Kept: langchain/, langgraph/ (this repo has
        # real LangGraph prose, unlike langgraph's own repo whose docs/ moved
        # off-repo to a dead link-index — see ATTRIBUTIONS.md), concepts/,
        # deepagents/, and the handful of top-level guide pages.
        exclude_substrings=("python/", "javascript/", "reference/", "contributing/", "openwiki/", "images/", "frontend/"),
    ),
]


def strip_doc_noise(body: str) -> str:
    # Every huggingface/transformers doc opens with an Apache-License HTML
    # comment block before the real heading — left unstripped, it was getting
    # picked up as the extracted "title" instead of the actual page heading.
    body = HTML_COMMENT_RE.sub("", body)
    body = MDX_IMPORT_RE.sub("", body)
    body = JSX_TAG_RE.sub("", body)
    return body


def chunk_doc_file(path: Path, src: DocSource, variables: dict[str, str]) -> list[dict]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if src.liquid:
        raw = resolve_liquid(raw, variables)
    meta, body = parse_frontmatter(raw)
    body = strip_doc_noise(body)
    paragraphs = split_paragraphs(body)
    if not paragraphs:
        return []

    rel_path = path.relative_to(src.root).as_posix()
    title = meta.get("title") or (paragraphs[0].lstrip("# ").split("\n")[0] if paragraphs else rel_path)
    # Points at the real cloned blob path; good enough to reconstruct a
    # dereferenceable GitHub URL without guessing the rendered docs-site route.
    full_repo_path = f"{src.root.as_posix().split('data/raw/agentic_ai/', 1)[-1].split('/', 1)[-1]}/{rel_path}"
    url = f"https://github.com/{src.repo}/blob/main/{full_repo_path}"

    windows = pack_into_windows(paragraphs)
    chunks = []
    for i, window in enumerate(windows):
        if not window.strip():
            continue
        chunks.append(
            {
                "id": stable_chunk_id(f"{src.name}-doc", rel_path, str(i)),
                "text": f"# {title}\n\n{window}",
                "metadata": {
                    "domain": src.domain,
                    "artifact_type": "doc_prose",
                    "title": title,
                    "source_path": rel_path,
                    "source_url": url,
                    "chunk_index": i,
                    "source": src.name,
                    "license": src.license,
                },
            }
        )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir-github-actions", default="data/processed/github_actions")
    parser.add_argument("--out-dir-agentic-ai", default="data/processed/agentic_ai")
    parser.add_argument("--github-docs-variables-dir", default="data/raw/agentic_ai/github-docs/data/variables")
    args = parser.parse_args()

    variables = load_variables(Path(args.github_docs_variables_dir))
    print(f"Loaded {len(variables)} github/docs Liquid variables for resolution")

    out_paths = {
        "github_actions": Path(args.out_dir_github_actions) / "doc_prose_chunks.jsonl",
        "agentic_ai": Path(args.out_dir_agentic_ai) / "doc_prose_chunks.jsonl",
    }
    for p in out_paths.values():
        p.parent.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    handles = {domain: path.open("w", encoding="utf-8") for domain, path in out_paths.items()}
    try:
        for src in SOURCES:
            if not src.root.exists():
                print(f"  [skip] {src.name}: root {src.root} not found", file=sys.stderr)
                continue
            files = [
                p
                for p in sorted(src.root.rglob(src.pattern.removeprefix("**/")))
                if not any(sub in p.relative_to(src.root).as_posix() for sub in src.exclude_substrings)
                and p.relative_to(src.root).as_posix() not in src.exclude_files
            ]
            src_chunks = 0
            for path in files:
                for chunk in chunk_doc_file(path, src, variables):
                    handles[src.domain].write(json.dumps(chunk, ensure_ascii=False) + "\n")
                    src_chunks += 1
            counts[src.name] = src_chunks
            print(f"{src.name}: {len(files)} files -> {src_chunks} chunks ({src.domain})")
    finally:
        for h in handles.values():
            h.close()

    print(f"\nTotal chunks: {sum(counts.values())}")
    for domain, path in out_paths.items():
        print(f"-> {path}")


if __name__ == "__main__":
    main()
