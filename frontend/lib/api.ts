const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Citation = {
  index: number;
  source_url: string;
  title: string;
  artifact_type: string;
};

export type Chunk = {
  id: string;
  score: number;
  text: string;
  artifact_type: string;
  title: string;
  source_url: string;
};

export type RouterResult = {
  domain: "n8n" | "github_actions" | "api_errors";
  task_type: "factual_lookup" | "error_diagnosis" | "fix_generation";
  needs_fix_generation: boolean;
};

export type QueryResponse = {
  router: RouterResult;
  mode: "answer" | "fix";
  answer: string | null;
  declined: boolean;
  citations: Citation[];
  fix_snippet: string | null;
  validated: boolean | null;
  attempts: number | null;
  validator_errors: string[];
  structured_chunks: Chunk[];
  prose_chunks: Chunk[];
};

export async function runQuery(query: string): Promise<QueryResponse> {
  const res = await fetch(`${API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Query failed (${res.status}): ${detail}`);
  }
  return res.json();
}

export type AggregateEval = {
  total_questions: number;
  errored_questions: number;
  qa_metrics: {
    n: number;
    context_precision: number;
    context_recall: number;
    faithfulness: number;
    answer_relevancy: number;
    decline_rate: number;
  };
  fix_generation_metrics: {
    n: number;
    parse_pass_rate: number;
    avg_attempts: number;
  };
  by_domain: Record<
    string,
    {
      context_precision: number | null;
      context_recall: number | null;
      faithfulness: number | null;
      answer_relevancy: number | null;
      parse_pass_rate: number | null;
    }
  >;
};

export type PerQuestionEval = {
  id: string;
  domain: string;
  task_type: string;
  elapsed_sec: number;
  query: string | null;
  scores: Record<string, number | boolean | string[] | null>;
};

export async function fetchAggregateEval(): Promise<AggregateEval> {
  const res = await fetch(`${API_URL}/eval/aggregate`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load eval aggregate (${res.status})`);
  return res.json();
}

export async function fetchPerQuestionEval(): Promise<PerQuestionEval[]> {
  const res = await fetch(`${API_URL}/eval/questions`, { cache: "no-store" });
  if (!res.ok) throw new Error(`Failed to load eval questions (${res.status})`);
  return res.json();
}
