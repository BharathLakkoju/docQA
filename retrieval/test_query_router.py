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
