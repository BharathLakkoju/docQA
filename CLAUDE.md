# CLAUDE.md

This file is read by Claude (via Claude Code) at the start of every session on this repo. It is the persistent memory of the project: what it is, why it exists, what's already been decided, and what must never be re-litigated without explicit sign-off from Bharath.

## Project identity

**Name:** WorkflowGPT / CI-CD Copilot
**One-line description:** A domain-specific, agentic RAG system that answers natural-language questions about n8n workflows, GitHub Actions CI/CD configs, and API/HTTP error debugging — and goes a step further by generating validated, corrected YAML/JSON config fixes, not just prose answers.
**Why this project exists:** This is a resume/portfolio project built to help Bharath move from his current Developer I / AI Software Engineer role into a stronger AI Software Engineer, Full Stack, or SDE-1/SDE-2 role. It is one of two "non-negotiable" project types recruiters look for (production RAG with a real eval layer). It must read as genuine domain authority (Bharath's own n8n/GitHub Actions/API debugging experience), not a generic tutorial.
**Distinctness from Bharath's other projects:** This is not Dvelve (his multi-agent research assistant). Dvelve demonstrates multi-agent orchestration. This project demonstrates retrieval evaluation rigor, hybrid structured/unstructured retrieval, and agentic self-correction on code/config artifacts. Do not blur the two when writing docs, READMEs, or resume bullets.

## Non-negotiable architectural decisions (already made — do not revisit without explicit request)

- **Vector DB: Pinecone.** Chosen for free-tier generosity and resume/hiring-signal value (managed, production-style vector service). Do not switch to ChromaDB/Weaviate unless Bharath explicitly asks.
- **Hybrid retrieval, two collections, not one.** Structured artifacts (n8n workflow JSON, GitHub Actions YAML) go in one collection using AST/structure-aware chunking (per node/job/step, not fixed-token windows). Unstructured prose (docs, forum threads, Stack Overflow Q&A) goes in a separate collection using standard semantic chunking (~600 tokens, ~100 overlap). This split is the core technical differentiator for the case study — do not collapse it into a single naive chunking pipeline to save time.
- **Agentic fix-suggestion loop, not just Q&A.** The system must not only answer questions but propose corrected YAML/JSON config snippets via a LangGraph-style generate → validate → reflect → regenerate loop. Validation means actually parsing/linting the output (`actionlint` for GitHub Actions YAML, n8n's own JSON schema for workflow JSON) before returning it. A "fix" that hasn't been validated is not a fix — it's a guess, and must be labeled as unverified if validation fails after retries.
- **Frontend: Next.js (App Router), deployed on Vercel. Backend: FastAPI, deployed on Render/Railway/Fly.io free tier.** Matches Bharath's existing stack. Do not propose Streamlit.
- **Eval is not optional and is not an afterthought.** RAGAS and/or DeepEval score retrieval (context precision/recall) and generation (faithfulness/answer relevancy) separately. A 50–100 question stratified eval set (across n8n / GitHub Actions / API-errors, and across factual-lookup / error-diagnosis / fix-generation task types) is a hard deliverable, with real, unmassaged numbers reported in the README — including mediocre ones if that's what the pipeline produces.
- **Zero cost, always. Never OpenAI, anywhere.** Explicit standing constraint from Bharath (2026-08-11): this project must be buildable and deployable without spending a penny. Embeddings run locally via `fastembed` (ONNX runtime, no PyTorch, no API key, ~150MB RAM — chosen specifically because it's cheap enough to run inside the free-tier backend at query time, not just at index-build time). All LLM calls (Answer Generator, Fix Agent, and RAGAS/DeepEval's LLM-as-judge scoring) go through OpenRouter using `:free`-suffixed models only — never OpenAI directly, never a paid OpenRouter model. Current default is `google/gemma-4-31b-it:free`; free model availability changes, so re-check `GET https://openrouter.ai/api/v1/models` (filter for `:free`) before assuming a hardcoded model id still exists.

## Data sourcing ground truth

Full source catalogue, licensing notes, and ingestion plan live in `INSTRUCTIONS.md` and the research artifact `WorkflowGPT CI/CD Copilot: Data Sources, Retrieval Architecture, and Licensing Build Reference`. Key locked-in choices:

- n8n structured corpus: `api.n8n.io/templates/search` + `ScraperNode/awesome-n8n-templates` GitHub mirror.
- n8n prose corpus: `n8n-io/n8n-docs` (or the pre-concatenated `techfundoffice/n8n-docs-llms` `llms.txt`) + Discourse `.json` API pulls from `community.n8n.io`.
- GitHub Actions structured corpus: Cardoen/Mens/Decan YAML dataset (Zenodo `10.5281/zenodo.10259013`), topped up with live GitHub Search-Code API pulls if needed.
- GitHub Actions failure corpus: GHALogs (Zenodo `10.5281/zenodo.10154920`) — `runs.json.gz` metadata plus a sampled subset of raw logs, not the full 142GB log archive.
- API/HTTP error prose corpus: Stack Exchange API (not the gated data dump, to sidestep the anti-LLM-training clause) for `github-actions`/`api`/`http-status-codes` tags, plus MDN HTTP status docs and the IANA status code registry.

**Licensing constraints that affect code, not just docs:**
- Do not bulk-download or redistribute the Stack Overflow data dump; use the live Stack Exchange API and attribute per Stack Exchange's terms (link back to source, credit authors).
- Do not present this project as a commercial product — n8n's docs/forum are under the Sustainable Use License (fair-code, not OSI open source).
- Prefer pre-collected, explicitly-licensed datasets (Zenodo, HuggingFace) over bulk-scraping raw GitHub repo files for anything that gets redistributed in the corpus; live API pulls are fine for retrieval-at-inference.
- Maintain an `ATTRIBUTIONS.md` tracking source + author + license for any CC-BY-SA content ingested.

## Working style / how Bharath wants Claude to operate on this repo

- He expects full rewrites over patches when iterating on docs or prompts; don't leave stale sections next to new ones.
- Don't ask clarifying questions for things you can reasonably decide yourself — state the assumption and proceed. Do ask when a decision would change licensing exposure, cost, or the core architecture above.
- No fabricated data, numbers, or eval results, ever. If a corpus source is thin or an eval score is bad, say so plainly.
- No placeholders in anything meant to be shipped (README, resume bullets, case study) — every claim must be backed by something actually built and run.
- Building order matters: ingestion → retrieval → agentic fix loop → eval pipeline with real numbers → frontend polish → deployment. Do not let frontend work get ahead of eval work.

## Current status

Update this section as the project progresses. As of the last update:

**Phase 0 (setup) and Phase 1 (ingestion) complete.** Repo scaffolded per INSTRUCTIONS.md Phase 0
(`ingestion/`, `retrieval/`, `agents/`, `eval/`, `backend/`, `frontend/`, `.env.example`,
`ATTRIBUTIONS.md`, `requirements.txt`, Python venv). All five Phase 1 corpora pulled from real, live
sources and chunked — 28,448 total chunks:

- n8n structured: 23,067 per-node chunks from 1,017 real templates (296 via `api.n8n.io`, 721 sampled
  from `ScraperNode/awesome-n8n-templates`).
- n8n prose: 2,503 doc chunks (`n8n-io/n8n-docs`) + 400 forum Q&A chunks (`community.n8n.io` Discourse
  API, error/debugging threads).
- GitHub Actions structured: 524 job-level chunks from 297 real live-pulled workflow YAML files (see
  ATTRIBUTIONS.md for why this deviated from the named Zenodo dataset — 1.4GB, not worth downloading for
  a locally-built index; live pulls used for retrieval-at-inference only, gitignored, not redistributed).
- GitHub Actions failures: 1,419 chunks from 505 failing runs, streamed from GHALogs' `runs.json.gz`
  (5MB actually read, not the full 1GB file, and never the 142GB raw log archive).
- API/HTTP errors: 400 Stack Exchange Q&A chunks (`github-actions`/`http-status-codes`/`rest`/`http`
  tags — `api` isn't a real SO tag, substituted per ATTRIBUTIONS.md) + 71 MDN status-page chunks + 64
  IANA registry chunks.

All ingestion/chunking code lives under `ingestion/{n8n,github_actions,api_errors,common}/` and is
re-runnable. Raw and processed data live in `data/raw/` and `data/processed/` (gitignored — regenerate
via the scripts, not committed). `ATTRIBUTIONS.md` has full per-source attribution logs and documents
every deviation from the plan with reasoning.

**Phase 2 (retrieval), Phase 3 (agentic fix loop), and Phase 4 (eval) complete**, all with real,
verified data — no mocked pipeline, no massaged numbers.

- **Phase 2**: Both Pinecone indexes built (`workflowgpt-configs`: 24,913 vectors; `workflowgpt-prose`:
  3,413 vectors), embedded locally via `fastembed`/`BAAI/bge-small-en-v1.5` (384-dim, zero cost, no
  OpenAI). Manual retrieval verification (`eval/retrieval_smoke_test_output.txt`) caught and fixed two
  real bugs: (1) the GitHub Actions failure corpus (1,419 chunks) was crowding out the smaller job corpus
  (524 chunks) for factual "what does X do" queries because its terse action-listing text scored
  marginally higher — fixed via task-type-aware `artifact_types` filtering in
  `retrieval/structured_retriever.py` + `agents/pipeline.py`; (2) the Query Router misclassified domain
  on ties (e.g. "workflow" alone beat an explicit "GitHub Actions" mention via dict-insertion-order
  tie-breaking) and missed "fails"/"write a job..." phrasing — fixed with weighted markers in
  `retrieval/query_router.py`, regression-tested in `retrieval/test_query_router.py`.
- **Phase 3**: Answer Generator (explicit code-path decline below `RELEVANCE_THRESHOLD=0.35`, never an
  LLM self-report) and Fix Agent (generate→validate→reflect, capped at 3 attempts, real `actionlint` +
  a self-derived n8n structural schema — n8n has no official published schema, documented in
  `agents/validators/n8n_schema.py`) both verified end-to-end against live OpenRouter calls.
- **Phase 4**: 61-question stratified eval set (`eval/question_set.jsonl`) run against the actual live
  pipeline (`eval/run_eval.py`, resumable — writes incrementally per question since free-tier judge
  calls are the expensive/flaky part). Found and fixed a real bug mid-run: curated fix-generation
  questions phrased "Write a job that…" weren't matching the router's `FIX_MARKERS` regex and were
  silently routed to the Answer Generator instead of the Fix Agent. **Real results (2026-08-11,
  `eval/results/aggregate.json`)**:
  - QA metrics (n=48): context_precision 0.554, context_recall 0.519, faithfulness 0.924,
    answer_relevancy 0.854, decline_rate 0.0.
  - Fix-generation (n=13): parse_pass_rate 0.923 (12/13 validated; the one failure was a Docker
    build-push YAML after 3 attempts), avg_attempts 1.385.
  - By domain: n8n's context_precision (0.208) is notably lower than GitHub Actions (0.516) and
    api_errors (0.842) — plausibly because DeepEval's free-model judge finds it harder to assess
    relevance of dense structured-JSON node-parameter chunks than clean YAML/prose. Worth stating
    plainly in the README rather than hiding it.
  - `context_recall`/`context_precision` came back `null` on a meaningful minority of individual
    questions (free judge model producing malformed JSON on complex multi-chunk verdicts) — a real,
    disclosed limitation of a zero-cost LLM-as-judge, mitigated but not eliminated by capping judge
    context to 5 chunks / 600 chars each (`eval/run_eval.py`'s `JUDGE_CONTEXT_MAX_CHUNKS`).

**Phase 5 (frontend + eval dashboard) complete**, verified live end-to-end in browser (not just build-checked):

- **Backend**: `backend/app.py`, a thin FastAPI layer over `agents/pipeline.py` and `eval/results/*.json`.
  `POST /query` runs the live agentic pipeline (Query Router → retrievers → Answer Generator or Fix
  Agent) and returns router decision, answer/citations or fix snippet/validation status, and the
  retrieved chunks. `GET /eval/aggregate` and `GET /eval/questions` serve the actual Phase 4
  `eval/results/aggregate.json` / `per_question.jsonl` output verbatim — no recomputation, no
  massaging. `fastapi`/`uvicorn` were in `requirements.txt` since Phase 0 planning but never actually
  `pip install`ed until now.
- **Frontend**: `frontend/`, Next.js 15 (App Router, TypeScript, Tailwind), hand-scaffolded (no
  `create-next-app`) since the directory already existed empty. Two pages: `/` (chat — query box,
  example queries, domain/task-type badges, grounded answers with clickable citations, an honest
  decline path, and a fix-generation view showing the validated/unverified badge, attempt count, the
  actual YAML/JSON snippet, and validator errors when unvalidated) and `/eval` (dashboard — aggregate QA
  + fix-generation metrics, by-domain breakdown with the n8n precision gap called out in-page, an
  explicit callout on the null-judge-score limitation, and a full per-question table). No charting
  library — bars are plain CSS, kept dependency-light per the zero-cost ethos.
  `next` was pinned up to `15.5.23` during scaffolding (initial `15.0.3` had a disclosed critical CVE);
  one remaining high-severity `sharp`/libvips advisory is in Next's optional image-optimizer path,
  which this app doesn't use (no `next/image`), so it was left rather than forcing a Next 16 major bump.
- **Verified live in-browser** (not just `next build`): factual lookup (n8n HTTP Request node, grounded
  answer + 2 real citations), fix-generation (GitHub Actions job request → validated YAML in 1 attempt),
  an out-of-corpus decline (LLM correctly said context didn't cover it — note the code-level
  `RELEVANCE_THRESHOLD` decline banner didn't trigger here because retrieval still returned chunks
  scoring just above 0.35; this is pre-existing Phase 3 behavior, not a Phase 5 bug), and the eval
  dashboard rendering the real aggregate + per-question numbers.

**Phase 6 (deployment) is live and verified end-to-end**, not just build-tested:

- **Backend**: `https://workflowgpt-backend.onrender.com`, deployed via Render's Docker Blueprint
  (`render.yaml` + `backend/Dockerfile`, which installs the `actionlint` Go binary alongside Python
  deps). `/health`, `/query` (both factual-lookup and fix-generation, `actionlint` validating
  successfully inside the container), and `/eval/*` all confirmed working live via curl.
- **Frontend**: `https://documentorqa.vercel.app` (Bharath's own custom Vercel alias — the project's
  Vercel-generated domain is `frontend-bharathlakkojus-projects.vercel.app`, both resolve to the same
  deployment), deployed via `vercel --prod` from the `frontend/` directory with `NEXT_PUBLIC_API_URL`
  pointed at the Render backend. Verified in-browser end-to-end on the real public URL: factual lookup,
  fix-generation (validated, 1 attempt), and the eval dashboard rendering real numbers.
- **Real deployment issues hit and fixed, worth remembering**:
  1. `OPENROUTER_API_KEY` was left blank on the first Render apply → every `/query` 500'd with
     `openai.AuthenticationError: Missing Authentication header` (Pinecone/retrieval worked fine,
     isolated to the LLM call) — fixed by setting the real key in Render's Environment tab.
  2. Vercel's CLI prints a transient per-deploy "Aliased: ..." URL in its output that is **not**
     necessarily the stable production URL — the actual stable one is the project-name-based domain
     (`frontend-<org>.vercel.app`), discoverable via `vercel alias ls`. Don't trust the CLI's inline
     "Aliased" line at face value for CORS/env-var wiring.
  3. Vercel account switch mid-session (`vercel login` in another terminal) meant the old `.vercel/`
     project link pointed at a project under the *previous* account — `vercel link --yes` again after
     an account switch, don't assume the existing link is still valid.
  4. The Vercel project had Deployment Protection (SSO wall) enabled by default, which silently
     302-redirected every visitor (including CORS preflight) to a Vercel login page — this is a
     dashboard-only project setting (Settings → Deployment Protection), no CLI toggle; had to be
     disabled by Bharath directly for the site to be publicly viewable at all.
  5. Render's free-tier web service spins down after ~15 min idle; the very first request after a cold
     start can fail client-side as "Failed to fetch" before the service wakes — a retry a few seconds
     later succeeds. Expected free-tier behavior, not a bug — worth a line in Phase 7's README.
- CORS is locked to `https://documentorqa.vercel.app` via `CORS_ORIGINS` on Render.

**Not started:** Phase 7 (README/case study) — the only remaining phase.

**Git:** seven commits on `master`, one per phase plus a small `.gitignore` fix for Vercel CLI metadata
(0/scaffolding, 1/ingestion, 2/retrieval, 3/agents, 4/eval, 5/backend+frontend, 6/deploy-configs, plus
the gitignore fix). Remote: `https://github.com/BharathLakkoju/docQA.git`, pushed and in sync.
