const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  status: number | null;
  constructor(message: string, status: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function extractErrorMessage(res: Response): Promise<string> {
  const text = await res.text();
  try {
    const data = JSON.parse(text);
    if (typeof data?.detail === "string") return data.detail;
  } catch {
    // body wasn't JSON — fall through to status-based messaging
  }
  if (res.status === 503) {
    return "The backend is temporarily unavailable — it may be a free-tier server waking up from idle, or the AI provider hitting a rate limit. Try again in a few seconds.";
  }
  if (res.status === 429) {
    return "Rate limited by the free-tier AI provider. Please wait a moment and try again.";
  }
  return text.trim() || `Request failed with status ${res.status}.`;
}

async function fetchJson<T>(
  url: string,
  init: RequestInit = {},
  timeoutMs = 45000
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let res: Response;
  try {
    res = await fetch(url, { ...init, signal: controller.signal });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      throw new ApiError(
        "The request timed out. If this is the first request in a while, the free-tier server may still be waking up from idle — try again."
      );
    }
    throw new ApiError(
      "Couldn't reach the backend. If this is the first request in a while, the free-tier server may still be waking up from idle — wait a few seconds and try again.",
      null
    );
  } finally {
    clearTimeout(timer);
  }
  if (!res.ok) {
    throw new ApiError(await extractErrorMessage(res), res.status);
  }
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError("The backend returned a response that couldn't be read. Try again.");
  }
}

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
  domain: "n8n" | "github_actions" | "api_errors" | "agentic_ai";
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
  return fetchJson<QueryResponse>(`${API_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query }),
  });
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
  return fetchJson<AggregateEval>(`${API_URL}/eval/aggregate`, { cache: "no-store" }, 20000);
}

export async function fetchPerQuestionEval(): Promise<PerQuestionEval[]> {
  return fetchJson<PerQuestionEval[]>(`${API_URL}/eval/questions`, { cache: "no-store" }, 20000);
}
