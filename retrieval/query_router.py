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

Domain = Literal["n8n", "github_actions", "api_errors", "agentic_ai"]
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
# agentic_ai: framework names are domain-unique (weight 3); "agent"/"tool use"/
# "orchestrat*" are shared vocabulary an n8n or API question could also use in
# passing, so weight 1 like the other domains' WEAK markers. Checked against
# every existing STRONG/WEAK/API regex above for shared tokens — none found;
# the only near-miss is API_MARKERS' bare "api" co-firing on phrasing like
# "OpenAI Agents SDK API," but AGENTIC_STRONG's weight-3 hit dominates that.
AGENTIC_STRONG = re.compile(
    r"\bmcp\b|\bmodel context protocol\b|\blanggraph\b|\bautogen\b|\bcrewai\b"
    r"|\bopenai agents sdk\b|\bclaude cookbooks?\b|\bcopilot\b|\bagentic workflows?\b"
    # Phase 9 (2026-08-12): OpenAI Codex, HuggingFace, LangChain — checked
    # against every existing marker above, no shared tokens.
    r"|\bcodex\b|\bhugging ?face\b|\btransformers\b|\blangchain\b",
    re.I,
)
# Regression: "GitHub Agentic Workflows" (a real ingested topic, github/docs'
# content/copilot/concepts/agents/) matched nothing at all before "agentic
# workflows?" and bare "agentic" were added — "Agentic" has no word boundary
# before "agent" (so AGENTIC_WEAK's old \bagent\b missed it) and "Workflows"
# (plural) doesn't match n8n's singular \bworkflow\b either, so the query
# fell through to every domain scoring zero and defaulted to api_errors.
# Found while manually verifying retrieval on real sample queries.
AGENTIC_WEAK = re.compile(
    r"\bagent\b|\bagentic\b|\bmulti-agent\b|\borchestrat\w*\b|\btool use\b|\btool call(ing)?\b", re.I
)

FIX_MARKERS = re.compile(
    r"\bfix\b|\bcorrect(ed)?\b|\bgenerate a (yaml|json|workflow|config)\b|\bwhat should (this|the) (yaml|json) (be|look like)\b"
    r"|\bsuggest a fix\b|\bhow do i fix\b"
    # "Write a job/workflow that..." is the natural phrasing for a config-generation
    # request — found via Phase 4 full eval run: all 13 curated fix_generation
    # questions use this phrasing and were being misrouted to factual_lookup.
    r"|\bwrite (a|an|the) [\w\s\-']{0,80}\b(job|workflow|yaml|json|config)\b"
    # agentic_ai's fix-generation kind is often Python code, not YAML/JSON, so
    # its natural phrasing is "write a function/agent/node..." rather than
    # "write a job/workflow/config..." — found via manual retrieval
    # verification, same bug class as the job/workflow phrasing fix above.
    r"|\bwrite (a|an|the) [\w\s\-']{0,80}\b(function|class|agent|node|script)\b",
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
    agentic_score = 3 * len(AGENTIC_STRONG.findall(query)) + len(AGENTIC_WEAK.findall(query))

    scores = {"n8n": n8n_score, "github_actions": gha_score, "api_errors": api_score, "agentic_ai": agentic_score}
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
    # agentic_ai supports fix_generation (CrewAI YAML / Python agent code) but, like api_errors,
    # has no error_diagnosis corpus (no failure-log equivalent exists for these frameworks) — an
    # honest scope gap, not an oversight.
    needs_fix_generation = task_type == "fix_generation" and domain in ("n8n", "github_actions", "agentic_ai")
    return RouterResult(domain=domain, task_type=task_type, needs_fix_generation=needs_fix_generation)
