"""Phase 1d — chunk sampled GHALogs failing runs into structured context.

Important data-quality caveat (documented, not hidden): the `error` field
GHALogs attaches to individual `log_insights` steps comes from *their own*
bash-command-extractor parsing tool choking on shell syntax (e.g. literally
`{"error": "Invalid request", "originalError": ""}` on inspection) — it is
not a reliable signal for why the CI job actually failed. Root-cause text
would require the raw log archive (142GB, intentionally not downloaded per
INSTRUCTIONS.md 1d). So this chunker keeps only what's verifiably real in
the metadata: which repo/workflow/event failed, and which actions/shell
steps ran in that job — useful grounding for "what was this failing
workflow doing" without fabricating a root-cause message that isn't there.

Input:  data/raw/github_actions/ghalogs_failures_sample.jsonl
Output: data/processed/github_actions/failure_chunks.jsonl (appended to the
        structured collection — see Phase 2 notes in ATTRIBUTIONS.md for why).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.chunk_ids import stable_chunk_id  # noqa: E402

MAX_STEPS_SHOWN = 15
MAX_CODE_CHARS = 300


def describe_step(step: dict) -> str:
    if step.get("type") == "action":
        repo = step.get("repository", "")
        action = step.get("action", "")
        version = step.get("version", "")
        return f"- uses: {repo}/{action}@{version} ({step.get('duration_sec', '?')}s)"
    code = (step.get("code") or "").strip().replace("\n", " ")
    if len(code) > MAX_CODE_CHARS:
        code = code[:MAX_CODE_CHARS] + "..."
    return f"- run: {code} ({step.get('duration_sec', '?')}s)"


def chunk_run(record: dict) -> list[dict]:
    meta = record.get("metadata") or {}
    repo = record.get("repository_name", "")
    workflow_path = record.get("workflow_path", "")
    run_title = meta.get("display_title", "")
    event = meta.get("event", "")
    conclusion = meta.get("conclusion", "")
    created_at = meta.get("created_at", "")
    html_url = meta.get("html_url", "")

    chunks = []
    for entry in record.get("log_insights") or []:
        job_file = entry.get("file", "")
        steps = entry.get("steps") or []
        if not steps:
            continue
        step_lines = [describe_step(s) for s in steps[:MAX_STEPS_SHOWN]]
        if len(steps) > MAX_STEPS_SHOWN:
            step_lines.append(f"... ({len(steps) - MAX_STEPS_SHOWN} more steps)")

        text = (
            f"Failing GitHub Actions run\n"
            f"Repository: {repo}\n"
            f"Workflow: {workflow_path}\n"
            f"Run: {run_title}\n"
            f"Trigger event: {event}\n"
            f"Conclusion: {conclusion}\n"
            f"Job log: {job_file}\n\n"
            f"Steps executed before/at failure:\n" + "\n".join(step_lines)
        )

        chunks.append(
            {
                "id": stable_chunk_id("gha-failure", record.get("_id", ""), job_file),
                "text": text,
                "metadata": {
                    "domain": "github_actions",
                    "artifact_type": "failed_run",
                    "repository": repo,
                    "workflow_path": workflow_path,
                    "event": event,
                    "conclusion": conclusion,
                    "created_at": created_at,
                    "job_log_file": job_file,
                    "actions_used": sorted(
                        {f"{s.get('repository')}/{s.get('action')}@{s.get('version')}" for s in steps if s.get("type") == "action"}
                    ),
                    "source": "ghalogs_zenodo",
                    "source_url": html_url,
                    "license": "CC-BY-SA-4.0",
                },
            }
        )
    return chunks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in-file", default="data/raw/github_actions/ghalogs_failures_sample.jsonl")
    parser.add_argument("--out-file", default="data/processed/github_actions/failure_chunks.jsonl")
    args = parser.parse_args()

    in_file = Path(args.in_file)
    out_file = Path(args.out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    total_runs = 0
    total_chunks = 0
    with in_file.open(encoding="utf-8") as f, out_file.open("w", encoding="utf-8") as out:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            total_runs += 1
            for chunk in chunk_run(record):
                out.write(json.dumps(chunk, ensure_ascii=False) + "\n")
                total_chunks += 1

    print(f"Chunked {total_runs} failing runs into {total_chunks} job-failure chunks")
    print(f"-> {out_file}")


if __name__ == "__main__":
    main()
