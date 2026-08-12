# WorkflowGPT / CI-CD Copilot

An agentic RAG system that answers questions about n8n workflows, GitHub Actions CI/CD configs,
API/HTTP error debugging, and AI agent tooling (MCP, LangGraph, AutoGen, CrewAI, OpenAI Agents SDK,
GitHub Copilot, HuggingFace, LangChain) — and goes a step further than a Q&A chatbot by **generating
and mechanically validating** corrected YAML/JSON/Python fixes.

**Live demo:** https://documentorqa.vercel.app · **API:** https://workflowgpt-backend.onrender.com/health

> I built an agentic RAG copilot over n8n workflows, GitHub Actions configs, API error patterns, and AI
> agent tooling docs that not only answers questions but generates and validates corrected YAML/JSON/
> Python fixes, with an independent RAGAS/DeepEval evaluation layer scoring retrieval and generation
> separately.

---

## What makes this different from a generic PDF chatbot

1. **Hybrid retrieval, two indexes, not one.** Structured artifacts (n8n workflow JSON, GitHub Actions
   YAML, CrewAI agent/task configs, Python agent-code examples, MCP JSON schemas) are chunked per
   node/job/agent/function — never a fixed-token window mid-block — and live in a separate Pinecone
   index from semantically-chunked prose (docs, forum threads, Stack Exchange Q&A). Collapsing these
   into one collection is the single easiest way to flatten this into a generic chatbot, so the split
   is enforced throughout the pipeline (`retrieval/structured_retriever.py` vs. `retrieval/prose_retriever.py`).
2. **An agentic fix loop, not just prose answers.** For fix-generation requests, the Fix Agent runs
   generate → validate → reflect, capped at 3 attempts. Validation is a **real** parse/lint call —
   `actionlint` for GitHub Actions YAML, a self-derived structural schema for n8n JSON (n8n has no
   official published schema), `ast.parse()` for AI-agent Python code, a self-derived structural schema
   for CrewAI YAML configs — never the LLM asserting its own output is correct. A snippet that fails
   validation after 3 attempts comes back labeled `validated: false`, not silently presented as a
   confirmed fix.
3. **An independently-scored eval layer**, not a vibe check. Retrieval (context precision/recall) and
   generation (faithfulness/answer relevancy) are scored separately via RAGAS/DeepEval, run against the
   actual live pipeline — see numbers below, including the mediocre ones.

## Real eval numbers

