import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { EvaluationRun, Mutant, Report } from '../../api/evaluations';
import runJson from '../../test/fixtures/shipping-run.json';
import nativeJson from '../../test/fixtures/shipping-mutants-native.json';
import generatedJson from '../../test/fixtures/shipping-mutants-generated.json';
import { InventoryStrip } from './InventoryStrip';
import { StageTrack } from './StageTrack';
import { SuiteComparison } from './SuiteComparison';
import { MutantExplorer } from './MutantExplorer';
import { evaluations } from '../../api/evaluations';
import { ArtifactViewer } from './RunEvidence';

const run = runJson as unknown as EvaluationRun;
const report = run.report as Report;

describe('artifact request fencing', () => {
  it('ignores content that arrives after retention removes the artifacts', async () => {
    let resolve!: (value: { content: string }) => void;
    vi.spyOn(evaluations, 'artifact').mockReturnValue(new Promise(done => { resolve = done; }));
    const artifacts = [{ path: 'test_example.py', accepted: 1, size_bytes: 10, sha256: 'a'.repeat(64) }];
    const view = render(<ArtifactViewer runId="one" artifacts={artifacts} pruned={false} />);
    await userEvent.click(screen.getByRole('button', { name: 'test_example.py' }));
    view.rerender(<ArtifactViewer runId="one" artifacts={[]} pruned />);
    await act(async () => resolve({ content: 'stale source' }));
    view.rerender(<ArtifactViewer runId="two" artifacts={artifacts} pruned={false} />);
    expect(screen.queryByText('stale source')).not.toBeInTheDocument();
    vi.restoreAllMocks();
  });
});

describe('InventoryStrip', () => {
  it('describes every category, including zero counts, for assistive technology', () => {
    render(<InventoryStrip mutation={report.generated.mutation!} name="Generated fixture" />);
    const strip = screen.getByRole('img');
    expect(strip).toHaveAccessibleName('Generated fixture: 13 mutants — 3 killed, 10 survived, 0 timed out, 0 invalid, 0 error, 0 suspicious');
  });
});

describe('SuiteComparison', () => {
  it('shows every outcome category for both suites and marks excluded ones', () => {
    render(<SuiteComparison report={report} terminal timings={run.timings ?? {}} />);
    const table = screen.getByRole('table', { name: /native versus generated/i });
    for (const name of ['Killed', 'Survived', 'Timed out', 'Invalid', 'Error', 'Suspicious']) {
      expect(within(table).getByRole('rowheader', { name: new RegExp(`^${name}`) })).toBeInTheDocument();
    }
    expect(within(table).getAllByText('excluded')).toHaveLength(4);
    const score = within(table).getByRole('row', { name: /mutation score/i });
    expect(score).toHaveTextContent('92.3% · 12/13');
    expect(score).toHaveTextContent('23.1% · 3/13');
  });
  it('states that both suites used the same inventory and configuration', () => {
    render(<SuiteComparison report={report} terminal timings={{}} />);
    expect(screen.getByText(/same mutant inventory/i)).toBeInTheDocument();
    expect(screen.getAllByText('Eligible for mutation')).toHaveLength(2);
  });
  it('explains a rejected suite rather than hiding it', () => {
    const rejected: Report = { ...report, generated: { ...report.generated, mutation: null, baseline_pass_rate: 0.5,
      baseline_runs: [report.generated.baseline_runs[0], { ...report.generated.baseline_runs[1], status: 'failed', passed_tests: 2, failed_tests: 1 }] } };
    render(<SuiteComparison report={rejected} terminal timings={{}} />);
    expect(screen.getByText('Rejected')).toBeInTheDocument();
    expect(screen.getByText('Baseline failed')).toBeInTheDocument();
  });
});

describe('StageTrack', () => {
  it('marks the current stage for an active run', () => {
    render(<StageTrack run={{ ...run, status: 'mutating', finished_at: null, events: run.events!.filter(e => e.stage !== 'completed') }} />);
    expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Mutating');
  });
  it('shows mutation as skipped for baseline-only runs and where a failed run stopped', () => {
    const events = run.events!.filter(e => !['mutating', 'completed'].includes(e.stage));
    render(<StageTrack run={{ ...run, status: 'failed', options: { ...run.options, baseline_only: true }, events }} />);
    expect(screen.getByText('Skipped · baseline only')).toBeInTheDocument();
    expect(screen.getByText(/Stopped here/)).toBeInTheDocument();
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });
});

describe('MutantExplorer', () => {
  beforeEach(() => {
    vi.spyOn(evaluations, 'allMutants').mockImplementation(async (_id, suite) =>
      (suite === 'native' ? nativeJson : generatedJson).items as unknown as Mutant[]);
  });

  it('joins suites by mutant and filters to disagreements', async () => {
    const user = userEvent.setup();
    render(<MutantExplorer runId={run.id} available emptyReason="" />);
    expect(await screen.findByText(/Showing 1–13 of 13 generated fixture mutants/)).toBeInTheDocument();
    const survived = screen.getByRole('radio', { name: /Survived/ });
    expect(survived.closest('label')).toHaveTextContent('10');

    await user.click(screen.getByRole('checkbox', { name: /only where suites disagree/i }));
    // Real data: native kills 12, generated kills 3; every generated kill is also a native kill.
    expect(screen.getByText(/of 9 generated fixture mutants/)).toBeInTheDocument();
    for (const item of screen.getAllByRole('listitem')) {
      expect(item).toHaveTextContent(/Survived.*Native:.*Killed/);
    }
  });

  it('is keyboard operable and switches the viewed suite', async () => {
    const user = userEvent.setup();
    render(<MutantExplorer runId={run.id} available emptyReason="" />);
    await screen.findByText(/Showing 1–13/);
    screen.getByRole('radio', { name: 'Native' }).focus();
    await user.keyboard(' ');
    expect(screen.getByText(/13 native mutants/)).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: /Killed/ }).closest('label')).toHaveTextContent('12');
  });

  it('explains why mutants are unavailable', () => {
    render(<MutantExplorer runId={run.id} available={false} emptyReason="This was a baseline check." />);
    expect(screen.getByText('This was a baseline check.')).toBeInTheDocument();
  });
});
