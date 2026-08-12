"""CrewAI YAML agent/task config schema validation for the Fix Agent.

Honesty note (same precedent as agents/validators/n8n_schema.py): CrewAI
does not publish a formal JSON Schema for its `agents.yaml`/`tasks.yaml`
config format either — this schema was derived by inspecting the structure
actually present across CrewAI's own canonical template files (see
ingestion/agentic_ai/chunk_agent_configs.py and ATTRIBUTIONS.md): required
keys `role`/`goal`/`backstory` for an agent entry, `description`/
`expected_output` for a task entry. It validates structural well-formedness
(the right keys exist, with string values), not CrewAI's full runtime
behavior (e.g. it can't know whether an `agent:` reference in a task
actually names a defined agent).
"""
from __future__ import annotations

from dataclasses import dataclass

import jsonschema

AGENT_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "additionalProperties": {
        "type": "object",
        "required": ["role", "goal", "backstory"],
        "properties": {
            "role": {"type": "string"},
            "goal": {"type": "string"},
            "backstory": {"type": "string"},
        },
    },
}

TASK_SCHEMA = {
    "type": "object",
    "minProperties": 1,
    "additionalProperties": {
        "type": "object",
        "required": ["description", "expected_output"],
        "properties": {
            "description": {"type": "string"},
            "expected_output": {"type": "string"},
        },
    },
}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str]


def _validate_against(obj: dict, schema: dict) -> ValidationResult:
    validator = jsonschema.Draft7Validator(schema)
    errors = [f"{'.'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in validator.iter_errors(obj)]
    return ValidationResult(valid=not errors, errors=errors)


def validate_crewai_yaml(obj: dict) -> ValidationResult:
    """Try the agent schema first, then the task schema, since a config
    snippet's top-level keys don't self-declare which kind it is — accept
    whichever schema it actually satisfies, and report the agent-schema
    errors if it matches neither (arbitrary but consistent tie-break)."""
    agent_result = _validate_against(obj, AGENT_SCHEMA)
    if agent_result.valid:
        return agent_result
    task_result = _validate_against(obj, TASK_SCHEMA)
    if task_result.valid:
        return task_result
    return agent_result
