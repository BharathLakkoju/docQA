# Attributions

Tracks source, author, and license for every piece of content ingested into the WorkflowGPT / CI-CD Copilot corpus that carries an attribution requirement (CC-BY-SA, CC-BY, MIT-with-attribution, or platform ToS requiring credit/link-back). Populated during ingestion (Phase 1) — one row appended per source item, not backfilled after the fact.

Do not delete rows once a source has been ingested, even if it's later dropped from the corpus, so provenance stays auditable.

## n8n structured corpus (workflow templates)

Full per-template attribution log (template ID, title, author, source URL, date pulled) lives in
[`data/processed/n8n/template_attributions.csv`](data/processed/n8n/template_attributions.csv) — 296
templates pulled live via `api.n8n.io/templates/search` + `/templates/workflows/{id}` on 2026-08-11
(4 of 300 attempted 404'd/were retired and were skipped, not substituted). Each row's `source_url`
links back to the template's page on n8n.io per its original author.

| Source | License | Notes |
|---|---|---|
| api.n8n.io/templates | Individual template author retains rights; publicly listed on n8n.io | See CSV above for per-item author + link-back. |

## n8n community mirror repos

| Repo | License | Notes |
|---|---|---|
| ScraperNode/awesome-n8n-templates | MIT | Templates belong to original creators; repo license covers the aggregation, not individual workflow authorship. 721 workflows sampled (up to 30 per category, 25 categories) on 2026-08-11 — not the full ~8,700, see `ingestion/n8n/chunk_mirror_templates.py`. |

## n8n prose corpus (docs)

| Source | License | Notes |
|---|---|---|
| n8n-io/n8n-docs (docs.n8n.io) | Sustainable Use License (fair-code, not OSI) | Non-commercial/personal use and redistribution permitted; do not present this project as a commercial product. |

## n8n community forum threads (Discourse)

Full per-topic attribution log lives in
[`data/processed/n8n/forum_attributions.csv`](data/processed/n8n/forum_attributions.csv) — 400 topics
pulled live via `community.n8n.io` search.json + `/t/{id}.json` on 2026-08-11, targeting error/debugging
threads (AxiosError, HTTP status codes, timeouts, etc. — see `ingestion/n8n/fetch_forum_threads.py` for
the query list). Each chunk pairs the question with the accepted answer where one exists (115/400), else
the top-voted reply, per the community ToS's attribution requirement (author + link-back, both retained
in metadata).

| Source | License | Notes |
|---|---|---|
| community.n8n.io (Discourse) | Community ToS (CC-BY-SA-style; attribute + link back) | See CSV above for per-item authors + link-back. |

## GitHub Actions structured corpus

**Deviation from the Zenodo dataset named in INSTRUCTIONS.md 1c, documented here per the "state the
assumption and proceed" rule in CLAUDE.md:** the Cardoen/Mens/Decan `workflows.tar.gz` (Zenodo
10.5281/zenodo.10259013) is 1.4GB — its own `workflows.csv.gz` is metadata-only and points into that
archive by content hash, so there's no smaller redistributable slice of it. Instead this corpus was
built from the **live GitHub REST Search Code API** (297 real `.github/workflows/*.yml` files, job-level
chunked, pulled 2026-08-11 via `ingestion/github_actions/fetch_workflows.py`, using the local `gh` CLI's
own auth so no token ever touched a log). Per CLAUDE.md's licensing rule this is retrieval-at-inference
use, not bulk redistribution: raw YAML lives in `data/raw/` and chunked output in `data/processed/`,
both gitignored and never committed. Per-file license lives in
[`data/processed/github_actions/workflow_attributions.csv`](data/processed/github_actions/workflow_attributions.csv)
(most raw GitHub workflow files carry no explicit license — `NOASSERTION` — consistent with the "many
raw GitHub workflow YAMLs carry no license" caveat in reference-doc.md; this is why the corpus is used
for local retrieval only, not redistributed).

