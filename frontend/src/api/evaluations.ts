// Types mirror backend/app/schemas/evaluation.py and routes/evaluations.py. Read-only; no contract changes.
export interface MutationSummary {
  inventory_sha256: string; configuration_sha256: string;
  generated: number; killed: number; survived: number; timed_out: number;
  invalid: number; errors: number; suspicious: number; denominator: number; score: number | null;
  duration_seconds: number;
}
export interface BaselineRun {
  status: 'passed' | 'failed' | 'collection_error' | 'timeout' | 'resource_limit' | 'infrastructure_error';
  collected_tests: number | null; passed_tests: number | null; failed_tests: number | null; duration_seconds: number;
}
export interface Suite {
  collection_status: 'not_run' | 'passed' | 'failed'; collected_tests: number | null; accepted_tests: number | null;
  rejected_tests: number | null; baseline_runs: BaselineRun[]; baseline_pass_rate: number | null;
  repeat_duration_variance_seconds2: number | null; mutation: MutationSummary | null;
}
export interface Report {
  status: string; native: Suite; generated: Suite; failure_reason: string | null;
  context_mode: 'spec_only' | 'spec_plus_code'; required_baseline_repeats: number;
  generation_config: { provider: string; model: string; prompt_version: string; temperature: number; seed: number | null };
  generation: { attempts: number; successful: boolean | null; duration_seconds: number | null;
    input_tokens: number | null; output_tokens: number | null; estimated_cost_usd: number | null };
  provenance: { repository_commit: string; runner_image_digest: string | null; manifest_sha256: string;
    specification_sha256: string; context_sha256: string; dependency_lock_sha256: string;
    python_version: string; tool_versions: Record<string, string> };
  artifacts: { path: string; sha256: string; size_bytes: number }[];
}
export interface EvaluationRun {
  id: string; target_id: string; status: string; created_at: number; started_at: number | null;
  finished_at: number | null; failure_reason: string | null; cancel_requested: number;
  report: Report | null; pruned: number; queue_seconds: number; max_seconds: number; image: string;
  options: {strategy: string; baseline_only: boolean};
  events?: {stage: string; at: number}[];
  timings?: Record<string, number> | null;
}
export interface Manifest {
  repository: { commit: string; bundle: string | null; url: string | null };
  specification: { path: string };
  context: { mode: string; interface_path: string; source_files: string[] };
  tests: { native_paths: string[]; generated_path: string; repeat_count: number; timeout_seconds: number };
  mutation: { source_paths: string[]; excluded_paths: string[]; timeout_seconds: number };
  limits: { memory_mb: number; cpus: number; pids: number; output_kb: number; scratch_mb: number; file_size_mb: number };
}
export interface Target { id: string; name: string; subject: string; created_at?: number; manifest: Manifest }
export interface CatalogEntry { subject: string; commit: string; provider: string }
export interface Artifact { path: string; sha256: string; size_bytes: number; accepted: number }
export interface Execution { status: string; exit_code: number | null; duration_seconds: number; stdout: string; stderr: string;
  output_truncated: boolean; oom_killed?: boolean; error_message?: string | null }
export interface Mutant { id: string; status: string; source_file: string; line: number; operator: string; diff: string;
  duration_seconds: number; killing_test: string | null; manual_review: string; review_notes?: string | null;
  execution: Execution | null;
}
export interface Log { stage: string; status: string; stdout: string; stderr: string; output_truncated: boolean }

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api/evaluations' + path, body === undefined ? undefined : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);
  if (data === null) throw new Error(`The evaluation API did not return JSON (HTTP ${response.status}). Check that the API is running.`);
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `The request could not be accepted (HTTP ${response.status}).`);
  return data;
}
export const evaluations = {
  catalog: () => request<CatalogEntry[]>('/catalog'),
  targets: () => request<Target[]>('/targets'),
  target: (id: string) => request<Target>(`/targets/${id}`),
  createTarget: (name: string, subject: string) => request<Target>('/targets', {name, subject}),
  runs: () => request<EvaluationRun[]>('/runs'),
  run: (id: string) => request<EvaluationRun>(`/runs/${id}`),
  start: (target_id: string, strategy: string, baseline_only: boolean, idempotency_key: string) =>
    request<EvaluationRun>('/runs', {target_id, strategy, baseline_only, idempotency_key}),
  cancel: (id: string) => request<EvaluationRun>(`/runs/${id}/cancel`, {}),
  artifacts: (id: string) => request<Artifact[]>(`/runs/${id}/artifacts`),
  artifact: (id: string, path: string) => request<{content: string}>(`/runs/${id}/artifact?path=${encodeURIComponent(path)}`),
  logs: (id: string) => request<Log[]>(`/runs/${id}/logs`),
  mutants: (id: string, suite: string, status: string, offset: number, limit = 20) => request<{items: Mutant[]; total: number}>(
    `/runs/${id}/mutants?suite=${suite}&offset=${offset}&limit=${limit}${status ? '&status=' + status : ''}`),
  /** Loads a suite's whole indexed inventory (bounded at 1000 mutants by the evaluator) in API-sized pages. */
  allMutants: async (id: string, suite: 'native' | 'generated') => {
    const items: Mutant[] = [];
    for (let offset = 0; offset < 1000; offset += 100) {
      const page = await evaluations.mutants(id, suite, '', offset, 100);
      items.push(...page.items);
      if (items.length >= page.total || !page.items.length) break;
    }
    return items;
  },
  ready: async () => (await fetch('/api/evaluations/ready')).ok,
  exportUrl: (id: string, format: 'json' | 'md' | 'csv') => `/api/evaluations/runs/${id}/export?format=${format}`,
};
