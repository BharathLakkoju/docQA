# AGENTS.md

This file defines the agent roles inside the WorkflowGPT / CI-CD Copilot system itself (the runtime agentic architecture), as distinct from CLAUDE.md, which governs how Claude Code should behave while building the repo. Read this before writing any orchestration, retrieval, or generation code.

## System shape

This is not a single-shot RAG chain. It is a small agentic pipeline with a router, two retrievers, a generator, a validator, and a reflection loop. Each role below should map to a distinct, testable module — do not merge these into one monolithic function, because the eval layer needs to score retrieval and generation independently.

## Agent roles

### 1. Query Router
**Responsibility:** Classify an incoming user question into a domain (n8n / GitHub Actions / API-error) and a task type (factual lookup / error diagnosis / fix-generation request).
**Why it exists:** Determines which retrieval collection(s) to query and whether the downstream Fix Agent should even engage. A factual lookup ("what does this n8n node do") should never trigger the fix-generation/validation loop; a fix request should always retrieve from the structured (config) collection first.
**Inputs:** raw user query.
**Outputs:** `{domain, task_type, needs_fix_generation: bool}`.
**Notes:** Keep this cheap — a small classification prompt or a lightweight rules+LLM hybrid is fine. Do not over-engineer; its only job is routing.

### 2. Structured Retriever (configs)
**Responsibility:** Retrieve from the Pinecone collection holding AST/structure-chunked n8n workflow JSON and GitHub Actions YAML (chunked per node/job/step, with metadata: file path, trigger type, action/node names).
**Why it exists:** Structured config data breaks under naive fixed-token chunking; this retriever exists specifically to preserve node/job/step boundaries so retrieved context is a coherent, parseable unit, not a mid-block text fragment.
**Inputs:** query (or router-refined query) + domain filter.
**Outputs:** top-k config chunks with metadata.

### 3. Prose Retriever (docs/forum/Q&A)
**Responsibility:** Retrieve from the Pinecone collection holding semantically-chunked docs, forum threads, and Stack Overflow Q&A.
**Why it exists:** Separated from the structured retriever because prose chunking strategy, embedding behavior, and relevance signals differ fundamentally from config chunking. Merging these into one collection is the single most common mistake that would flatten this project back into "generic PDF chatbot."
**Inputs:** query + domain filter.
**Outputs:** top-k prose chunks with source metadata (for attribution).

### 4. Answer Generator
**Responsibility:** Given the user question and retrieved context (from one or both retrievers), produce a grounded natural-language answer.
**Why it exists:** Handles the plain Q&A case. Must explicitly say "I don't have enough context to answer that" when retrieval returns nothing relevant, rather than hallucinating — this behavior is itself an eval test case (see INSTRUCTIONS.md AC 10 equivalent).
**Inputs:** query, retrieved context (structured and/or prose), router output.
**Outputs:** natural-language answer + citations to source chunks.

### 5. Fix Agent (generate → validate → reflect loop)
**Responsibility:** For fix-generation requests, produce a corrected YAML (GitHub Actions) or JSON (n8n workflow) snippet grounded in retrieved structured context, then validate it, then retry with reflection if validation fails, up to a capped number of attempts.
**Why it exists:** This is the agentic differentiator — the thing that separates this from a prose-only RAG chatbot. A fix that hasn't been mechanically validated is not a fix.
**Loop steps:**
1. **Generate:** produce a corrected config snippet, constrained to valid YAML/JSON structure (schema-constrained decoding or a Pydantic model), grounded in retrieved structured context plus any relevant prose context (e.g., a forum thread describing the same error).
2. **Validate:** actually parse and lint the output — `actionlint` for GitHub Actions YAML, n8n's workflow JSON schema for n8n configs. This is a real subprocess/library call, not an LLM self-report of validity.
3. **Reflect:** if validation fails, feed the validator's error output back into the generator as additional context and retry.
4. **Cap:** after N attempts (e.g., 3), stop and return the best attempt labeled explicitly as **unverified** if it still fails validation. Never silently return an unvalidated fix as if it were confirmed correct.
**Inputs:** query, retrieved structured + prose context, router output.
**Outputs:** `{fix_snippet, validated: bool, attempts: int, validator_errors: list}`.

### 6. Eval Agent (offline, not in the live request path)
**Responsibility:** Run the 50–100 question stratified eval set against the live pipeline on demand (CI or manual trigger), scoring retrieval (context precision/recall) and generation (faithfulness/answer relevancy) separately via RAGAS/DeepEval, plus a parse-pass rate for fix-generation items.
**Why it exists:** This is the resume-critical deliverable. It must run against the actual deployed retrieval and generation modules, not a separate reimplementation, so eval numbers are honest.
**Inputs:** the eval question set (with gold answers / gold corrected configs).
**Outputs:** per-question scores + aggregate scores, stored and rendered in the frontend eval dashboard.

## Interaction diagram (textual)

```
User query
   -> Query Router
        -> [factual lookup / error diagnosis] -> Prose Retriever (+ Structured Retriever if relevant)
                -> Answer Generator -> response with citations
        -> [fix-generation request] -> Structured Retriever (+ Prose Retriever for context)
                -> Fix Agent (generate -> validate -> reflect loop, capped)
                        -> validated fix, or best-effort labeled "unverified"
```

The Eval Agent runs separately/offline against this same pipeline and feeds the dashboard.

## Hard rules for whoever (human or Claude) implements these agents

- Never let the Fix Agent return a config snippet without attempting validation at least once.
- Never merge the structured and prose retrievers into a single collection "for simplicity" — this destroys the technical story of the project.
- Never have the Answer Generator or Fix Agent fabricate a citation or source it didn't actually retrieve.
- Keep each agent's inputs/outputs as plain, testable data structures so the Eval Agent can probe each stage independently.