| Source | License | Notes |
|---|---|---|
| GitHub REST Search Code API (live) | Per-repo, mostly NOASSERTION — see CSV | Local index only, gitignored, not redistributed. |
| Cardoen/Mens/Decan dataset (Zenodo 10.5281/zenodo.10259013) | See Zenodo record | Named as the redistributable alternative in INSTRUCTIONS.md; not used here — see deviation note above. |

## GitHub Actions failure corpus

Sourced by **streaming** `runs.json.gz` directly off Zenodo (never downloading the full 1.06GB file to
disk) and keeping only `conclusion in {failure, timed_out}` records, stopping once 500 were collected
(reached after scanning just 3,125 run records / 5MB — see `ingestion/github_actions/fetch_failure_runs.py`).
The full 142GB raw log archive was never touched, per INSTRUCTIONS.md 1d.

**Data-quality caveat, stated plainly per CLAUDE.md ("no fabricated data... say so plainly"):** GHALogs'
`log_insights[].steps[].error` field is the *dataset's own extraction tool* failing to parse shell
syntax (e.g. literally `{"error": "Invalid request", "originalError": ""}` on inspection) — it is not a
reliable signal for the actual CI failure cause, and the chunker deliberately excludes it rather than
present it as a root-cause explanation. What's kept is verifiably real: which repo/workflow/event
failed, and which actions/shell steps ran in that job.

| Source | License | Notes |
|---|---|---|
| GHALogs (Zenodo 10.5281/zenodo.10154920) | CC-BY-SA-4.0 | `runs.json.gz` streamed, not downloaded; only 500 failing-run records + associated `log_insights` kept. |

## API/HTTP error prose corpus (Stack Exchange)

Full per-item attribution log (question + each answer, author, link-back, license) lives in
[`data/processed/api_errors/stackexchange_attributions.csv`](data/processed/api_errors/stackexchange_attributions.csv)
— 400 questions (100/tag across `github-actions`, `http-status-codes`, `rest`, `http`) pulled live via
`api.stackexchange.com` on 2026-08-11. Note: `api` is not an actual Stack Overflow tag (confirmed via
`/tags/api/info` returning zero items) despite being named as a candidate tag in reference-doc.md, so it
was substituted with `rest` and `http` — both real, both already named as alternatives in the same
document. Not the gated Stack Overflow data dump (anti-LLM-training clause) — the live API only, whose
content remains CC-BY-SA per Stack Exchange's terms.

| Source | License | Notes |
|---|---|---|
| api.stackexchange.com (live) | CC BY-SA 4.0 (per-item, see CSV) | See CSV above for per-item author + link-back. |

## Reference layers

| Source | License | Notes |
|---|---|---|
| MDN HTTP status code reference (mdn/content, `reference/status/`) | CC-BY-SA 2.5 | 61 status-code pages, cloned via sparse checkout 2026-08-11. |
| IANA HTTP Status Code Registry | Public/authoritative registry | 64 assigned status codes (unassigned ranges skipped), pulled 2026-08-11. |

## Agentic AI corpus (4th domain: `agentic_ai`)

