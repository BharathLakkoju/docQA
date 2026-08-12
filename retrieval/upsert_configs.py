"""Phase 2 — embed + upsert the structured ("configs") corpus into Pinecone.

Per INSTRUCTIONS.md Phase 2 step 1: n8n structured (1a) + GitHub Actions
structured (1c). The GitHub Actions failure corpus (1d) is included here
too — INSTRUCTIONS.md's Phase 2 doesn't explicitly assign it to either
collection, and it's structured execution telemetry (actions/steps/exit
context), not human-written prose, so it belongs with configs. This
judgment call is documented in ATTRIBUTIONS.md.

The agentic_ai domain (added later, see CLAUDE.md) contributes three
structured artifact types here too: CrewAI YAML agent/task configs,
Python agent-code examples (chunked per function/class or notebook cell),
and MCP JSON schema definitions/examples.

Run after all of ingestion/n8n/{fetch_templates,chunk_workflows,
chunk_mirror_templates}.py, ingestion/github_actions/{fetch_workflows,
chunk_workflows,fetch_failure_runs,chunk_failure_runs}.py, and
ingestion/agentic_ai/{chunk_agent_configs,chunk_agent_code,chunk_mcp_schema}.py.

Run as: python -m retrieval.upsert_configs
"""
from __future__ import annotations

from pathlib import Path

from .pinecone_client import get_configs_index
from .upsert_common import upsert_collection

FILES = [
    Path("data/processed/n8n/structured_chunks.jsonl"),
    Path("data/processed/github_actions/structured_chunks.jsonl"),
    Path("data/processed/github_actions/failure_chunks.jsonl"),
    Path("data/processed/agentic_ai/agent_config_chunks.jsonl"),
    Path("data/processed/agentic_ai/agent_code_chunks.jsonl"),
    Path("data/processed/agentic_ai/mcp_schema_chunks.jsonl"),
]


def main() -> None:
    index = get_configs_index()
    total = upsert_collection(index, FILES, "configs")
    print(f"\nUpserted {total} vectors into the configs index.")
    stats = index.describe_index_stats()
    print(f"Index stats: {stats}")


if __name__ == "__main__":
    main()
