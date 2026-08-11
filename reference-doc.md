# WorkflowGPT / CI/CD Copilot — Build Reference: Real Data Sources, Retrieval Techniques & Legal Notes

## TL;DR
- **You can build this entirely on real, already-collected data.** The strongest immediately-usable assets are: n8n's official template API (`api.n8n.io/templates/search`) plus community GitHub mirrors of 2,000–10,000+ workflow JSON files; the GHALogs Zenodo dataset (513k GitHub Actions runs *with full raw logs*, CC-BY-SA-4.0); the Stack Exchange Data Dump (Stack Overflow Q&A tagged `github-actions`/`n8n`, CC-BY-SA); and official docs repos (`n8n-io/n8n-docs`, `github/docs`) that ship clean Markdown.
- **The defensible architecture is hybrid retrieval**: route structured config (workflow YAML/JSON) through AST/structure-aware chunking (the cAST method, EMNLP 2025) into one index, and unstructured prose (docs, forum threads) through semantic chunking into another; then layer an agentic self-correction loop (LangGraph "generate → validate YAML → reflect → regenerate") for fix suggestions. This is well-precedented in 2025–2026 literature and is exactly the differentiator that reads well on a resume.
- **Watch three licensing traps**: the Stack Overflow dump now sits behind a login + an anti-LLM-training clause; n8n's docs/forum are *fair-code* (Sustainable Use License), not OSI open source; and GitHub's scraping policy only clearly blesses scraping for *open-access research*, so prefer the API + pre-collected datasets over bulk scraping.

## Key Findings

### 1. n8n data sources (abundant and immediately usable)
- **Official template API** — `https://api.n8n.io/templates/search`, plus `/templates/categories`, `/templates/collections`, and `/templates/workflows/{id}` (returns the importable workflow JSON in a `workflow` key). This is the single best n8n source: a documented, public JSON API backing the template library, which as of August 2026 lists **11,298 templates** (`n8n.io/workflows`: "11298 Workflow Automation Templates…Explore 11190 automated workflow templates from n8n's global community"). No scraping needed.
- **GitHub mirror collections** (all ready-to-import `.json` workflow files):
  - `ScraperNode/awesome-n8n-templates` — 8,697+ workflows across 25 categories, 236 integrations; MIT-licensed repo.
  - `zengfr/n8n-workflow-all-templates` — 9,146+ (now 10,258+) workflows, refreshed monthly.
  - `Danitilahun/n8n-workflow-templates` — 2,053 workflows with a bundled FastAPI search/browse server and SQLite indexer (a good ingestion-pipeline reference itself).
  - `enescingoz/awesome-n8n-templates` — 280+ curated templates with per-category READMEs.
- **HuggingFace datasets** (workflow JSON + instruction pairs, useful for eval/fine-tune):
  - `mbakgun/n8nbuilder-n8n-workflows-dataset` — Alpaca + OpenAI-format JSONL (prompt→workflow).
  - `DavidrPatton/n8n-Toolkit` — multi-modal instruction dataset with task-type/difficulty labels.
  - `arkelai/n8n-workflows-v2-4k`, `arkelai/n8n-workflows-2k`, `ruh-ai/n8n-workflow`, `eclaude/n8n-workflows-sft`.
- **Official documentation** — `docs.n8n.io`, source in `github/n8n-io/n8n-docs` as MkDocs Markdown under `docs/` (subfoldered by topic). The site publishes an **`llms.txt`** and per-page `.md`. Community project `techfundoffice/n8n-docs-llms` ships a pre-concatenated `llms.txt` of the entire docs — a drop-in RAG corpus.
- **Community forum** — `community.n8n.io` runs on **Discourse**, which exposes a JSON API: append `.json` to any topic/category URL (e.g., `/c/questions/6.json`, `/t/{topic-id}.json`), and use `/latest.json`, `/search.json?q=`. This is the richest source of *error threads and troubleshooting Q&A* (the most valuable content for a debugging copilot).