**Scope deviation from what was originally asked, documented here per CLAUDE.md's "state the
assumption and proceed" rule:** the request that prompted this domain named Claude docs/blogs, OpenAI
docs/blogs, and Cursor docs/blogs explicitly. All three carry **explicit anti-scraping ToS clauses**
(Anthropic's ToS prohibits "crawling or scraping data or information"; OpenAI's Terms of Use prohibit
"automatically or programmatically extracting data or Output"; Cursor's MSA bars "unauthorized
third-party programs to harvest, scrape, or extract data") — a materially different situation from the
GitHub Actions YAML precedent below (silence/`NOASSERTION`, not an explicit prohibition), so per this
project's own licensing rule they are excluded outright, not worked around. **Cursor has no
open-source substitute and is dropped entirely.** Claude and OpenAI content is included instead via
their own MIT-licensed open-source repos (`claude-cookbooks`, `openai-agents-python`) rather than their
ToS-blocked doc sites — same topical coverage, cleaner license. All seven sources below were cloned
2026-08-12 (shallow, `--depth 1`; `github/docs` and `microsoft/autogen` additionally used
`--filter=blob:none`/sparse-checkout to avoid pulling unnecessary history/media) and are gitignored raw
data, chunked into `data/processed/agentic_ai/` and (for one slice) `data/processed/github_actions/`.

| Source | License | Notes |
|---|---|---|
| `github/docs` (`content/`) | CC-BY-4.0 (content), MIT (code samples) | 245 files under `content/actions/**` tagged **`domain: github_actions`** (fixes the pre-existing gap where GitHub Actions had zero prose corpus — see CLAUDE.md's original gap analysis); 543 files under `content/copilot/**` tagged `domain: agentic_ai` (Copilot is this project's clean substitute for the ToS-blocked Cursor request). Raw Markdown uses GitHub's own Liquid templating (`{% data variables.product.X %}`, `{% ifversion %}`, IDE/OS-tab conditionals) — resolved via `ingestion/agentic_ai/github_docs_liquid.py` using the repo's own `data/variables/*.yml`, not left as raw template syntax. Six pages that render pricing/feature-comparison tables via genuine Liquid `{% for %}`/`{% case %}`/`{% assign %}` loops over external data tables were excluded rather than indexed as broken template fragments (see that module's docstring for the full list and rationale — resolving them needs a real Liquid interpreter, out of scope here). 2 files/2308 chunks total between both domain slices. |
| `modelcontextprotocol/modelcontextprotocol` | Apache-2.0 (spec/code) / CC-BY-4.0 (docs) — repo mid-transition from an earlier MIT license, per its own `LICENSE` file | 256 doc/spec pages (latest `2026-07-28` snapshot only, plus non-versioned community/dev pages — older dated snapshots skipped to avoid indexing the same conceptual pages six times over) → `doc_prose`; 155 `$defs` type definitions + 129 concrete request/response examples from `schema/2026-07-28/` → `mcp_schema`. |
| `crewAIInc/crewAI` | MIT | 197 docs pages (`docs/edge/en/**`, the current/latest version — the repo keeps a full docs snapshot per historical version back to v1.10.0, which would have 32x-duplicated near-identical content had "edge" not been picked specifically) → `doc_prose`; 6 canonical `agents.yaml`/`tasks.yaml` template files (the exact files CrewAI's own `crewai create crew` CLI scaffolds into every new project) → 14 `agent_config` chunks, one per agent/task. |
| `openai/openai-agents-python` | MIT | 386 docs pages → `doc_prose`; 215 example `.py` files, AST-chunked per top-level function/class → `agent_code`. |
| `langchain-ai/langgraph` | MIT | **Deviation:** LangGraph's docs moved off-repo to docs.langchain.com (the repo's `docs/llms.txt` is just a link index, no actual prose) — no `doc_prose` chunks from this source's docs/ folder. Its 35 example notebooks are still real, redistributable content: code cells → `agent_code`, markdown cells → `doc_prose` (135 + 41 chunks). |
| `microsoft/autogen` | CC-BY-4.0 (docs, root `LICENSE`) / MIT (code, `LICENSE-CODE`) | Scoped to `python/` only (root `docs/` is almost entirely the .NET binding's docs, off-topic) — 68 markdown docs → `doc_prose`; 61 example `.py` files + 49 notebooks (code cells → `agent_code`, markdown cells → `doc_prose`) — 193 + 342 + 102 chunks. |
| `anthropics/claude-cookbooks` | MIT | 96 notebooks (code cells → `agent_code`, markdown cells → `doc_prose`) — 934 + 340 chunks. This project's substitute for Anthropic's ToS-blocked docs/blog. |

**Ingestion code:** `ingestion/agentic_ai/{chunk_docs,chunk_agent_configs,chunk_mcp_schema,chunk_agent_code}.py`
+ shared helpers in `ingestion/common/code_chunking.py` (new: AST-based Python/notebook chunking,
distinct from the YAML/JSON tree-walking used for n8n/GitHub Actions structured chunking) and
`ingestion/agentic_ai/github_docs_liquid.py` (new: Liquid-tag resolution, needed only by this source —
none of the other 27 sources across all four domains use build-time templating).

### Phase 9 additions (2026-08-12): OpenAI Codex, HuggingFace, LangChain

The user asked to also cover Claude Code docs, OpenAI/Codex docs, Cursor IDE docs, Windsurf IDE docs,
HuggingFace docs, and LangChain/LangGraph docs. Re-checked licensing per-source (same standard as
above): Claude Code's own repo (`anthropics/claude-code`) is publicly viewable but explicitly
"All rights reserved" under Anthropic's Commercial Terms of Service, not an open license, and its real
docs live on the same ToS-blocked `code.claude.com` property as before — **skipped**. Cursor and
Windsurf were re-checked specifically: Windsurf's Acceptable Use Policy bars scraping/crawling
identically to Cursor's MSA, and neither has any open-source docs mirror anywhere (checked GitHub
directly for community mirrors — none found) — **both skipped, no substitute exists**. The other three
had genuine redistributable substitutes:

| Source | License | Notes |
|---|---|---|
| `openai/codex` (`docs/`) | Apache-2.0 | **Thinner than expected, stated plainly rather than overclaimed:** of the 15 files, 8 (`config.md`, `exec.md`, `execpolicy.md`, `getting-started.md`, `sandbox.md`, `slash_commands.md`, `example-config.md`, `agents_md.md`) are short (~130-750 char) redirect stubs pointing at `developers.openai.com` — the actual hosted docs site — rather than real in-repo content; only `install.md` (system requirements, real setup steps) is substantive end-user documentation. Included anyway since the stubs are still real, dereferenceable, on-topic content, just low-density. 18 chunks. |
| `huggingface/hub-docs` (`docs/hub/`) | Apache-2.0 | 270 files → 808 chunks. |
| `huggingface/transformers` (`docs/source/en/`) | Apache-2.0 | Scoped to top-level guides + `tasks/`/`quantization/`/`main_classes/` only — `model_doc/` alone is 513 near-identical per-architecture reference pages (BertConfig, BertModel, ...) that would dominate the corpus by volume for low retrieval value; `internal/`/`kernel_doc/`/`serve-cli/`/`community_integrations/`/`reference/` are similarly deep API reference, not conceptual guides. 182 files → 819 chunks. Every file opens with an Apache-License HTML-comment header that was leaking into the extracted chunk title until `strip_doc_noise()` was taught to strip `<!--...-->` blocks — a real bug caught by spot-checking output, not assumed correct. |
| `langchain-ai/docs` (`src/oss/`) | MIT | **Deviation, same pattern as LangGraph:** `langchain-ai/langchain`'s own repo no longer carries docs (code only); its real docs moved to this separate, still-open repo. Scoped to `langchain/`, `langgraph/` (this repo has genuine LangGraph prose, unlike the LangGraph repo's own dead `docs/llms.txt` link-index), `concepts/`, `deepagents/`, and top-level guides — excluded `python/integrations/` (hundreds of thin per-provider pages, same low-density issue as `transformers/model_doc/`), `javascript/`, `reference/`, `contributing/`, `openwiki/`, and `langchain/frontend/` (TypeScript/React UI-integration content, not core LangChain concepts — found leaking into a spot-check and excluded). 164 files → 1,435 chunks. |

A separate real bug, not source-specific: `ingestion/common/prose_chunking.py`'s token-counting call
(`tiktoken`) raised on the literal string `<|endoftext|>` appearing in HuggingFace's own LLM-training
docs (a real special token, treated as disallowed input by default) — fixed by counting tokens with
`disallowed_special=()` so any literal special-token-shaped text in source docs is counted as plain
text, never mis-parsed as control syntax.
