"""agentic_ai domain — AST/structure-aware chunking of CrewAI's YAML
agent/task configs. Same philosophy as ingestion/n8n/node_chunking.py and
ingestion/github_actions/chunk_workflows.py: chunk boundary = one
unit-of-behavior (one agent, one task), never a mid-block cut.

Source: crewAIInc/crewAI's own canonical `agents.yaml`/`tasks.yaml`
templates — these are the exact files CrewAI's own `crewai create crew`
CLI command scaffolds into every new project, so despite there being only
six files total (three template pairs), this is authoritative, canonical
content, not thin scraping (see ATTRIBUTIONS.md).

Validated against the required-key expectations the Fix Agent's
`agents/validators/crewai_schema.py` checks: `role`/`goal`/`backstory` for
agents, `description`/`expected_output` for tasks (self-derived from these
same template files, since CrewAI publishes no formal JSON Schema for its
YAML configs either — same honesty-note precedent as n8n_schema.py).

Output: data/processed/agentic_ai/agent_config_chunks.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ruamel.yaml import YAML

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402

YAML_RT = YAML()
YAML_RT.preserve_quotes = True

AGENT_FILES = [
    "lib/cli/src/crewai_cli/templates/crew/config/agents.yaml",
    "lib/cli/src/crewai_cli/templates/flow/crews/content_crew/config/agents.yaml",
    "lib/crewai/tests/config/agents.yaml",
]
TASK_FILES = [
    "lib/cli/src/crewai_cli/templates/crew/config/tasks.yaml",
    "lib/cli/src/crewai_cli/templates/flow/crews/content_crew/config/tasks.yaml",
    "lib/crewai/tests/config/tasks.yaml",
]


def dump_yaml(obj) -> str:
    from io import StringIO

    buf = StringIO()
    YAML_RT.dump(obj, buf)
    return buf.getvalue()


def chunk_config_file(path: Path, repo_root: Path, config_kind: str) -> list[dict]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        data = YAML_RT.load(f)
    if not isinstance(data, dict):
        return []

    rel_path = path.relative_to(repo_root).as_posix()
    url = f"https://github.com/crewAIInc/crewAI/blob/main/{rel_path}"
    chunks = []
    for name, body in data.items():
        if not isinstance(body, dict):
            continue
        text = f"{config_kind} '{name}' (crewAI YAML config, {rel_path}):\n\n{dump_yaml({name: body})}"
        chunks.append(
            {
                "id": stable_chunk_id("crewai-config", rel_path, str(name)),
                "text": text,
                "metadata": {
                    "domain": "agentic_ai",
                    "artifact_type": "agent_config",
                    "config_kind": config_kind,
                    "config_name": str(name),
                    "source_path": rel_path,
                    "source_url": url,
                    "source": "crewai_config_templates",
                    "license": "MIT",
                },
            }
        )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="data/raw/agentic_ai/crewai")
    parser.add_argument("--out-file", default="data/processed/agentic_ai/agent_config_chunks.jsonl")
    args = parser.parse_args()

    repo_root = Path(args.repo_root)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    total_chunks = 0
    total_files = 0
    with out_file.open("w", encoding="utf-8") as out:
        for rel, kind in [(f, "agent") for f in AGENT_FILES] + [(f, "task") for f in TASK_FILES]:
            path = repo_root / rel
            if not path.exists():
                print(f"  [skip] {rel}: not found", file=sys.stderr)
                continue
            chunks = chunk_config_file(path, repo_root, kind)
            total_files += 1
            for chunk in chunks:
                out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                total_chunks += 1

    print(f"Chunked {total_files} CrewAI config files into {total_chunks} agent_config chunks")
    print(f"-> {out_file}")


if __name__ == "__main__":
    main()
