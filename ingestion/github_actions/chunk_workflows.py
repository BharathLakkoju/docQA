"""Phase 1c — AST/structure-aware chunking of GitHub Actions workflow YAML.

Chunk boundary = one job (its full step list kept together as a coherent,
parseable unit), never a mid-step cut. Jobs whose YAML exceeds a size
budget are split into step-group sub-chunks that each repeat the job header
(name/runs-on/needs) for context, mirroring the cAST "split large nodes,
merge small siblings" approach cited in reference-doc.md.

Input:  data/raw/github_actions/live/*.yml   (from fetch_workflows.py)
Output: data/processed/github_actions/structured_chunks.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from io import StringIO
from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.scanner import ScannerError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402

MAX_CHUNK_CHARS = 4000
YAML_RT = YAML()
YAML_RT.preserve_quotes = True


def dump_yaml(obj) -> str:
    buf = StringIO()
    YAML_RT.dump(obj, buf)
    return buf.getvalue()


def normalize_triggers(on_value) -> list[str]:
    if on_value is None:
        return []
    if isinstance(on_value, str):
        return [on_value]
    if isinstance(on_value, list):
        return [str(v) for v in on_value]
    if hasattr(on_value, "keys"):  # dict-like (CommentedMap)
        return [str(k) for k in on_value.keys()]
    return [str(on_value)]


def actions_used(steps: list) -> list[str]:
    uses = []
    for step in steps or []:
        if isinstance(step, dict) and step.get("uses"):
            uses.append(str(step["uses"]))
    return sorted(set(uses))


def build_job_chunks(
    job_name: str, job_def: dict, workflow_name: str, triggers: list[str],
    source: str, source_url: str, license_: str, file_key: str,
) -> list[dict]:
    steps = job_def.get("steps") or []
    runs_on = job_def.get("runs-on", "")
    needs = job_def.get("needs", [])
    if isinstance(needs, str):
        needs = [needs]
    uses = actions_used(steps)

    header = {"name": job_def.get("name", job_name), "runs-on": runs_on}
    if needs:
        header["needs"] = needs

    full_job_yaml = dump_yaml({job_name: job_def})
    metadata_base = {
        "domain": "github_actions",
        "artifact_type": "workflow_job",
        "workflow_name": workflow_name,
        "triggers": triggers,
        "job_name": job_name,
        "runs_on": str(runs_on),
        "actions_used": uses,
        "source": source,
        "source_url": source_url,
        "license": license_,
    }

    if len(full_job_yaml) <= MAX_CHUNK_CHARS or not steps:
        text = f"Workflow: {workflow_name}\nTriggers: {', '.join(triggers)}\n\n{full_job_yaml}"
        return [
            {
                "id": stable_chunk_id("gha-job", file_key, job_name),
                "text": text[:MAX_CHUNK_CHARS + 500],
                "metadata": {**metadata_base, "step_range": None},
            }
        ]

    # Large job: split into step groups, each carrying the job header for context.
    chunks = []
    group: list = []
    group_start = 0
    group_chars = 0
    header_yaml = dump_yaml({job_name: header})

    def flush(end_idx: int):
        if not group:
            return
        job_slice = dict(header)
        job_slice["steps"] = list(group)
        text = (
            f"Workflow: {workflow_name}\nTriggers: {', '.join(triggers)}\n"
            f"(job '{job_name}', steps {group_start + 1}-{end_idx})\n\n"
            f"{dump_yaml({job_name: job_slice})}"
        )
        chunks.append(
            {
                "id": stable_chunk_id("gha-job", file_key, job_name, str(group_start)),
                "text": text[:MAX_CHUNK_CHARS + 500],
                "metadata": {**metadata_base, "step_range": [group_start, end_idx]},
            }
        )

    for i, step in enumerate(steps):
        step_chars = len(dump_yaml(step))
        if group and group_chars + step_chars > MAX_CHUNK_CHARS - len(header_yaml):
            flush(i)
            group, group_chars, group_start = [], 0, i
        group.append(step)
        group_chars += step_chars
    flush(len(steps))

    return chunks


def chunk_file(path: Path, attr_lookup: dict) -> list[dict]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        try:
            data = YAML_RT.load(f)
        except ScannerError as e:
            raise ValueError(f"invalid YAML: {e}") from e
    if not isinstance(data, dict) or "jobs" not in data:
        return []

    sha = path.stem
    attr = attr_lookup.get(sha, {})
    source_url = attr.get("html_url", f"local:{path.name}")
    license_ = attr.get("license", "unknown")
    workflow_name = data.get("name") or path.name
    triggers = normalize_triggers(data.get("on") or data.get(True))  # ruamel may parse bare `on:` as bool True key

    chunks = []
    jobs = data.get("jobs") or {}
    for job_name, job_def in jobs.items():
        if not isinstance(job_def, dict):
            continue
        chunks += build_job_chunks(
            str(job_name), job_def, workflow_name, triggers, "github_search_code_live", source_url, license_, sha
        )
    return chunks


def load_attributions(csv_path: Path) -> dict:
    lookup = {}
    if not csv_path.exists():
        return lookup
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lookup[row["sha"]] = row
    return lookup


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-dir", default="data/raw/github_actions/live")
    parser.add_argument("--attributions-csv", default="data/processed/github_actions/workflow_attributions.csv")
    parser.add_argument("--out-file", default="data/processed/github_actions/structured_chunks.jsonl")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    attr_lookup = load_attributions(Path(args.attributions_csv))

    files = sorted(in_dir.glob("*.yml")) + sorted(in_dir.glob("*.yaml"))
    total_chunks = 0
    total_files = 0
    with out_file.open("w", encoding="utf-8") as out:
        for path in files:
            try:
                chunks = chunk_file(path, attr_lookup)
            except (ValueError, Exception) as e:  # malformed/unparseable YAML — real-world data, skip and report
                print(f"  [skip] {path.name}: {e}", file=sys.stderr)
                continue
            if not chunks:
                continue
            total_files += 1
            for chunk in chunks:
                out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                total_chunks += 1

    print(f"Chunked {total_files}/{len(files)} workflow files into {total_chunks} job chunks")
    print(f"-> {out_file}")


if __name__ == "__main__":
    main()
