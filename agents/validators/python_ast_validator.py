"""Python syntax validation for the Fix Agent's agentic_ai fix-generation
path (LangGraph nodes, CrewAI/AutoGen/OpenAI-Agents-SDK-style agent code).

Real validation via `ast.parse()` — cheap, no subprocess, no network — but
still a genuine parse call, not the LLM self-reporting correctness, per the
same rule actionlint_validator.py and n8n_schema.py follow. This checks
syntactic validity only (it cannot know whether e.g. `Agent(...)` is called
with arguments a real agent framework accepts) — the same "structural, not
semantic" scope n8n_schema.py is explicit about.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


def validate_python(code: str) -> ValidationResult:
    try:
        ast.parse(code)
    except SyntaxError as e:
        location = f"line {e.lineno}, col {e.offset}" if e.lineno is not None else "unknown location"
        return ValidationResult(valid=False, errors=[f"{location}: {e.msg}"])
    return ValidationResult(valid=True, errors=[])
