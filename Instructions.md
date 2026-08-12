# INSTRUCTIONS.md

Concrete, sequenced build instructions for WorkflowGPT / CI-CD Copilot. This is the execution plan; CLAUDE.md is project memory/context, AGENTS.md is the runtime agent architecture. Follow the order below — do not jump ahead to frontend or deployment before ingestion, retrieval, and the eval pipeline produce real numbers.

## Phase 0 — Setup

1. Initialize the repo with separate top-level directories: `ingestion/`, `retrieval/`, `agents/`, `eval/`, `backend/` (FastAPI), `frontend/` (Next.js App Router).
2. Create `.env.example` documenting every required environment variable (Pinecone API key/environment, OpenRouter or chosen LLM provider key, GitHub token for API pulls). Never commit real secrets.
3. Create `ATTRIBUTIONS.md` (empty, to be filled during ingestion) to track source/author/license per piece of CC-BY-SA or similarly licensed content ingested.
4. Set up Pinecone: two indexes/namespaces — one for structured configs, one for prose — per the AGENTS.md architecture. Do not use a single collection.

## Phase 1 — Ingestion (Week 1 target: n8n; Week 2 target: GitHub Actions + API errors)

### 1a. n8n structured corpus
- Pull workflow templates via the official API: `https://api.n8n.io/templates/search` (paginate through results), storing the raw workflow JSON per template.
- Supplement by cloning `ScraperNode/awesome-n8n-templates` (MIT licensed, ~8,700+ workflows across 25 categories) for volume and category diversity.
- Parse each workflow JSON into per-node chunks (node type, parameters, connections, credential references as metadata, not raw secrets). This is AST/structure-aware chunking, not fixed-token splitting — a chunk boundary should be a node or a logical group of connected nodes, never a mid-node cut.
- Attach metadata: source template ID, category, node types present, trigger type.

### 1b. n8n prose corpus
- Ingest n8n docs: either clone `n8n-io/n8n-docs` and read the Markdown under `docs/`, or use the pre-concatenated `techfundoffice/n8n-docs-llms` `llms.txt` as a faster start.
- Pull forum content from `community.n8n.io` via its Discourse JSON API (append `.json` to category/topic URLs, e.g. `/c/questions/6.json`, `/t/{topic-id}.json`, `/search.json?q=`). Prioritize threads that look like real error/debugging Q&A (e.g., threads containing stack traces, `AxiosError`, status codes) since this is the highest-value content for the debugging use case.
- Semantic-chunk prose at roughly 600 tokens with 100-token overlap.
- Log every forum thread pulled (URL + author + date) into `ATTRIBUTIONS.md`.

### 1c. GitHub Actions structured corpus
- Download the Cardoen/Mens/Decan workflow YAML dataset (Zenodo `10.5281/zenodo.10259013`) for real, redistributable `.github/workflows/*.yml` files.
- Optionally top up with live pulls via the GitHub REST Search Code API (`GET /search/code?q=...+path:.github/workflows+extension:yml`) — respect the 10 requests/minute limit, authenticate, and use these live pulls for retrieval-at-inference only, not for bulk redistribution in the shipped corpus.
- AST/structure-chunk YAML per job/step (use a YAML parser to a tree, e.g. `ruamel.yaml`, and chunk on job/step boundaries), attaching metadata: workflow trigger (`on:`), job name, actions used.

### 1d. GitHub Actions failure corpus
- Download GHALogs metadata (`runs.json.gz` from Zenodo `10.5281/zenodo.10154920`) — do not download the full 142GB raw log archive; instead pull a sampled subset of raw logs for failing runs specifically, since those are what a debugging copilot needs.
- Pair each sampled failing run's parsed step/error info with its workflow context where possible.

### 1e. API/HTTP error prose corpus
- Pull Q&A via the live Stack Exchange API (`api.stackexchange.com`, `tagged=github-actions` / `api` / `http-status-codes`) — do not use the gated Stack Overflow data dump, since it now carries an anti-LLM-training clause.
- Ingest MDN's HTTP status code reference and the IANA HTTP Status Code Registry as a clean structured reference layer.
- Attribute every Stack Exchange item pulled (author, link back to source question/answer) per Stack Exchange's CC-BY-SA terms, logged in `ATTRIBUTIONS.md`.

## Phase 2 — Retrieval layer

1. Embed and upsert the structured corpus (1a + 1c) into the Pinecone "configs" collection with the metadata fields above as filterable attributes.
2. Embed and upsert the prose corpus (1b + 1e) into the Pinecone "prose" collection.
3. Implement the Query Router (see AGENTS.md) to classify domain + task type and decide which collection(s) to hit.
4. Implement the Structured Retriever and Prose Retriever as separate, independently testable modules — write a small standalone test script that queries each in isolation before wiring them into the full pipeline.
5. Verify retrieval quality manually on ~10 sample queries per domain before moving on — if retrieval is visibly bad here, fix chunking/embedding now, not after the generator is built on top of it.

## Phase 3 — Generation and the agentic fix loop

