# WorkflowGPT / CI-CD Copilot

An agentic RAG system that answers questions about n8n workflows, GitHub Actions CI/CD configs, and
API/HTTP error debugging — and goes a step further than a Q&A chatbot by **generating and mechanically
validating** corrected YAML/JSON config fixes.

**Live demo:** https://documentorqa.vercel.app · **API:** https://workflowgpt-backend.onrender.com/health

> I built an agentic RAG copilot over n8n workflows, GitHub Actions configs, and API error patterns
> that not only answers questions but generates and validates corrected YAML/JSON fixes, with an
> independent RAGAS/DeepEval evaluation layer scoring retrieval and generation separately.

---

## What makes this different from a generic PDF chatbot

1. **Hybrid retrieval, two indexes, not one.** Structured artifacts (n8n workflow JSON, GitHub Actions
   YAML) are chunked per node/job — never a fixed-token window mid-block — and live in a separate
   Pinecone index from semantically-chunked prose (docs, forum threads, Stack Exchange Q&A). Collapsing
   these into one collection is the single easiest way to flatten this into a generic chatbot, so the
   split is enforced throughout the pipeline (`retrieval/structured_retriever.py` vs.
   `retrieval/prose_retriever.py`).
2. **An agentic fix loop, not just prose answers.** For fix-generation requests, the Fix Agent runs
   generate → validate → reflect, capped at 3 attempts. Validation is a **real** subprocess/library
   call — `actionlint` for GitHub Actions YAML, a self-derived structural schema for n8n JSON (n8n has
   no official published schema) — never the LLM asserting its own output is correct. A snippet that
   fails validation after 3 attempts comes back labeled `validated: false`, not silently presented as a
   confirmed fix.
3. **An independently-scored eval layer**, not a vibe check. Retrieval (context precision/recall) and
   generation (faithfulness/answer relevancy) are scored separately via RAGAS/DeepEval against a
   61-question stratified set, run against the actual live pipeline — see numbers below, including the
   mediocre ones.

## Real eval numbers

