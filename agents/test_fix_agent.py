"""Pure-logic / real-validator tests for the Fix Agent — no LLM calls, no
network. Run: python -m pytest agents/test_fix_agent.py -v
"""
import json

from agents.fix_agent import _extract_snippet, _validate


def test_extract_snippet_from_fenced_yaml():
    llm_output = "Here you go:\n\n```yaml\nname: CI\non: push\n```\n\nLet me know if that helps!"
    assert _extract_snippet(llm_output) == "name: CI\non: push"


def test_extract_snippet_from_fenced_json():
    llm_output = '```json\n{"a": 1}\n```'
    assert _extract_snippet(llm_output) == '{"a": 1}'


def test_extract_snippet_falls_back_to_raw_text_when_no_fence():
    llm_output = "name: CI\non: push"
    assert _extract_snippet(llm_output) == "name: CI\non: push"


def test_validate_github_actions_valid_snippet():
    valid_yaml = """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""
    is_valid, errors = _validate("github_actions", valid_yaml)
    assert is_valid is True
    assert errors == []


def test_validate_github_actions_catches_outdated_action():
    stale_yaml = """
name: CI
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v1
"""
    is_valid, errors = _validate("github_actions", stale_yaml)
    assert is_valid is False
    assert any("too old" in e for e in errors)


def test_validate_n8n_valid_workflow():
    workflow = json.dumps(
        {
            "nodes": [
                {"id": "1", "name": "Trigger", "type": "n8n-nodes-base.manualTrigger", "position": [0, 0], "parameters": {}}
            ],
            "connections": {},
        }
    )
    is_valid, errors = _validate("n8n", workflow)
    assert is_valid is True
    assert errors == []


def test_validate_n8n_missing_required_field():
    workflow = json.dumps({"nodes": [{"id": "1"}], "connections": {}})
    is_valid, errors = _validate("n8n", workflow)
    assert is_valid is False
    assert len(errors) > 0


def test_validate_n8n_invalid_json_reports_parse_error_not_crash():
    is_valid, errors = _validate("n8n", "not valid json {{{")
    assert is_valid is False
    assert "not valid JSON" in errors[0]