1. Implement the Answer Generator: takes query + retrieved context, produces a grounded answer with citations back to source chunks. Must explicitly decline to answer ("I don't have enough context...") when retrieval returns nothing relevant above a relevance threshold — build this as an explicit code path, not an implicit hope that the LLM will behave.
2. Implement the Fix Agent's generate step: constrained YAML/JSON generation (schema-constrained decoding or a Pydantic model wrapping the LLM call) grounded in retrieved structured context.
3. Implement the validate step for real: integrate `actionlint` (as a subprocess call against generated GitHub Actions YAML) and n8n's workflow JSON schema (as a library-based schema validation call against generated n8n JSON). This must be an actual parse/lint call, not the LLM asserting its own output is valid.
4. Implement the reflect-and-retry loop: on validation failure, feed the validator's actual error message back into the next generation attempt. Cap at 3 attempts. On final failure, return the best attempt clearly labeled `validated: false`.
5. Wire the Query Router's `needs_fix_generation` flag to decide whether a request goes to the Answer Generator or the Fix Agent.

## Phase 4 — Evaluation pipeline (do this before frontend polish)

1. Build the eval question set: 50–100 questions, stratified across the three domains (n8n / GitHub Actions / API errors) and across three task types (factual lookup, error diagnosis, fix-generation). For fix-generation items, store a gold corrected YAML/JSON snippet alongside the question.
2. Wire in RAGAS and/or DeepEval:
   - Score retrieval independently: context precision and context recall against each retriever.
   - Score generation independently: faithfulness (is the answer grounded in retrieved context) and answer relevancy/correctness against gold answers.
   - For fix-generation items, additionally compute a parse-pass rate (did the final returned snippet pass `actionlint`/schema validation) as a code-specific metric that RAGAS/DeepEval don't natively cover.
3. Run the full eval set against the actual deployed retrieval and generation modules (not a mocked or simplified reimplementation) and store per-question and aggregate results.
4. Report the real numbers. If faithfulness or context recall is mediocre, say so in the README and explain what it reveals (e.g., "context recall was low on API-error questions, suggesting the Stack Exchange corpus needs more depth in that tag") rather than hiding or softening it.

## Phase 5 — Frontend and eval dashboard

1. Build the Next.js (App Router) query/chat interface calling the FastAPI backend over a real API.
2. Build a second page: the eval dashboard, showing aggregate RAGAS/DeepEval scores, a per-question breakdown, and a chart comparing retrieval faithfulness vs. answer accuracy across the test set (and the fix-generation parse-pass rate).
3. Ensure retrieval misses are visibly and honestly surfaced in the UI (not silently hidden) when the Answer Generator declines to answer.

## Phase 6 — Deployment

1. Deploy FastAPI backend to Render, Railway, or Fly.io free tier.
2. Deploy Next.js frontend to Vercel.
3. Verify the live deployed version end-to-end (not just localhost) — actually query it, actually trigger a fix-generation request, actually load the eval dashboard.
4. Confirm no secrets are exposed client-side or committed to the repo.

## Phase 7 — README and case study

1. Write the README assuming a hiring manager will skim it in under 90 seconds: what it does, real eval numbers up front, architecture diagram/summary, how to run locally, licensing/attribution notes.
2. State plainly and specifically what makes this different from a generic PDF chatbot: hybrid structured/unstructured retrieval, the agentic validate-and-reflect fix loop, and the independently-scored eval layer.
3. Do not claim this is a commercial product (n8n's content is under a fair-code license, not OSI open source) — frame it as an open, attributed portfolio/research project.
4. Draft the one-sentence interview-ready summary, e.g.: "I built an agentic RAG copilot over n8n workflows, GitHub Actions configs, and API error patterns that not only answers questions but generates and validates corrected YAML/JSON fixes, with an independent RAGAS/DeepEval evaluation layer scoring retrieval and generation separately."

## Phase 8 — 4th domain: Agentic AI / Multi-Agent Orchestration tooling

Added after Phase 7, once all seven original phases were live. Same ingestion → retrieval/router →
agentic fix loop → eval → frontend/docs order as Phases 1–5, applied to a new `agentic_ai` domain
covering AI agent tooling, agentic orchestration frameworks, and MCP.

### 8a. Sourcing — with a real licensing constraint

The request that prompted this domain named Claude/OpenAI/Cursor docs and blogs explicitly. All three
carry explicit anti-scraping ToS clauses (not just silence, unlike the GitHub Actions YAML precedent in
1c) — excluded outright per this project's own licensing rule, not worked around. Cursor has no
open-source substitute and is dropped. Approved substitute sources (all redistributable, see
ATTRIBUTIONS.md for exact licenses and per-source chunk counts): `github/docs` (`content/actions` fills
the pre-existing GitHub Actions prose gap; `content/copilot` becomes the Cursor substitute),
`modelcontextprotocol/modelcontextprotocol`, `crewAIInc/crewAI`, `openai/openai-agents-python`,
`langchain-ai/langgraph`, `microsoft/autogen`, `anthropics/claude-cookbooks` (the Claude/OpenAI
substitute — their own MIT-licensed SDK/cookbook repos, not their ToS-blocked doc sites).

### 8b. Chunking — two new structured artifact types, one new prose complication

- `agent_config`: CrewAI YAML agent/task configs, chunked per agent/task (same one-chunk-per-unit
  philosophy as n8n nodes/GHA jobs).
- `agent_code`: Python examples, chunked per top-level function/class via `ast.parse` (a genuinely new
  chunking pattern — source-code parsing, not YAML/JSON tree-walking) or per notebook cell for `.ipynb`
  sources; notebook markdown cells become `doc_prose` in the same pass.
- `mcp_schema`: MCP JSON schema type definitions and request/response examples, one chunk per
  definition/example.
- `github/docs`' Markdown uses build-time Liquid templating (`{% data variables.X %}`,
  `{% ifversion %}`, IDE/OS-tab conditionals) — resolved via a small dedicated module rather than
  indexed as raw template syntax; a handful of pages driven by genuine `{% for %}` loops over external
  data tables were excluded rather than partially resolved.

