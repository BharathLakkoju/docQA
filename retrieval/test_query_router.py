"""Pure-logic tests for the Query Router — no API keys needed, runs now."""
from retrieval.query_router import classify_domain, classify_task_type, route


def test_domain_n8n():
    assert classify_domain("How do I configure a webhook trigger node in n8n?") == "n8n"


def test_domain_github_actions():
    assert classify_domain("Why does my GitHub Actions workflow job fail on push?") == "github_actions"


def test_domain_api_errors():
    assert classify_domain("What does HTTP status code 429 mean?") == "api_errors"


def test_task_type_factual():
    assert classify_task_type("What does the n8n Webhook node do?") == "factual_lookup"


def test_task_type_error_diagnosis():
    assert classify_task_type("My workflow keeps failing with an AxiosError, why?") == "error_diagnosis"


def test_task_type_fix_generation():
    assert classify_task_type("Can you fix this GitHub Actions YAML for me?") == "fix_generation"


def test_needs_fix_generation_only_for_config_domains():
    r = route("Fix this n8n workflow JSON, the HTTP node is misconfigured")
    assert r.domain == "n8n"
    assert r.task_type == "fix_generation"
    assert r.needs_fix_generation is True

    r2 = route("How do I fix a 403 error from the Stripe API?")
    assert r2.needs_fix_generation is False  # api_errors has no structured corpus to ground a fix in


def test_factual_lookup_never_triggers_fix_loop():
    r = route("What triggers does the n8n Schedule Trigger node support?")
    assert r.needs_fix_generation is False


def test_third_person_fails_counts_as_error_marker():
    # Regression: "fail(ed|ing|ure)?" didn't match "fails" (found alongside
    # the domain tie-break bug in the same smoke-test query).
    assert classify_task_type("My GitHub Actions workflow fails on npm test, why?") == "error_diagnosis"


def test_write_a_job_phrasing_triggers_fix_generation():
    # Regression: found via the full Phase 4 eval run — all 13 curated
    # fix_generation questions use "Write a job/workflow that..." phrasing,
    # which FIX_MARKERS didn't recognize, so they were misrouted to
    # factual_lookup and never reached the Fix Agent.
    r = route("Write a GitHub Actions job that checks out the repo and runs npm test")
    assert r.task_type == "fix_generation"
    assert r.needs_fix_generation is True

    r2 = route("Write an n8n workflow JSON with a Manual Trigger connected to a Set node")
    assert r2.task_type == "fix_generation"
    assert r2.needs_fix_generation is True


def test_generic_workflow_term_does_not_beat_explicit_github_actions_mention():
    # Regression: "workflow" alone is an n8n marker, but this query is
    # unambiguously about GitHub Actions. Found via Phase 2 manual retrieval
    # verification (eval/retrieval_smoke_test_output.txt) — this used to
    # misroute to n8n on a 1-1 marker tie broken by dict insertion order.
    assert classify_domain("My GitHub Actions workflow fails on npm test, why?") == "github_actions"


def test_domain_agentic_ai_strong_markers():
    assert classify_domain("How does LangGraph handle multi-agent orchestration?") == "agentic_ai"
    assert classify_domain("What is MCP (Model Context Protocol)?") == "agentic_ai"
    assert classify_domain("How do I define a CrewAI agent's role and goal?") == "agentic_ai"
    assert classify_domain("How does GitHub Copilot's local sandbox work?") == "agentic_ai"


def test_agentic_ai_weak_marker_does_not_beat_other_domains():
    # "agent"/"orchestrat*" alone are shared vocabulary — an n8n query that
    # happens to say "orchestrate" shouldn't get pulled into agentic_ai.
    assert classify_domain("How do I orchestrate multiple n8n workflow triggers?") == "n8n"


def test_agentic_ai_python_code_fix_phrasing():
    # Regression: found via manual retrieval verification — "write a
    # function/agent/node..." (natural phrasing for a Python-code fix
    # request) didn't match FIX_MARKERS, which was tuned for
    # "write a job/workflow/yaml/json/config..." from the n8n/GHA domains.
    r = route("Write a Python function that creates a LangGraph node")
    assert r.task_type == "fix_generation"
    assert r.domain == "agentic_ai"
    assert r.needs_fix_generation is True


def test_agentic_ai_fix_generation():
    r = route("Write a CrewAI agent config with a role, goal, and backstory")
    assert r.domain == "agentic_ai"
    assert r.task_type == "fix_generation"
    assert r.needs_fix_generation is True


def test_domain_agentic_ai_phase9_markers():
    assert classify_domain("How do I fine-tune a model with HuggingFace transformers?") == "agentic_ai"
    assert classify_domain("What is LangChain?") == "agentic_ai"
    assert classify_domain("How do I configure OpenAI Codex's sandbox mode?") == "agentic_ai"


def test_agentic_workflows_phrase_does_not_fall_through_to_api_errors():
    # Regression: found via manual retrieval verification. "Agentic" has no
    # word boundary before "agent" and "Workflows" (plural) doesn't match
    # n8n's singular \bworkflow\b, so this query scored zero everywhere and
    # silently defaulted to api_errors before "agentic workflows?"/"agentic"
    # markers were added.
    assert classify_domain("What are GitHub Agentic Workflows?") == "agentic_ai"


def test_agentic_ai_has_no_error_diagnosis_corpus():
    # Like api_errors, agentic_ai has no failure-log corpus, so even an
    # explicit fix-ish request without config-generation phrasing should
    # not force needs_fix_generation via error markers alone.
    r = route("Why is my LangGraph agent throwing an error?")
    assert r.domain == "agentic_ai"
    assert r.task_type == "error_diagnosis"
    assert r.needs_fix_generation is False
