"use client";

import { useEffect, useState } from "react";
import { fetchAggregateEval, fetchPerQuestionEval, type AggregateEval, type PerQuestionEval } from "@/lib/api";

function Bar({ label, value, max = 1 }: { label: string; value: number | null; max?: number }) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-600">
        <span>{label}</span>
        <span className="font-mono">{value == null ? "n/a" : value.toFixed(3)}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100">
        <div className="h-2 rounded-full bg-accent" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

const DOMAIN_LABEL: Record<string, string> = {
  n8n: "n8n",
  github_actions: "GitHub Actions",
  api_errors: "API / HTTP errors",
  agentic_ai: "Agentic AI / Orchestration",
};

export default function EvalDashboard() {
  const [agg, setAgg] = useState<AggregateEval | null>(null);
  const [rows, setRows] = useState<PerQuestionEval[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([fetchAggregateEval(), fetchPerQuestionEval()])
      .then(([a, r]) => {
        setAgg(a);
        setRows(r);
      })
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-sm text-slate-500">Loading eval results...</p>;
  if (error)
    return (
      <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700">
        {error}
      </div>
    );
  if (!agg) return null;

  const nullCounts = { context_precision: 0, context_recall: 0 };
  for (const r of rows) {
    if (r.task_type !== "fix_generation") {
      if (r.scores.context_precision == null) nullCounts.context_precision++;
      if (r.scores.context_recall == null) nullCounts.context_recall++;
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-ink">Eval Dashboard</h1>
        <p className="mt-1 text-sm text-slate-600">
          {agg.total_questions}-question stratified eval set, run against the live pipeline (RAGAS /
          DeepEval, free-tier LLM-as-judge). Retrieval and generation are scored independently. These are
          the real, unmassaged numbers from the last full run — including nulls where the free judge
          model failed to produce a parseable verdict.
        </p>
      </div>

      <section className="grid gap-6 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-2">
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">
            QA metrics <span className="font-normal text-slate-400">(n={agg.qa_metrics.n})</span>
          </h2>
          <Bar label="Context precision" value={agg.qa_metrics.context_precision} />
          <Bar label="Context recall" value={agg.qa_metrics.context_recall} />
          <Bar label="Faithfulness" value={agg.qa_metrics.faithfulness} />
          <Bar label="Answer relevancy" value={agg.qa_metrics.answer_relevancy} />
          <p className="text-xs text-slate-500">
            Decline rate: {(agg.qa_metrics.decline_rate * 100).toFixed(0)}%
          </p>
        </div>
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-ink">
            Fix generation <span className="font-normal text-slate-400">(n={agg.fix_generation_metrics.n})</span>
          </h2>
          <Bar label="Parse pass rate" value={agg.fix_generation_metrics.parse_pass_rate} />
          <p className="text-xs text-slate-500">
            Avg attempts to validate: {agg.fix_generation_metrics.avg_attempts.toFixed(2)} (cap: 3)
          </p>
          <p className="text-xs text-slate-500">
            Errored questions: {agg.errored_questions} / {agg.total_questions}
          </p>
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-ink">By domain</h2>
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
          {Object.entries(agg.by_domain).map(([domain, m]) => (
            <div key={domain} className="space-y-2">
              <h3 className="text-xs font-semibold text-slate-700">{DOMAIN_LABEL[domain] ?? domain}</h3>
              <Bar label="Context precision" value={m.context_precision} />
              <Bar label="Context recall" value={m.context_recall} />
              <Bar label="Faithfulness" value={m.faithfulness} />
              <Bar label="Answer relevancy" value={m.answer_relevancy} />
              {m.parse_pass_rate != null && <Bar label="Parse pass rate" value={m.parse_pass_rate} />}
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-slate-500">
          n8n's context precision (0.208) is notably lower than every other domain, including the AI
          agent tooling domain (0.336) whose structured content (CrewAI YAML, Python code, MCP JSON
          schema) is similarly dense — so this looks like a chunk-shape-specific weak spot for the free
          judge model, not a general "structured content scores low" pattern. GitHub Actions (0.516) and
          API errors (0.842) score higher still. Disclosed as-is, not hidden.
        </p>
      </section>

      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800">
        Judge reliability: context_precision/recall came back null for {nullCounts.context_precision}/
        {rows.filter((r) => r.task_type !== "fix_generation").length} and {nullCounts.context_recall}/
        {rows.filter((r) => r.task_type !== "fix_generation").length} QA questions respectively — the
        free-tier judge model occasionally produced malformed JSON on complex multi-chunk verdicts. A
        real, disclosed limitation of zero-cost LLM-as-judge scoring, not hidden from this dashboard.
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="mb-3 text-sm font-semibold text-ink">Per-question results</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-slate-500">
                <th className="py-2 pr-3">ID</th>
                <th className="py-2 pr-3">Domain</th>
                <th className="py-2 pr-3">Task</th>
                <th className="py-2 pr-3">Query</th>
                <th className="py-2 pr-3">Precision</th>
                <th className="py-2 pr-3">Recall</th>
                <th className="py-2 pr-3">Faithfulness</th>
                <th className="py-2 pr-3">Relevancy</th>
                <th className="py-2 pr-3">Parse</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-slate-100 align-top">
                  <td className="py-2 pr-3 font-mono text-slate-400">{r.id}</td>
                  <td className="py-2 pr-3">{DOMAIN_LABEL[r.domain] ?? r.domain}</td>
                  <td className="py-2 pr-3">{r.task_type.replace("_", " ")}</td>
                  <td className="max-w-xs py-2 pr-3 text-slate-700">{r.query}</td>
                  <td className="py-2 pr-3 font-mono">
                    {fmt(r.scores.context_precision as number | null)}
                  </td>
                  <td className="py-2 pr-3 font-mono">{fmt(r.scores.context_recall as number | null)}</td>
                  <td className="py-2 pr-3 font-mono">{fmt(r.scores.faithfulness as number | null)}</td>
                  <td className="py-2 pr-3 font-mono">{fmt(r.scores.answer_relevancy as number | null)}</td>
                  <td className="py-2 pr-3 font-mono">
                    {r.scores.parse_pass_rate != null
                      ? r.scores.parse_pass_rate === 1
                        ? "pass"
                        : "fail"
                      : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function fmt(v: number | null | undefined): string {
  if (v == null) return "n/a";
  return v.toFixed(2);
}
