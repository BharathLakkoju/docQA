"""AGENTS.md Query Router — classifies domain + task_type, decides whether
the Fix Agent should engage. Deliberately a cheap rules-based classifier,
not an LLM call: AGENTS.md says "keep this cheap... its only job is
routing," and every category here is identifiable from surface keywords
without needing a model in the loop.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Domain = Literal["n8n", "github_actions", "api_errors"]
TaskType = Literal["factual_lookup", "error_diagnosis", "fix_generation"]

# Weighted, not just counted: "workflow"/"node"/"trigger" are generic terms
# that show up in both n8n and GitHub Actions vocabulary (a GHA query saying
# "my workflow" would otherwise tie with an n8n marker and lose to it on
# dict-insertion-order tie-breaking — a real bug caught during Phase 2
# manual verification, see eval/retrieval_smoke_test_output.txt). Strong,
# domain-unique markers get weight 3; generic/shared markers get weight 1.
N8N_STRONG = re.compile(r"\bn8n\b", re.I)
N8N_WEAK = re.compile(r"\bworkflow\b|\bnode\b|\btrigger\b|\bwebhook\b", re.I)
GHA_STRONG = re.compile(r"\bgithub actions?\b|\bgha\b|\bactions/checkout\b|\bworkflow_dispatch\b|\bworkflow file\b", re.I)
GHA_WEAK = re.compile(r"\.ya?ml\b|\bjob\b|\bci/cd\b|\bpipeline\b|\bmatrix\b|\brunner\b|\bruns-on\b", re.I)
HTTP_STATUS_RE = re.compile(r"\b[1-5]\d{2}\b")
API_MARKERS = re.compile(r"\bapi\b|\bhttp\b|\brest\b|\bstatus code\b|\baxios\b|\bcurl\b", re.I)

FIX_MARKERS = re.compile(
    r"\bfix\b|\bcorrect(ed)?\b|\bgenerate a (yaml|json|workflow|config)\b|\bwhat should (this|the) (yaml|json) (be|look like)\b"
    r"|\bsuggest a fix\b|\bhow do i fix\b"
    # "Write a job/workflow that..." is the natural phrasing for a config-generation
    # request — found via Phase 4 full eval run: all 13 curated fix_generation
    # questions use this phrasing and were being misrouted to factual_lookup.
    r"|\bwrite (a|an|the) [\w\s\-']{0,80}\b(job|workflow|yaml|json|config)\b",
    re.I,
)
ERROR_MARKERS = re.compile(
    r"\berror\b|\bfail(s|ed|ing|ure)?\b|\bexception\b|\bcrash(es|ed|ing)?\b|\bdebug(ging)?\b|\bwhy (is|does|did)\b|\bnot working\b|\btraceback\b",
    re.I,
)


@dataclass
class RouterResult:
    domain: Domain
    task_type: TaskType
    needs_fix_generation: bool


def classify_domain(query: str) -> Domain:
    n8n_score = 3 * len(N8N_STRONG.findall(query)) + len(N8N_WEAK.findall(query))
    gha_score = 3 * len(GHA_STRONG.findall(query)) + len(GHA_WEAK.findall(query))
    api_score = len(API_MARKERS.findall(query)) + (1 if HTTP_STATUS_RE.search(query) else 0)

    scores = {"n8n": n8n_score, "github_actions": gha_score, "api_errors": api_score}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "api_errors"  # generic questions with no clear domain marker default to the broadest corpus
    return best  # type: ignore[return-value]


def classify_task_type(query: str) -> TaskType:
    if FIX_MARKERS.search(query):
        return "fix_generation"
    if ERROR_MARKERS.search(query):
        return "error_diagnosis"
    return "factual_lookup"


def route(query: str) -> RouterResult:
    domain = classify_domain(query)
    task_type = classify_task_type(query)
    # A factual lookup never triggers the fix loop, even if it mentions "error" in passing —
    # only an explicit fix/correction request should (per AGENTS.md's Query Router notes).
    needs_fix_generation = task_type == "fix_generation" and domain in ("n8n", "github_actions")
    return RouterResult(domain=domain, task_type=task_type, needs_fix_generation=needs_fix_generation)