### 2. GitHub Actions data sources
- **GHALogs (the headline dataset)** — Zenodo record `10.5281/zenodo.10154920` (concept DOI `...919`), MSR 2025 data paper by Moriconi, Durieux, Falleri, Troncy & Francillon (EURECOM et al.), IEEE/ACM proceedings pp. 669–673. Per the abstract: **"116k CI/CD workflows…across 25k public code projects spanning 20 different programming languages. This dataset includes 513k workflow runs encompassing 2.3 million individual steps…To the best of our knowledge, this is the largest dataset of CI/CD runs that includes full log data"** (precisely: 116,259 workflows, 348,909 jobs, 2,327,747 steps; 640 GB uncompressed). Files on Zenodo: `github_run_logs.zip` (142.3 GB raw log text), `runs.json.gz` (1.1 GB run metadata JSON-lines), `repositories.json.gz` (69.2 MB); total 143.4 GB. License **CC-BY-SA-4.0**. Note: it does **not** include the workflow YAML definition files — only runtime logs + parsed metadata (status, `conclusion`, timings, container image, actions used, parsed shell-step ASTs).
- **Workflow YAML dataset** — Cardoen/Mens/Decan "A dataset of GitHub Actions workflow histories," Zenodo `10.5281/zenodo.10259013` — the complement to GHALogs, covering the actual `.github/workflows` YAML files and their version histories (GHALogs cites it as related work).
- **TravisTorrent** — Zenodo `10.5281/zenodo.1254890`; ~2.64M builds (Jan 2013–Dec 2017) across Java/Ruby/Python/JS; CSV + SQL dumps (~1.8 GB unpacked CSV); ~55–66 features per build including pass/fail/errored outcome. Older (Travis, not Actions) but the canonical build-failure-prediction dataset. `monperrus/travistorrent-java-ci-build-dataset` is a Java-only slice (519,373 builds).
- **GitHub REST/Search API for live YAML collection** — Search Code endpoint (`GET /search/code?q=...+path:.github/workflows+extension:yml`) is limited to **10 requests/minute** and requires authentication; other search endpoints allow 30/min. Core REST is 5,000 req/hr authenticated (60 unauthenticated; 15,000 for GHEC org apps). Use `GET /repos/{owner}/{repo}/contents/.github/workflows` to pull raw YAML. For bulk, GH Archive on BigQuery is the scalable alternative.
- **Stack Overflow / Stack Exchange** — the `github-actions` tag has tens of thousands of Q&A. Two access paths: (a) **Stack Exchange Data Dump** (7z XML: Posts, Comments, Tags, PostLinks, PostHistory) — historically on `archive.org/details/stackexchange`, now gated behind login + terms; (b) the live **Stack Exchange API** (`api.stackexchange.com`, JSON, `tagged=github-actions`).
- **CI failure ML research** — the "LLM-Driven CI Failure Diagnosis and Automated Repair" line of work (JTIE 2025) and `lca-ci-builds-repair` (LongCodeArena) pair failures with validated fixes; LogChunks (797 labeled Travis logs).

### 3. API error / debugging pattern sources
- **Stack Overflow tags** `api`, `rest`, `http-status-codes`, `http`, `curl` — same dump/API access as above; the highest-signal source for "what does error X mean + how to fix."
- **HTTP status codes** — MDN Web Docs (`developer.mozilla.org/en-US/docs/Web/HTTP/Status`, CC-BY-SA 2.5) and the IANA HTTP Status Code Registry (authoritative, machine-readable). Good structured reference layer.
- The n8n forum itself is full of concrete API error threads (e.g., `AxiosError: Request failed with status code 400`), which double as both n8n *and* API-error training/eval material.

### 4. Hybrid structured/unstructured retrieval precedent
- **cAST (chunking via Abstract Syntax Tree)**, Zhang et al., EMNLP 2025 Findings (arXiv:2506.15655, Carnegie Mellon + Augment Code), code at `github.com/yilinjz/astchunk`. Recursively splits large AST nodes and merges siblings within a size budget; per the abstract it improves code generation "e.g., boosting Recall@5 by 4.3 points on RepoEval retrieval and Pass@1 by 2.67 points on SWE-bench generation" versus line-based chunking. This is the citation to anchor your YAML/JSON chunking design.
- **Practical takeaway for YAML/JSON**: parse with a structure-aware parser (tree-sitter / `ruamel.yaml` / `PyYAML` to a tree), chunk on node boundaries (per job, per step, per top-level key) rather than fixed tokens, and attach metadata (file path, `on:` triggers, action names) as filterable fields. Prose docs use standard semantic chunking (e.g., ~600-token chunks with ~100-token overlap, a config validated in the 2026 "Agent-Orchestrated Adaptive RAG" study).
- **Routing**: keep two collections (structured configs vs prose) and either route by query classification or run hybrid dense+BM25 retrieval and merge — the pattern used across the AST-RAG writeups and AstraAI (HPC codebase RAG, which serializes code chunks + metadata to JSON and embeds only the `user_intent` field).

