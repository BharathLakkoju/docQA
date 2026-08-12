"use client";

import { useState } from "react";
import { runQuery, ApiError, type QueryResponse } from "@/lib/api";

const EXAMPLES = [
  "What does the n8n HTTP Request node do?",
  "Why is my GitHub Actions job failing with 'npm ERR! code ENOENT'?",
  "Write a GitHub Actions job that checks out code and runs npm test on push",
  "What is MCP (Model Context Protocol)?",
  "Write a CrewAI agent config with a role, goal, and backstory",
  "What is the Hugging Face MCP Server?",
];

const DOMAIN_LABEL: Record<string, string> = {
  n8n: "n8n",
  github_actions: "GitHub Actions",
  api_errors: "API / HTTP errors",
  agentic_ai: "Agentic AI / Orchestration",
};

export default function ChatPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastSubmitted, setLastSubmitted] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResponse | null>(null);

  async function submit(q: string) {
    const trimmed = q.trim();
    if (!trimmed || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    setLastSubmitted(trimmed);
    try {
      const res = await runQuery(trimmed);
      setResult(res);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-ink">Ask about n8n, GitHub Actions, or API errors</h1>
        <p className="mt-1 text-sm text-slate-600">
          Answers are grounded in retrieved context and declined when nothing relevant is found. Fix
          requests are validated (actionlint / n8n schema) before being shown, and never silently
          presented as confirmed if validation fails.
        </p>
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(query);
        }}
        className="flex gap-2"
      >
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. Why does my workflow_dispatch input not show up in the run?"
          className="flex-1 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-accent focus:outline-none"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Thinking..." : "Ask"}
        </button>
      </form>

      <div className="flex flex-wrap gap-2 text-xs">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => {
              setQuery(ex);
              submit(ex);
            }}
            className="rounded-full border border-slate-300 bg-white px-3 py-1 text-slate-600 hover:border-accent hover:text-accent"
          >
            {ex}
          </button>
        ))}
      </div>

      {error && (
        <div className="flex items-start justify-between gap-3 rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
          <span>{error}</span>
          {lastSubmitted && (
            <button
              onClick={() => submit(lastSubmitted)}
              disabled={loading}
              className="shrink-0 rounded-md border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
            >
              Retry
            </button>
          )}
        </div>
      )}

      {result && (
        <div className="space-y-4 rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
              domain: {DOMAIN_LABEL[result.router.domain] ?? result.router.domain}
            </span>
            <span className="rounded-full bg-slate-100 px-2 py-1 text-slate-700">
              task: {result.router.task_type.replace("_", " ")}
            </span>
            {result.router.needs_fix_generation && (
              <span className="rounded-full bg-blue-100 px-2 py-1 text-accent">fix-generation loop</span>
            )}
          </div>

          {result.mode === "answer" && (
            <>
              {result.declined ? (
                <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
                  {result.answer}
                </div>
              ) : (
                <p className="whitespace-pre-wrap text-sm text-ink">{result.answer}</p>
              )}
              {result.citations.length > 0 && (
                <div className="space-y-1 border-t border-slate-100 pt-3">
                  <div className="text-xs font-medium text-slate-500">Sources</div>
                  <ul className="space-y-1 text-xs">
                    {result.citations.map((c) => (
                      <li key={c.index}>
                        <span className="text-slate-400">[{c.index}]</span>{" "}
                        {c.source_url ? (
                          <a href={c.source_url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                            {c.title}
                          </a>
                        ) : (
                          <span>{c.title}</span>
                        )}
                        <span className="text-slate-400"> ({c.artifact_type})</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {result.mode === "fix" && (
            <>
              <div className="flex items-center gap-2 text-sm">
                {result.validated ? (
                  <span className="rounded-full bg-green-100 px-2 py-1 text-xs font-medium text-green-700">
                    validated ({result.attempts} attempt{result.attempts === 1 ? "" : "s"})
                  </span>
                ) : (
                  <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700">
                    unverified — failed validation after {result.attempts} attempts
                  </span>
                )}
              </div>
              <pre className="overflow-x-auto rounded-md bg-slate-900 p-3 text-xs text-slate-100">
                {result.fix_snippet}
              </pre>
              {!result.validated && result.validator_errors.length > 0 && (
                <div className="space-y-1 rounded-md border border-red-200 bg-red-50 p-3 text-xs text-red-700">
                  <div className="font-medium">Validator errors (last attempt):</div>
                  <ul className="list-inside list-disc">
                    {result.validator_errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