### 8c. Retrieval/router

`agentic_ai` added to the Query Router's `Domain` literal with its own weighted STRONG/WEAK markers
(framework names strong, "agent"/"orchestrat*" weak); supports `factual_lookup` and `fix_generation`
but not `error_diagnosis` (no failure-log corpus exists for these frameworks — an honest gap, like
`api_errors` having no fix-generation today). `github_actions` also gained prose retrieval for the
first time (previously zero prose corpus).

### 8d. Fix Agent

Two validated fix kinds under one domain: `ast.parse()` for Python agent code (no subprocess needed,
unlike `actionlint`), and a self-derived CrewAI structural schema (role/goal/backstory or
description/expected_output) for YAML configs — CrewAI publishes no official schema either, same
honesty-note precedent as the n8n schema. Which kind a request wants is read off the LLM's own fenced
code-block language tag, with a content-sniff fallback if that tag is missing.

### 8e. Eval

20 new questions (12 factual_lookup, 8 fix_generation, stratified across the seven sources), appended
to the existing 61 with IDs `eval-061`..`eval-080`. Full 81-question re-run required — aggregate metrics
are computed globally, not incrementally.

## Phase 9 — Extending the agentic_ai domain: OpenAI Codex, HuggingFace, LangChain

Added the same day as Phase 8, in response to a follow-up request to also cover Claude Code, OpenAI/
Codex, Cursor, Windsurf, HuggingFace, and LangChain docs. Re-checked licensing per name: Claude Code's
repo is public but "All rights reserved" (Anthropic Commercial Terms), and Cursor/Windsurf both have
explicit anti-scraping AUPs/MSAs with zero open-source docs mirrors anywhere — all three skipped, same
reasoning as Phase 8. Three names had genuine redistributable substitutes and were added as more
`doc_prose` sources within the existing `agentic_ai` domain (no new artifact types, no new Fix Agent
validators — these four sources are prose-only):

- `openai/codex` (`docs/`, Apache-2.0) — thinner than expected on inspection: 8 of 15 files are short
  redirect stubs to `developers.openai.com`, only `install.md` is substantive. Included anyway and
  stated plainly in ATTRIBUTIONS.md, per the "no fabricated/massaged data, even mediocre" rule.
- `huggingface/hub-docs` + `huggingface/transformers` (`docs/`, both Apache-2.0) — `transformers`
  scoped to top-level guides/`tasks/`/`quantization/`/`main_classes/` only; `model_doc/` (513
  near-identical per-architecture reference pages) excluded as low-density volume, same judgment as
  CrewAI's version-folder exclusion in Phase 8.
- `langchain-ai/docs` (`src/oss/`, MIT) — LangChain's docs moved off-repo like LangGraph's did, but
  landed at this separate, still-open repo (unlike LangGraph's own dead `docs/llms.txt` link-index).
  Scoped to `langchain/`, `langgraph/`, `concepts/`, `deepagents/`; excluded `python/integrations/`
  (same low-density issue as `model_doc/`), `javascript/`, and `langchain/frontend/` (TypeScript/React
  UI-integration content that leaked into an early spot-check).

Two real ingestion bugs found and fixed during this phase (both documented in detail in
ATTRIBUTIONS.md): `transformers`' Apache-License HTML-comment header was leaking into extracted chunk
titles (fixed by stripping `<!--...-->` blocks), and `tiktoken`'s token counter raised on the literal
string `<|endoftext|>` appearing in HuggingFace's own LLM-training docs (fixed via
`disallowed_special=()`). Router markers extended for the four new sources' vocabulary
(`codex`/`huggingface`/`transformers`/`langchain`); 8 new factual_lookup eval questions appended
(`eval-081`..`eval-088`) — no fix_generation, since none of these sources added a fixable artifact type.

## Standing rules throughout all phases

- Do not fabricate data, sources, or eval numbers at any phase.
- Do not skip the licensing/attribution logging step during ingestion — retrofit-attributing later is much harder.
- Do not let frontend or deployment work start before Phase 4 (eval) produces real numbers.
- If a data source proves harder to access than expected (rate limits, ToS discomfort, dataset quality issues), fall back to the documented alternative in the research reference rather than silently improvising an unlicensed workaround.