### 5. Agentic RAG for fix-suggestion
- **Self-correcting loop pattern** (LangGraph): nodes for Generate → Check/Execute → Reflect → regenerate, looping to a retry cap. Multiple concrete implementations exist (LearnOpenCV "self-correcting RAG agent," "self-corrective agentic RAG" with Pydantic v2 structured output + hybrid search).
- **Domain-specific precedent**: RAVEN (Agentic RAG for automated vulnerability repair, arXiv:2606.22647); the "self-healing CI/CD" maturity model (Observer → Gatekeeper → Healer); Bouzenia & Pradel's LLM agent that autonomously sets up and runs test suites; the "From Assistance to Agency" study of autonomy/control in CI/CD pipelines.
- **Structured-output best practice**: constrain generation to valid YAML via JSON-schema/grammar-constrained decoding or Pydantic models, then *validate* the emitted YAML (parse it, run `actionlint` for GitHub Actions or n8n's own JSON schema) inside the agent loop before returning — the "generate-then-verify" pattern. The JTIE CI-repair paper found constrained generation improved diff similarity (Token-F1 to 0.923) and that adding workflow-YAML context consistently helped.

### 6. Eval datasets/frameworks
- **Frameworks (2026 best practice)**: RAGAS and DeepEval are the two standards; both compute Faithfulness + Answer Relevancy for the generator and Context Precision/Recall for the retriever. Score retriever and generator *separately*. The 2026 guidance stresses that generation-only metrics hide retrieval regressions — you must track context recall too (target Precision@k 0.7+). DeepEval integrates into CI pipelines ("SOTA RAG metrics in 5 lines of code"); TruLens/Arize Phoenix/Opik add production observability.
- **Code-debugging benchmarks to model your eval set on**:
  - **SWE-bench Verified** — per OpenAI, "a subset of the original test set from SWE-bench, consisting of 500 samples verified to be non-problematic by our human annotators" (drawn from 12 Python repos; ~68% of the original 2,294 instances filtered out).
  - **SWE-bench Lite** — per the cAST paper, "a 300-problem subset where each issue is solvable by editing a single file."
  - **DebugBench** — Tian et al., ACL 2024 Findings (arXiv:2401.04621): "an LLM debugging benchmark consisting of 4,253 instances. It covers four major bug categories and 18 minor types in C++, Java, and Python" (C++ 1,438 / Java 1,401 / Python 1,414; bugs implanted via GPT-4 on LeetCode code released after June 2022 to limit leakage).
  - Also: RepoDebug (repo-level multi-language debugging) and debug-gym (interactive debugging environment integrating Aider, Mini-nightmare, SWE-bench).
- **Recommended eval-set design** (50–100 Q): stratify across the three domains (n8n / GitHub Actions / API errors) and across task types (factual lookup, error-diagnosis, config-fix-generation). For fix-generation items, store a gold corrected YAML/JSON and grade with an executable/parse check plus a code-aware similarity metric (not BLEU) — mirroring DebugBench's test-suite verification.

### 7. Licensing notes (per source)
- **n8n docs & forum**: fair-code under the **Sustainable Use License** (SUL, adopted March 2022, replacing Apache-2.0 + Commons Clause) — permits internal/non-commercial/personal use and free redistribution; a public portfolio project is fine, but avoid presenting it as a commercial product. Not OSI open source. Forum posts are governed by the community ToS at `community.n8n.io/tos`; treat user posts as attributable content. n8n's own AI Terms state n8n won't use customer content to train models — a courtesy worth mirroring.
- **n8n community template repos**: MIT (`ScraperNode`); `enescingoz`/`WorkflowForge` note templates belong to original creators — attribute, don't claim ownership.
- **Stack Overflow / Stack Exchange**: content is **CC-BY-SA** (2.5→3.0→4.0 by era). Attribution required — "Visually indicate that the content is from the Stack Exchange network" and "Link back to the original source question or answer" plus author names. The data-dump download now requires login and agreement to terms that **prohibit using the file for LLM training** ("this file is being provided to me for…projects that do not include training a large language model") and reserve the right to cut off redistributors; the live API content remains CC-BY-SA.
- **GitHub public repos**: viewing/forking allowed by ToS, but each repo's own LICENSE governs reuse (many workflow files have no license = all rights reserved). GitHub's Acceptable Use Policy allows scraping of "public, non-personal information from GitHub for research purposes, only if any publications resulting from that research are open access," and forbids activity that places a disproportionate burden on servers. Prefer the API.
- **GitHub docs (`github/docs`)**: content in `content/`, `data/`, `assets/` is **CC-BY-4.0** (site-building code is MIT) — clean to reuse with attribution.
- **GHALogs**: CC-BY-SA-4.0. **TravisTorrent**: CC-BY-SA. **MDN**: CC-BY-SA 2.5.

## Details

### Recommended ingestion pipeline (concrete)
1. **n8n structured corpus**: Pull workflow JSON via `api.n8n.io/templates/search` (paginate) + clone `ScraperNode/awesome-n8n-templates`. Parse each JSON; chunk per-node (node type, parameters, credentials refs) with metadata. Store in a "configs" vector collection + a metadata DB for filtering.
2. **n8n prose corpus**: Ingest `techfundoffice/n8n-docs-llms` `llms.txt` (or clone `n8n-io/n8n-docs` and read `docs/**/*.md`). Semantic-chunk (~600 tokens/100 overlap). Pull forum error threads via Discourse `.json` endpoints; store question+accepted-answer pairs.
3. **GitHub Actions structured corpus**: Download the Cardoen/Mens/Decan YAML dataset (Zenodo `...10259013`) for real workflow YAML; optionally top up with live Search-Code API pulls. AST/structure-chunk per job/step.
4. **GitHub Actions failure corpus**: Download GHALogs (`...10154920`) run metadata (`runs.json.gz`) + a sample of raw logs; pair failing runs with their logs. Use for error-pattern retrieval and eval.
5. **API-error prose corpus**: Stack Exchange dump/API for `github-actions`/`api`/`http-status-codes` tags + MDN/IANA HTTP status reference.
6. **Retrieval**: two collections (configs vs prose), hybrid dense+BM25, query router. **Generation**: agentic LangGraph loop with schema-constrained YAML/JSON output + `actionlint`/n8n-schema validation before returning a fix.
7. **Eval**: 50–100 stratified questions; RAGAS/DeepEval for faithfulness/relevancy/context-recall; executable parse-check for fix-generation items.

### Source-quality caveats surfaced during research
- GHALogs paper cites concept DOI `...919` while the versioned record is `...920` — same dataset; a v1.0.1 (`zenodo.org/records/14796970`) also exists.
- TravisTorrent field count is reported as 55 (original Beller et al. 2017 MSR paper: "we provide 55 data fields for each build") vs 66 (a 2026 PLOS ONE paper) — likely derived features in the latter. Build count is widely cited as 2,640,825 from 1,359 projects.
- Several HuggingFace n8n datasets have flaky dataset-viewer/Parquet conversion (500 errors, schema-cast errors from mixed Alpaca/OpenAI columns) — download raw JSONL rather than relying on `load_dataset`'s auto-conversion.

## Recommendations
1. **Week 1 — ingest the zero-scrape assets first**: n8n template API + `n8n-docs-llms` `llms.txt` + GitHub `content/` docs + one HuggingFace n8n dataset. This alone gives a demoable RAG over n8n.
2. **Week 2 — add GitHub Actions**: GHALogs metadata + Cardoen YAML dataset + a small live Search-Code pull. Build the two-collection hybrid retriever and the AST/structure chunker for YAML.
3. **Week 3 — agentic fix layer**: implement the LangGraph generate→validate(`actionlint`)→reflect loop with schema-constrained output. This is the resume centerpiece — it's the difference between "another prose RAG" and "an agent that emits a validated corrected config."
4. **Week 4 — eval + polish**: build the 50–100 Q stratified eval set, wire RAGAS + DeepEval into CI, and report faithfulness/context-recall numbers plus a fix-generation parse-pass rate in your README.
5. **Thresholds that change the plan**: if forum Discourse `.json` scraping is rate-limited or ToS-uncomfortable, drop it and lean on the Stack Exchange API (clear CC-BY-SA). If GHALogs' 142 GB log ZIP is too big, use only `runs.json.gz` metadata + a sampled subset of logs. If live GitHub Search-Code hits the 10-req/min wall, switch to GH Archive on BigQuery or rely solely on the pre-collected YAML dataset.

## Caveats
- Do not present the copilot as a commercial product given n8n's SUL and the Stack Overflow anti-LLM-training clause; frame it as an open, attributed portfolio/research project and keep an attributions file (author names + source links for any CC-BY-SA content).
- Many raw GitHub workflow YAMLs carry no license (all-rights-reserved by default) — prefer the explicitly-licensed Zenodo YAML dataset for redistribution; use live API pulls only for retrieval-at-inference, not for republishing a corpus.
- Community "awesome" repos aggregate third-party templates whose original authors retain rights — attribute and don't claim ownership.
- GHALogs contains logs, not YAML; if your fix-suggestion feature needs to *edit* workflow YAML, you need the Cardoen YAML dataset (Zenodo `...10259013`) or live API pulls in addition.
- The GitHub "research/open-access" scraping carve-out is aimed at academic publication; for a portfolio project, staying on APIs and pre-licensed datasets is the cleaner posture than relying on that clause.
