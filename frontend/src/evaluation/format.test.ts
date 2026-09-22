import { describe, expect, it } from 'vitest';
import type { MutationSummary, Suite } from '../api/evaluations';
import run from '../test/fixtures/shipping-run.json';
import { eligibility, excluded, parseLogStage, scoreText, seconds } from './format';

const summary = (overrides: Partial<MutationSummary>): MutationSummary => ({
  inventory_sha256: 'a'.repeat(64), configuration_sha256: 'b'.repeat(64), generated: 0, killed: 0, survived: 0,
  timed_out: 0, invalid: 0, errors: 0, suspicious: 0, denominator: 0, score: null, duration_seconds: 1, ...overrides,
});
const suite = (overrides: Partial<Suite>): Suite => ({
  collection_status: 'passed', collected_tests: 3, accepted_tests: 3, rejected_tests: 0, baseline_pass_rate: 1,
  repeat_duration_variance_seconds2: 0, mutation: null,
  baseline_runs: [1, 2].map(() => ({ status: 'passed' as const, collected_tests: 3, passed_tests: 3, failed_tests: 0, duration_seconds: 0.5 })),
  ...overrides,
});

describe('scoreText', () => {
  it('always shows the denominator next to the score (real shipping run)', () => {
    expect(scoreText(run.report!.generated.mutation as MutationSummary)).toBe('23.1% · 3/13');
    expect(scoreText(run.report!.native.mutation as MutationSummary)).toBe('92.3% · 12/13');
  });
  it('never reports 0% when nothing was scorable', () => {
    expect(scoreText(summary({ generated: 4, timed_out: 3, invalid: 1 }))).toBe('Unmeasured (0 scorable of 4)');
  });
  it('distinguishes an absent mutation stage', () => {
    expect(scoreText(null)).toBe('Not measured');
  });
  it('counts every excluded category', () => {
    expect(excluded(summary({ timed_out: 1, invalid: 2, errors: 3, suspicious: 4 }))).toBe(10);
  });
});

describe('eligibility mirrors the report mutation gate', () => {
  it('accepts a stable passing suite', () => {
    expect(eligibility(suite({}), 2, true).state).toBe('eligible');
  });
  it('rejects failed collection, empty suites and failing repeats', () => {
    expect(eligibility(suite({ collection_status: 'failed', baseline_runs: [] }), 2, true)).toEqual({ state: 'rejected', reason: 'Collection failed' });
    expect(eligibility(suite({ collected_tests: 0 }), 2, true).reason).toBe('Empty suite');
    const failing = suite({ baseline_runs: [{ status: 'timeout', collected_tests: 3, passed_tests: 0, failed_tests: 0, duration_seconds: 30 }] });
    expect(eligibility(failing, 2, true)).toEqual({ state: 'rejected', reason: 'Baseline timeout' });
  });
  it('rejects unstable counts even when every repeat passed', () => {
    const unstable = suite({ baseline_runs: [
      { status: 'passed', collected_tests: 3, passed_tests: 3, failed_tests: 0, duration_seconds: 1 },
      { status: 'passed', collected_tests: 2, passed_tests: 2, failed_tests: 0, duration_seconds: 1 }] });
    expect(eligibility(unstable, 2, true).reason).toBe('Unstable baseline counts');
  });
  it('treats missing repeats as pending while running and rejected once terminal', () => {
    const partial = suite({ baseline_runs: suite({}).baseline_runs.slice(0, 1) });
    expect(eligibility(partial, 2, false).state).toBe('pending');
    expect(eligibility(partial, 2, true)).toEqual({ state: 'rejected', reason: '1 of 2 baseline repeats' });
  });
  it('reports a suite that never ran', () => {
    const unrun = suite({ collection_status: 'not_run', baseline_runs: [] });
    expect(eligibility(unrun, 2, true).state).toBe('not_run');
    expect(eligibility(unrun, 2, false).state).toBe('pending');
  });
  it('does not claim a stopped run never executed a suite its report omits', () => {
    const unrun = suite({ collection_status: 'not_run', baseline_runs: [] });
    expect(eligibility(unrun, 2, true, true).reason).toBe('Not recorded before the run stopped');
  });
});

describe('formatting', () => {
  it('parses log stage names from the logs endpoint', () => {
    expect(parseLogStage('generated-baseline-2')).toEqual({ suite: 'generated', kind: 'Baseline', repeat: 2 });
    expect(parseLogStage('native-collection')).toEqual({ suite: 'native', kind: 'Collection', repeat: null });
    expect(parseLogStage('mystery_stage')).toEqual({ suite: null, kind: 'mystery stage', repeat: null });
  });
  it('formats durations', () => {
    expect(seconds(0.0022)).toBe('2 ms');
    expect(seconds(23.8)).toBe('23.8 s');
    expect(seconds(125)).toBe('2 min 5 s');
    expect(seconds(null)).toBe('—');
  });
});
