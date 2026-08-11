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
