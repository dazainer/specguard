import type { EvaluationRun, MutationSummary, Suite } from '../api/evaluations';

export const TERMINAL = new Set(['completed', 'failed', 'cancelled']);

/** Mutation outcome categories, in the order the methodology lists them. They partition the inventory. */
export const OUTCOMES = ['killed', 'survived', 'timed_out', 'invalid', 'errors', 'suspicious'] as const;
export type Outcome = typeof OUTCOMES[number];

export const OUTCOME_LABEL: Record<Outcome, string> = {
  killed: 'Killed', survived: 'Survived', timed_out: 'Timed out',
  invalid: 'Invalid', errors: 'Error', suspicious: 'Suspicious',
};

export const OUTCOME_HELP: Record<Outcome, string> = {
  killed: 'A test failed against the mutant. Counts toward the score.',
  survived: 'Every test passed against the mutant. Counts toward the score.',
  timed_out: 'Execution hit the mutation timeout. Excluded from the score.',
  invalid: 'mutmut produced a variant that could not be run. Excluded from the score.',
  errors: 'Collection or infrastructure failure. Excluded from the score.',
  suspicious: 'Unexpected test counts or output. Excluded from the score.',
};

/** Worker lifecycle, in execution order. Collection and baseline repeat once per suite. */
export const STAGES = ['queued', 'preparing', 'generating', 'collecting', 'baseline_running', 'mutating'] as const;
export const STAGE_LABEL: Record<string, string> = {
  queued: 'Queued', preparing: 'Preparing', generating: 'Generating', collecting: 'Collecting',
  baseline_running: 'Baseline', mutating: 'Mutating', completed: 'Completed', failed: 'Failed', cancelled: 'Cancelled',
};

export const label = (value: string) => value.replace(/_/g, ' ');
export const errorText = (error: unknown) => error instanceof Error ? error.message : 'Request failed';
export const shortId = (id: string) => id.slice(0, 8);
export const shortHash = (hash: string | null | undefined, size = 12) => {
  if (!hash) return '—';
  const [prefix, value] = hash.includes(':') ? hash.split(':', 2) : ['', hash];
  return (prefix ? prefix + ':' : '') + value.slice(0, size);
};

export function percent(value: number | null | undefined, digits = 1) {
  return value == null ? '—' : `${(value * 100).toFixed(digits)}%`;
}

export function seconds(value: number | null | undefined) {
  if (value == null) return '—';
  if (value < 1) return `${Math.round(value * 1000)} ms`;
  if (value < 90) return `${value.toFixed(1)} s`;
  return `${Math.floor(value / 60)} min ${Math.round(value % 60)} s`;
}

export function bytes(value: number) {
  return value < 1024 ? `${value} B` : `${(value / 1024).toFixed(1)} KiB`;
}

export function timestamp(epochSeconds: number | null | undefined) {
  return epochSeconds == null ? '—' : new Date(epochSeconds * 1000).toLocaleString();
}

/** Score text always carries its denominator; a zero denominator is unmeasured, never 0%. */
export function scoreText(m: MutationSummary | null | undefined) {
  if (!m) return 'Not measured';
  if (m.score == null) return `Unmeasured (0 scorable of ${m.generated})`;
  return `${percent(m.score)} · ${m.killed}/${m.denominator}`;
}

export function excluded(m: MutationSummary) {
  return m.timed_out + m.invalid + m.errors + m.suspicious;
}

export type Eligibility = { state: 'eligible' | 'rejected' | 'pending' | 'not_run'; reason: string };

/** Mirrors the report's mutation gate so the UI can explain why a suite was or was not scored. */
export function eligibility(suite: Suite, required: number, runTerminal: boolean, runStopped = false): Eligibility {
  if (suite.collection_status === 'not_run' && !suite.baseline_runs.length) {
    if (!runTerminal) return { state: 'pending', reason: 'Waiting to collect' };
    // A stopped run's report may omit steps that its logs show; do not claim they never ran.
    return { state: 'not_run', reason: runStopped ? 'Not recorded before the run stopped' : 'Not executed in this run' };
  }
  if (suite.collection_status === 'failed') return { state: 'rejected', reason: 'Collection failed' };
  if (suite.collected_tests === 0) return { state: 'rejected', reason: 'Empty suite' };
  const failed = suite.baseline_runs.find(run => run.status !== 'passed');
  if (failed) return { state: 'rejected', reason: `Baseline ${label(failed.status)}` };
  const unstable = suite.baseline_runs.some(run => run.collected_tests !== suite.collected_tests || run.passed_tests !== suite.collected_tests);
  if (unstable) return { state: 'rejected', reason: 'Unstable baseline counts' };
  if (suite.baseline_runs.length < required) {
    return runTerminal
      ? { state: 'rejected', reason: `${suite.baseline_runs.length} of ${required} baseline repeats` }
      : { state: 'pending', reason: `Baseline ${suite.baseline_runs.length} of ${required}` };
  }
  return { state: 'eligible', reason: `Collected, ${suite.baseline_runs.length}/${required} baselines passed` };
}

/** "generated-baseline-2" → {suite: 'generated', kind: 'Baseline', repeat: 2}. */
export function parseLogStage(stage: string) {
  const match = /^(native|generated)-(collection|baseline)(?:-(\d+))?$/.exec(stage);
  if (!match) return { suite: null, kind: label(stage), repeat: null };
  return { suite: match[1] as 'native' | 'generated', kind: match[2] === 'collection' ? 'Collection' : 'Baseline', repeat: match[3] ? Number(match[3]) : null };
}

export function scopeText(run: EvaluationRun) {
  return run.options.baseline_only ? 'Baseline only' : 'Mutation comparison';
}

export const STRATEGY_LABEL: Record<string, string> = { 'contract-v1': 'Contract coverage', 'boundary-v1': 'Boundary coverage' };