61-question stratified set (n8n / GitHub Actions / API-errors × factual-lookup / error-diagnosis /
fix-generation), run against the live deployed pipeline via free-tier LLM-as-judge scoring
(`eval/run_eval.py` → [`eval/results/aggregate.json`](eval/results/aggregate.json), also browsable live
at [`/eval`](https://documentorqa.vercel.app/eval)). These are the actual, unmassaged numbers from the
last full run.

| QA metric (n=48)       | Score | | Fix generation (n=13) | Score |
|---|---|---|---|---|
| Context precision       | 0.554 | | Parse pass rate         | 0.923 (12/13) |
| Context recall          | 0.519 | | Avg. attempts to validate | 1.39 (cap: 3) |
| Faithfulness             | 0.924 | | Errored questions        | 0 / 61 |
| Answer relevancy         | 0.854 | | | |
| Decline rate              | 0%    | | | |

**By domain** — n8n's context precision (0.208) is notably lower than GitHub Actions (0.516) and
API-errors (0.842). Plausible explanation: the free-model judge finds it harder to assess relevance of
dense structured-JSON node-parameter chunks than clean YAML or prose. Stated here rather than hidden.

**A real, disclosed limitation of zero-cost LLM-as-judge scoring**: `context_precision`/`context_recall`
came back `null` for 8/48 and 15/48 QA questions respectively — the free-tier judge model occasionally
produced malformed JSON on complex multi-chunk verdicts. Mitigated (capped judge context to 5 chunks /
600 chars each) but not eliminated. The live dashboard surfaces this explicitly rather than papering
over it with an average that ignores the nulls.

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
      │      Prose Retriever      │◀── docs, forum,        │   Structured Retriever    │◀── n8n node /
      │  (Pinecone: workflowgpt-  │    Stack Exchange Q&A  │ (Pinecone: workflowgpt-   │    GHA job chunks
      │        prose)             │                        │       configs)            │
      └────────────┬──────────────┘                        └────────────┬──────────────┘
                    │  + structured chunks if relevant                   │  + prose chunks for context
                    ▼                                                   ▼
         ┌──────────────────────┐                         ┌───────────────────────────────┐
         │   Answer Generator     │                         │          Fix Agent              │
         │  grounded answer +     │                         │  generate → validate → reflect,  │
         │  citations, or an       │                         │  capped at 3 attempts.            │
         │  explicit decline if     │                         │  actionlint / n8n schema — a     │
         │  nothing scores above   │                         │  real parse/lint call, never an   │
         │  the relevance          │                         │  LLM self-report.                 │
         │  threshold              │                         │  validated: true, or best-effort  │
         │                         │                         │  labeled unverified                │
         └──────────────────────────┘                         └───────────────────────────────┘
```

The **Eval Agent** (`eval/run_eval.py`) runs offline against this same live pipeline — not a separate
reimplementation — and feeds the numbers above into the dashboard.

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Vector DB | Pinecone (2 indexes: configs, prose) | Free-tier, managed, production-shaped |
| Embeddings | `fastembed` / `BAAI/bge-small-en-v1.5` (ONNX, local) | Zero cost, no GPU, runs inside the backend at query time |
| LLM (answers, fixes, judge) | OpenRouter, `:free`-suffixed models only | Zero cost, never OpenAI |
| Backend | FastAPI (Python) | Thin wrapper over the agent pipeline |
| Frontend | Next.js 15 (App Router, TypeScript, Tailwind) | Chat UI + eval dashboard |
| Validation | `actionlint` (Go binary) + a self-derived n8n structural schema | Real parse/lint, not LLM self-assertion |
| Eval | RAGAS / DeepEval | Independent retrieval vs. generation scoring |
| Hosting | Render (backend, Docker) + Vercel (frontend) | Both free tiers |

Every LLM call — Answer Generator, Fix Agent, and RAGAS/DeepEval's judge — goes through OpenRouter's
free models. No OpenAI calls anywhere, no paid API usage; this project runs at zero marginal cost.

## Repo layout

```
ingestion/    fetch + chunk scripts for all five corpora (n8n templates/docs/forum,
              GitHub Actions workflows/failure runs, Stack Exchange/MDN/IANA)
retrieval/    Pinecone clients, embeddings, Query Router, structured + prose retrievers
agents/       Answer Generator, Fix Agent (generate/validate/reflect loop), validators/
eval/         question set, RAGAS/DeepEval wiring, run_eval.py, results/
backend/      FastAPI app (thin wrapper over agents/pipeline.py + eval results)
frontend/     Next.js chat UI + eval dashboard
ATTRIBUTIONS.md   per-source licensing log for every CC-BY-SA / attributed corpus item
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

**5. Re-run the eval set** against your own pipeline (resumable — writes incrementally):
```bash
python eval/run_eval.py
```

`actionlint` (the GitHub Actions YAML validator) is a Go binary, not a Python package — install it per
https://github.com/rhysd/actionlint or let `backend/Dockerfile` install it automatically in the
container.

**Tests**: `pytest retrieval/test_query_router.py agents/test_fix_agent.py` — Query Router regression
tests (including the two real routing bugs found and fixed during Phase 2 manual verification) and Fix
Agent generate/validate/reflect loop tests.

## Deployment

Backend on Render (Docker), frontend on Vercel — both free tiers, both live at the URLs above. Full
walkthrough plus every real issue hit along the way (blank env vars, Vercel alias confusion, Deployment
Protection silently blocking the public site, Render cold starts) is in
[`DEPLOYMENT.md`](DEPLOYMENT.md).

## Licensing and attribution

This project ingests content under several licenses — n8n's docs/forum under the Sustainable Use
License (fair-code, **not** OSI open source), Stack Exchange content under CC BY-SA 4.0, MDN under
CC-BY-SA 2.5, community mirror repos under MIT. **This is not, and is not presented as, a commercial
product** — it's an open, attributed portfolio/research project. Every attributed source, author, and
license is logged per-item in [`ATTRIBUTIONS.md`](ATTRIBUTIONS.md) and the per-source CSVs it links to.
The Stack Overflow data dump (which carries an anti-LLM-training clause) was deliberately avoided in
favor of the live Stack Exchange API with proper attribution.

## Known limitations

- **n8n retrieval precision is the weakest spot** (0.208 context precision vs. 0.516–0.842 elsewhere) —
  see "Real eval numbers" above for the likely cause.
- **Free-tier LLM-as-judge scoring is not fully reliable** — a meaningful minority of individual
  question scores came back `null` rather than a wrong number, which is itself informative but should
  not be read as "these questions scored 0."
- **Render's free-tier backend spins down after ~15 minutes idle.** The first request after a period of
  inactivity may take 30-60s to wake the container and can occasionally show a client-side "Failed to
  fetch" before it's fully warm — retrying a few seconds later succeeds. This is a hosting-tier
  trade-off for running at zero cost, not an application bug.
- **The n8n structural schema is self-derived**, not an official n8n-published schema (n8n doesn't
  publish one) — see `agents/validators/n8n_schema.py` for what it actually checks.
