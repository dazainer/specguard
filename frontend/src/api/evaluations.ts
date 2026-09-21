export interface MutationSummary {
  generated: number; killed: number; survived: number; timed_out: number;
  invalid: number; errors: number; suspicious: number; denominator: number; score: number | null;
}
export interface Suite {
  collection_status: string; collected_tests: number | null; accepted_tests: number | null;
  rejected_tests: number | null; baseline_pass_rate: number | null; mutation: MutationSummary | null;
}
export interface Report {
  status: string; native: Suite; generated: Suite; failure_reason: string | null;
  generation_config: { provider: string; model: string; prompt_version: string };
  provenance: { repository_commit: string; runner_image_digest: string };
}
export interface EvaluationRun {
  id: string; target_id: string; status: string; created_at: number; started_at: number | null;
  finished_at: number | null; failure_reason: string | null; cancel_requested: number;
  report: Report | null; pruned: number; queue_seconds: number;
  options: {strategy: string; baseline_only: boolean};
  events?: {stage: string; at: number}[];
  timings?: Record<string, number>;
}
export interface Target { id: string; name: string; subject: string; manifest: { repository: { commit: string } } }
export interface Artifact { path: string; sha256: string; size_bytes: number; accepted: number }
export interface Mutant { id: string; status: string; source_file: string; line: number; operator: string; diff: string;
  duration_seconds: number; killing_test: string | null; manual_review: string;
  execution: { stdout: string; stderr: string; output_truncated: boolean } | null;
}
export interface Log { stage: string; status: string; stdout: string; stderr: string; output_truncated: boolean }

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api/evaluations' + path, body === undefined ? undefined : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'The request could not be accepted.');
  return data;
}
export const evaluations = {
  catalog: () => request<{subject: string; commit: string; provider: string}[]>('/catalog'),
  targets: () => request<Target[]>('/targets'),
  createTarget: (name: string, subject: string) => request<Target>('/targets', {name, subject}),
  runs: () => request<EvaluationRun[]>('/runs'),
  run: (id: string) => request<EvaluationRun>(`/runs/${id}`),
  start: (target_id: string, strategy: string, baseline_only: boolean, idempotency_key: string) =>
    request<EvaluationRun>('/runs', {target_id, strategy, baseline_only, idempotency_key}),
  cancel: (id: string) => request<EvaluationRun>(`/runs/${id}/cancel`, {}),
  artifacts: (id: string) => request<Artifact[]>(`/runs/${id}/artifacts`),
  artifact: (id: string, path: string) => request<{content: string}>(`/runs/${id}/artifact?path=${encodeURIComponent(path)}`),
  logs: (id: string) => request<Log[]>(`/runs/${id}/logs`),
  mutants: (id: string, suite: string, status: string, offset: number) => request<{items: Mutant[]; total: number}>(
    `/runs/${id}/mutants?suite=${suite}&offset=${offset}&limit=20${status ? '&status=' + status : ''}`),
};
