"""AGENTS.md Fix Agent — generate -> validate -> reflect loop, capped.

Never returns a snippet without attempting validation at least once (a
"fix" that hasn't been mechanically checked is a guess, not a fix — it
must come back labeled validated=False if it never passes). Validation is
a real subprocess/library call (actionlint / the n8n structural schema),
never the LLM self-reporting correctness.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agents.llm_client import chat  # noqa: E402
from agents.validators.actionlint_validator import validate_yaml as validate_gha_yaml  # noqa: E402
from agents.validators.n8n_schema import validate_workflow as validate_n8n_json  # noqa: E402
from retrieval.result_types import RetrievedChunk  # noqa: E402

MAX_ATTEMPTS = 3
Domain = Literal["n8n", "github_actions"]

FENCE_RE = re.compile(r"```(?:yaml|yml|json)?\s*\n(.*?)```", re.DOTALL)

SYSTEM_PROMPT_TEMPLATE = (
    "You are the Fix Agent for WorkflowGPT, a copilot that generates corrected {kind} "
    "for {domain_desc}. Given the user's request and grounding context below, output ONLY the "
    "corrected {kind} in a single fenced code block. No prose before or after the code block."
)


@dataclass
class FixResult:
    fix_snippet: str
    validated: bool
    attempts: int
    validator_errors: list[str] = field(default_factory=list)


def _extract_snippet(llm_output: str) -> str:
    m = FENCE_RE.search(llm_output)
    return m.group(1).strip() if m else llm_output.strip()


def _validate(domain: Domain, snippet: str) -> tuple[bool, list[str]]:
    if domain == "github_actions":
        result = validate_gha_yaml(snippet)
        return result.valid, result.errors

    # n8n: must first be parseable JSON before the structural schema can even run.
    try:
        obj = json.loads(snippet)
    except json.JSONDecodeError as e:
        return False, [f"not valid JSON: {e}"]
    result = validate_n8n_json(obj)
    return result.valid, result.errors


def _build_context_block(structured: list[RetrievedChunk], prose: list[RetrievedChunk]) -> str:
    parts = []
    for c in structured[:5]:
        parts.append(f"[structured context] {c.text}")
    for c in prose[:3]:
        parts.append(f"[related discussion] {c.text[:800]}")
    return "\n\n".join(parts)


def generate_fix(
    query: str,
    domain: Domain,
    structured_context: list[RetrievedChunk],
    prose_context: list[RetrievedChunk],
) -> FixResult:
    kind = "GitHub Actions workflow YAML" if domain == "github_actions" else "n8n workflow JSON"
    domain_desc = "GitHub Actions CI/CD" if domain == "github_actions" else "n8n workflows"
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(kind=kind, domain_desc=domain_desc)
    context_block = _build_context_block(structured_context, prose_context)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Grounding context:\n{context_block}\n\nRequest: {query}"},
    ]

    last_snippet = ""
    last_errors: list[str] = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        llm_output = chat(messages, max_tokens=1200, temperature=0.1)
        snippet = _extract_snippet(llm_output)
        last_snippet = snippet

        is_valid, errors = _validate(domain, snippet)
        last_errors = errors

        if is_valid:
            return FixResult(fix_snippet=snippet, validated=True, attempts=attempt, validator_errors=[])

        if attempt < MAX_ATTEMPTS:
            messages.append({"role": "assistant", "content": llm_output})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "That did not pass validation. Validator errors:\n"
                        + "\n".join(f"- {e}" for e in errors)
                        + "\n\nFix these specific issues and output the corrected snippet again, "
                        "in the same fenced-code-block format, no prose."
                    ),
                }
            )

    return FixResult(fix_snippet=last_snippet, validated=False, attempts=MAX_ATTEMPTS, validator_errors=last_errors)