**Current snapshot: 177 of 232 questions scored** (n8n / GitHub Actions / API-errors / AI-agent-tooling ×
factual-lookup / error-diagnosis / fix-generation), run against the live deployed pipeline via
free-tier LLM-as-judge scoring (`eval/run_eval.py` → [`eval/results/aggregate.json`](eval/results/aggregate.json),
also browsable live at [`/eval`](https://documentorqa.vercel.app/eval)). These are the actual,
unmassaged numbers from the last completed run (2026-08-12); the remaining 55 are blocked on OpenRouter's
free-tier daily quota (see below) and will be added once it resets.

| QA metric (n=156)      | Score | | Fix generation (n=21) | Score |
|---|---|---|---|---|
| Context precision       | 0.423 | | Parse pass rate         | 0.952 (20/21) |
| Context recall          | 0.457 | | Avg. attempts to validate | 1.238 (cap: 3) |
| Faithfulness             | 0.966 | | Errored questions        | 55 / 232 (quota, see below) |
| Answer relevancy         | 0.889 | | | |
| Decline rate              | 0%    | | | |

**By domain:**

| Domain | Context precision | Context recall | Faithfulness | Answer relevancy | Parse pass rate |
|---|---|---|---|---|---|
| n8n | 0.313 | 0.462 | 0.910 | 0.837 | 1.0 |
| GitHub Actions | 0.403 | 0.413 | 0.972 | 0.964 | 0.857 |
| API errors | 0.802 | 0.748 | 0.974 | 0.826 | — |
| AI agent tooling | 0.208 | 0.276 | 0.993 | 0.912 | 1.0 |

AI-agent-tooling now has the lowest context precision/recall (0.208 / 0.276) of the four domains — the
opposite of what an earlier, smaller sample suggested. Plausible reason: it's the newest and densest
corpus (14k+ chunks) and many of its factual-lookup questions are terse, single-topic doc-page titles
("What is Fleet mode?", "What is Sampling?") pulled directly from page titles rather than a fuller
natural-language question, which gives the retriever and judge less to work with. n8n's precision, by
contrast, improved substantially (0.208 → 0.313) after a real retrieval bug was found and fixed this
session — see below. Stated here rather than smoothed over.

**Two real bugs found and fixed by actually running the eval and robustness suites, not assumed
correct:**
1. **The decline threshold was miscalibrated and effectively disabled.** The 24-case robustness suite
   (`eval/run_edge_case_tests.py`) caught the Answer Generator confidently answering pure out-of-corpus
   questions ("What's the weather in Paris?", "capital of Australia?") instead of declining. Direct
   measurement showed `bge-small-en-v1.5` cosine scores for genuinely unrelated queries against this
   corpus cluster at 0.46–0.53 (not near zero — an anisotropy property of this embedding family), while
   genuinely relevant queries cluster at 0.78–0.90. The threshold was set to 0.35, comfortably below
   both clusters, so nothing ever declined. Raised to 0.6; all 6 out-of-corpus cases now decline
   correctly, and the full suite is 23/24 (the one remaining failure is a live rate-limit error from
   running two eval jobs concurrently, not a code defect).
2. **The eval runner's resume logic treated errors as permanent.** `eval/run_eval.py` is designed to be
   interruptible and resumable (free-tier judge calls are the slow, flaky part), but it was marking
   *any* prior result — including quota-exhaustion errors — as "done," so a resumed run would skip
   previously-errored questions forever instead of retrying them. Fixed to only treat genuinely-scored
   results as complete; this session's resume run correctly retried 113 previously-errored questions and
   scored 58 of them for real before hitting quota again.

**A live, disclosed limitation, not a one-off**: OpenRouter's free tier enforces an account-wide **daily**
quota that this project has now hit twice across two work sessions — confirmed both times by a direct
post-run probe call also returning 429 across every fallback model, not a per-model or per-minute issue.
Running the eval and the robustness suite concurrently against the same shared pool makes it worse. This
is the real cost of a genuinely zero-dollar LLM judge, stated plainly rather than hidden.

**A separate, ongoing limitation of zero-cost LLM-as-judge scoring**: `context_precision`/`context_recall`
regularly come back `null` on individual questions — the free-tier judge model occasionally produces
malformed JSON on complex multi-chunk verdicts, independent of the rate-limit issue above. Mitigated
(capped judge context to 5 chunks / 600 chars each) but not eliminated. The live dashboard surfaces this
explicitly rather than papering over it with an average that ignores the nulls.

## Architecture

```
                                    ┌────────────────────┐
User query ───────────────────────▶│    Query Router     │  (rules-based: domain + task-type
                                    └─────────┬───────────┘   classification, decides fix vs. answer)
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    │                                                   │
        factual lookup / error diagnosis                     fix-generation request
                    │                                                   │
                    ▼                                                   ▼
      ┌──────────────────────────┐                        ┌──────────────────────────┐
      │      Prose Retriever      │◀── docs, forum,        │   Structured Retriever    │◀── n8n node / GHA
      │  (Pinecone: workflowgpt-  │    Stack Exchange Q&A  │ (Pinecone: workflowgpt-   │    job / CrewAI
      │        prose)             │                        │       configs)            │    config / agent
      └────────────┬──────────────┘                        └────────────┬──────────────┘    code / MCP schema
                    │  + structured chunks if relevant                   │  + prose chunks for context
                    ▼                                                   ▼
         ┌──────────────────────┐                         ┌───────────────────────────────┐
         │   Answer Generator     │                         │          Fix Agent              │
         │  grounded answer +     │                         │  generate → validate → reflect,  │
         │  citations, or an       │                         │  capped at 3 attempts.            │
         │  explicit decline if     │                         │  actionlint / n8n schema /        │
         │  nothing scores above   │                         │  ast.parse() / CrewAI schema —    │
         │  the relevance          │                         │  a real parse/lint call, never    │
         │  threshold              │                         │  an LLM self-report.               │
         │                         │                         │  validated: true, or best-effort  │
         └──────────────────────────┘                         │  labeled unverified                │
                                                                └───────────────────────────────┘
```

Four domains share the same two-collection architecture — `domain` and `artifact_type` are just
metadata filters, so adding AI-agent-tooling as a 4th domain (and giving GitHub Actions its first real
prose corpus) needed no new Pinecone index. The **Eval Agent** (`eval/run_eval.py`) runs offline
against this same live pipeline — not a separate reimplementation — and feeds the numbers above into
the dashboard.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Vector DB | Pinecone (2 indexes: configs, prose) | Free-tier, managed, production-shaped |
| Embeddings | `fastembed` / `BAAI/bge-small-en-v1.5` (ONNX, local) | Zero cost, no GPU, runs inside the backend at query time |
| LLM (answers, fixes, judge) | OpenRouter, `:free`-suffixed models only | Zero cost, never OpenAI |
| Backend | FastAPI (Python) | Thin wrapper over the agent pipeline |
| Frontend | Next.js 15 (App Router, TypeScript, Tailwind) | Chat UI + eval dashboard |
| Validation | `actionlint` (Go binary), `ast.parse()`, self-derived n8n + CrewAI structural schemas | Real parse/lint, not LLM self-assertion |
| Eval | RAGAS / DeepEval | Independent retrieval vs. generation scoring |
| Hosting | Render (backend, Docker) + Vercel (frontend) | Both free tiers |

Every LLM call — Answer Generator, Fix Agent, and RAGAS/DeepEval's judge — goes through OpenRouter's
free models. No OpenAI calls anywhere, no paid API usage; this project runs at zero marginal cost (and,
as documented above, that free tier has a real daily ceiling that this project's own testing has hit).

## Repo layout

```
ingestion/    fetch + chunk scripts for all corpora:
              n8n (templates/docs/forum), GitHub Actions (workflows/failure runs/docs),
              api_errors (Stack Exchange/MDN/IANA), agentic_ai/ (MCP, CrewAI, OpenAI Agents SDK,
              LangGraph, AutoGen, Claude Cookbooks, GitHub Copilot docs, OpenAI Codex,
              HuggingFace, LangChain)
retrieval/    Pinecone clients, embeddings, Query Router, structured + prose retrievers
agents/       Answer Generator, Fix Agent (generate/validate/reflect loop), validators/
eval/         question set (232 questions), RAGAS/DeepEval wiring, run_eval.py,
              run_edge_case_tests.py (robustness suite), results/
backend/      FastAPI app (thin wrapper over agents/pipeline.py + eval results)
frontend/     Next.js chat UI + eval dashboard
ATTRIBUTIONS.md   per-source licensing log for every corpus item, including why several
                  requested sources (Claude Code, Cursor, Windsurf docs) were excluded
DEPLOYMENT.md     how this was actually deployed, including real issues hit
```

## Running it locally

```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env   # fill in PINECONE_API_KEY, OPENROUTER_API_KEY (both free)
```

**1. Ingest** (each corpus is fetch → chunk, run as scripts from the repo root — not `-m`, some import
sibling modules directly; see `ingestion/<domain>/`):
```bash
python ingestion/n8n/fetch_templates.py && python ingestion/n8n/chunk_workflows.py

git clone --depth 1 https://github.com/ScraperNode/awesome-n8n-templates data/raw/n8n/awesome-n8n-templates
python ingestion/n8n/chunk_mirror_templates.py

git clone --depth 1 https://github.com/n8n-io/n8n-docs data/raw/n8n/n8n-docs
python ingestion/n8n/chunk_docs.py

python ingestion/n8n/fetch_forum_threads.py && python ingestion/n8n/chunk_forum_threads.py
python ingestion/github_actions/fetch_workflows.py && python ingestion/github_actions/chunk_workflows.py
python ingestion/github_actions/fetch_failure_runs.py && python ingestion/github_actions/chunk_failure_runs.py
python ingestion/api_errors/fetch_stackexchange.py && python ingestion/api_errors/chunk_stackexchange.py

git clone --depth 1 --filter=blob:none --sparse https://github.com/mdn/content data/raw/api_errors/mdn-content
git -C data/raw/api_errors/mdn-content sparse-checkout set files/en-us/web/http/reference/status
python ingestion/api_errors/chunk_mdn_status.py

python ingestion/api_errors/fetch_chunk_iana.py

# agentic_ai domain (7 sources, cloned shallow into data/raw/agentic_ai/ — see
# ATTRIBUTIONS.md's Agentic AI corpus section for exact clone commands and per-source scoping,
# e.g. why openai_agents_sdk_docs excludes docs/{ja,ko,zh,ref}/ and transformers excludes model_doc/)
python ingestion/agentic_ai/chunk_docs.py
python ingestion/agentic_ai/chunk_agent_configs.py
python ingestion/agentic_ai/chunk_mcp_schema.py
python ingestion/agentic_ai/chunk_agent_code.py
```
Each script takes `--help` for its options (output directories, limits, etc.) — defaults write into
`data/raw/` and `data/processed/` (gitignored). `ingestion/github_actions/fetch_workflows.py` shells out
to the [`gh`](https://cli.github.com) CLI (`gh api ...`) so your token never touches a log file —
requires `gh auth login` first.

**2. Index** into Pinecone (these run the real upsert immediately — no `--help`/dry-run flag):
```bash
python retrieval/upsert_configs.py   # structured corpus -> workflowgpt-configs
python retrieval/upsert_prose.py     # prose corpus -> workflowgpt-prose
python retrieval/smoke_test_retrievers.py   # sanity-check retrieval before building on top
```

**3. Run the backend**:
```bash
uvicorn backend.app:app --reload --port 8000
```

**4. Run the frontend** (separate terminal):
```bash
cd frontend
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

**5. Re-run the eval set** against your own pipeline (resumable — writes incrementally, skips
already-scored questions on re-run):
```bash
python eval/run_eval.py
python eval/run_edge_case_tests.py   # separate robustness/edge-case suite, plain assertions not LLM-judge scores
```

`actionlint` (the GitHub Actions YAML validator) is a Go binary, not a Python package — install it per
https://github.com/rhysd/actionlint or let `backend/Dockerfile` install it automatically in the
container.

**Tests**: `pytest retrieval/test_query_router.py agents/test_fix_agent.py` — 32 tests covering Query
Router domain/task-type classification (including real routing bugs found and fixed during manual
verification, across all four domains) and the Fix Agent's generate/validate/reflect loop across all
its validated fix kinds (GitHub Actions YAML, n8n JSON, AI-agent Python code, CrewAI YAML).

## Deployment

Backend on Render (Docker), frontend on Vercel — both free tiers, both live at the URLs above. Full
walkthrough plus every real issue hit along the way (blank env vars, Vercel alias confusion, Deployment
Protection silently blocking the public site, Render cold starts) is in
[`DEPLOYMENT.md`](DEPLOYMENT.md).

## Licensing and attribution

This project ingests content under several licenses — n8n's docs/forum under the Sustainable Use
License (fair-code, **not** OSI open source), Stack Exchange content under CC BY-SA 4.0, MDN under
CC-BY-SA 2.5, GitHub Docs under CC-BY-4.0, and the agentic_ai domain's seven sources under
MIT/Apache-2.0/CC-BY-4.0 (full per-source table in ATTRIBUTIONS.md). **This is not, and is not presented
as, a commercial product** — it's an open, attributed portfolio/research project. Every attributed
source, author, and license is logged per-item in [`ATTRIBUTIONS.md`](ATTRIBUTIONS.md) and the
per-source CSVs it links to. The Stack Overflow data dump (which carries an anti-LLM-training clause)
was deliberately avoided in favor of the live Stack Exchange API with proper attribution.

**Sources considered and deliberately excluded**: Claude Code, Cursor, and Windsurf's own
documentation/blog sites all carry explicit anti-scraping ToS/AUP clauses, and none has any open-source
mirror — confirmed by direct inspection, not assumed. Claude and OpenAI content is covered instead via
their own MIT-licensed open-source repos (`anthropics/claude-cookbooks`, `openai/openai-agents-python`,
`openai/codex`) rather than their ToS-blocked doc sites. See ATTRIBUTIONS.md's Agentic AI corpus section
for the full per-source reasoning.

## Known limitations

- **n8n retrieval precision is the weakest spot** (0.208 context precision vs. 0.336–0.842 elsewhere) —
  see "Real eval numbers" above for the likely cause.
- **Free-tier LLM-as-judge scoring is not fully reliable** — a meaningful minority of individual
  question scores came back `null` rather than a wrong number, which is itself informative but should
  not be read as "these questions scored 0."
- **OpenRouter's free tier has a real daily quota, account-wide.** This project's own eval expansion
  work exhausted it mid-session — confirmed across multiple never-before-tried free models, all
  returning the same `free-models-per-day-high-balance` error. `/query` now returns a clean 503 with an
  actionable message when this happens (fixed after being caught live), rather than a bare 500.
- **Render's free-tier backend spins down after ~15 minutes idle.** The first request after a period of
  inactivity may take 30-60s to wake the container and can occasionally show a client-side "Failed to
  fetch" before it's fully warm — retrying a few seconds later succeeds. This is a hosting-tier
  trade-off for running at zero cost, not an application bug.
- **The n8n and CrewAI structural schemas are self-derived**, not officially published ones (neither
  project publishes one) — see `agents/validators/n8n_schema.py` and `agents/validators/crewai_schema.py`
  for what they actually check.
- **OpenAI Codex's docs corpus is thin**: 8 of 15 files are short redirect stubs to
  `developers.openai.com` rather than substantive in-repo content; only `install.md` has real depth.
  Included anyway (still real, on-topic, dereferenceable content) rather than silently dropped, per this
  project's "state thin sources plainly" rule.
