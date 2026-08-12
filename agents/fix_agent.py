"""AGENTS.md Fix Agent — generate -> validate -> reflect loop, capped.

Never returns a snippet without attempting validation at least once (a
"fix" that hasn't been mechanically checked is a guess, not a fix — it
must come back labeled validated=False if it never passes). Validation is
a real subprocess/library call (actionlint / the n8n structural schema /
ast.parse / the CrewAI structural schema), never the LLM self-reporting
correctness.

agentic_ai is the one domain with two validated fix "kinds" instead of
one (Python agent code vs. CrewAI YAML config) — which kind a given
request wants is read off the fence-language tag the LLM itself chose
(```python vs ```yaml), since that's already deterministic and already
parsed by FENCE_RE. If the LLM omits a tag, `_sniff_agentic_kind` falls
back to a cheap content heuristic rather than guessing wrong silently.
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
from agents.validators.crewai_schema import validate_crewai_yaml  # noqa: E402
from agents.validators.n8n_schema import validate_workflow as validate_n8n_json  # noqa: E402
from agents.validators.python_ast_validator import validate_python  # noqa: E402
from retrieval.result_types import RetrievedChunk  # noqa: E402

try:
    from ruamel.yaml import YAML

    _YAML = YAML(typ="safe")
except ImportError:  # pragma: no cover - ruamel is already a hard dependency elsewhere
    _YAML = None

MAX_ATTEMPTS = 3
Domain = Literal["n8n", "github_actions", "agentic_ai"]

FENCE_RE = re.compile(r"```(\w+)?\s*\n(.*?)```", re.DOTALL)


def _sniff_agentic_kind(snippet: str) -> Literal["python", "yaml"]:
    """Fallback only: fires when the LLM's fenced block has no language tag."""
    stripped = snippet.lstrip()
    if stripped.startswith(("import ", "from ", "def ", "class ", "async def ", "@")):
        return "python"
    if _YAML is not None:
        try:
            obj = _YAML.load(snippet)
            if isinstance(obj, dict):
                return "yaml"
        except Exception:
            pass
    return "python"


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


def _extract_snippet(llm_output: str) -> tuple[str, str | None]:
    """Returns (snippet, fence_lang) — fence_lang is None if the LLM omitted a language tag."""
    m = FENCE_RE.search(llm_output)
    if not m:
        return llm_output.strip(), None
    return m.group(2).strip(), (m.group(1).lower() if m.group(1) else None)


def _validate(domain: Domain, snippet: str, fence_lang: str | None = None) -> tuple[bool, list[str]]:
    if domain == "github_actions":
        result = validate_gha_yaml(snippet)
        return result.valid, result.errors

    if domain == "agentic_ai":
        kind = fence_lang if fence_lang in ("python", "py", "yaml", "yml") else _sniff_agentic_kind(snippet)
        if kind in ("python", "py"):
            result = validate_python(snippet)
            return result.valid, result.errors
        if _YAML is None:
            return False, ["ruamel.yaml is unavailable — cannot validate CrewAI config YAML"]
        try:
            obj = _YAML.load(snippet)
        except Exception as e:
            return False, [f"not valid YAML: {e}"]
        if not isinstance(obj, dict):
            return False, ["expected a YAML mapping of agent/task name -> config, got something else"]
        result = validate_crewai_yaml(obj)
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


AGENTIC_YAML_MARKERS = re.compile(r"\bcrewai\b|\byaml\b|\bagents?\.yaml\b|\btasks?\.yaml\b|\bagent config\b", re.I)


def _agentic_kind_from_query(query: str) -> Literal["python", "yaml"]:
    """agentic_ai has two fixable artifact kinds; decide which one the
    request wants up front so the system prompt asks for the right fence
    language (this also becomes the fallback kind if the LLM omits a tag)."""
    return "yaml" if AGENTIC_YAML_MARKERS.search(query) else "python"


def _kind_and_desc(domain: Domain, query: str) -> tuple[str, str, str]:
    """Returns (kind label for the prompt, domain description, fence language to request)."""
    if domain == "github_actions":
        return "GitHub Actions workflow YAML", "GitHub Actions CI/CD", "yaml"
    if domain == "agentic_ai":
        agentic_kind = _agentic_kind_from_query(query)
        if agentic_kind == "yaml":
            return "CrewAI YAML agent/task config", "agentic AI / multi-agent orchestration tooling", "yaml"
        return "Python agent code (LangGraph/AutoGen/OpenAI Agents SDK style)", "agentic AI / multi-agent orchestration tooling", "python"
    return "n8n workflow JSON", "n8n workflows", "json"


def generate_fix(
    query: str,
    domain: Domain,
    structured_context: list[RetrievedChunk],
    prose_context: list[RetrievedChunk],
) -> FixResult:
    kind, domain_desc, fence_lang_hint = _kind_and_desc(domain, query)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(kind=kind, domain_desc=domain_desc) + f" Use the ```{fence_lang_hint} fence tag."
    context_block = _build_context_block(structured_context, prose_context)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Grounding context:\n{context_block}\n\nRequest: {query}"},
    ]

    last_snippet = ""
    last_errors: list[str] = []

    for attempt in range(1, MAX_ATTEMPTS + 1):
        llm_output = chat(messages, max_tokens=1200, temperature=0.1)
        snippet, fence_lang = _extract_snippet(llm_output)
        fence_lang = fence_lang or fence_lang_hint
        last_snippet = snippet

        is_valid, errors = _validate(domain, snippet, fence_lang)
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
