import { CheckCircle2, AlertTriangle } from 'lucide-react';
import type { Report, Suite } from '../../api/evaluations';
import { OUTCOMES, OUTCOME_HELP, OUTCOME_LABEL, eligibility, excluded, percent, scoreText, seconds, shortHash } from '../../evaluation/format';
import { ExecStatus } from './Badges';
import { InventoryStrip } from './InventoryStrip';

const SUITES = [
  { key: 'native', name: 'Native', role: 'Reference tests shipped with the target' },
  { key: 'generated', name: 'Generated fixture', role: 'Handwritten fixture standing in for model output' },
] as const;

function SuitePanel({ name, role, suite, required, terminal, stopped, mutating, timing }: {
  name: string; role: string; suite: Suite; required: number; terminal: boolean; stopped: boolean; mutating: boolean;
  timing: { baseline?: number; mutation?: number };
}) {
  const gate = eligibility(suite, required, terminal, stopped);
  const m = suite.mutation;
  const headingId = `suite-${name.toLowerCase().replace(/\s+/g, '-')}`;
  return <article className="sg-suite" aria-labelledby={headingId}>
    <header className="sg-suite-head">
      <div><h3 id={headingId}>{name}</h3><p>{role}</p></div>
      <span className={`sg-gate is-${gate.state}`}>
        {gate.state === 'eligible' ? <CheckCircle2 size={13} aria-hidden="true" /> : gate.state === 'rejected' ? <AlertTriangle size={13} aria-hidden="true" /> : null}
        {gate.state === 'eligible' ? 'Eligible for mutation' : gate.state === 'rejected' ? 'Rejected' : gate.state === 'pending' ? 'Pending' : 'Not run'}
      </span>
    </header>
    <p className="sg-gate-reason">{gate.reason}</p>

    {m ? <>
      <div className="sg-score">
        <span className="sg-score-value">{m.score == null ? '—' : percent(m.score)}</span>
        <span className="sg-score-label">{m.score == null ? scoreText(m) : `${m.killed} killed of ${m.denominator} scorable`}</span>
      </div>
      <InventoryStrip mutation={m} name={name} />
      <p className="sg-strip-caption">{m.generated} mutants · {excluded(m)} excluded from the score{timing.mutation != null ? ` · ${seconds(timing.mutation)}` : ''}</p>
    </> : <p className="sg-noscore">{mutating && gate.state === 'eligible' ? 'Running against every mutant now. The score appears when the run finishes.' : !terminal ? 'Mutation runs after both baselines pass.' : stopped ? 'No mutation score: the run stopped before this suite was scored.' : 'No mutation score for this suite.'}</p>}

    <h4>Baseline repeats <span className="sg-muted">({suite.baseline_runs.length} of {required} required{timing.baseline != null ? ` · ${seconds(timing.baseline)}` : ''})</span></h4>
    {suite.baseline_runs.length ? <ol className="sg-repeats">
      {suite.baseline_runs.map((run, i) => <li key={i}>
        <span className="sg-repeat-n">#{i + 1}</span><ExecStatus status={run.status} />
        <span>{run.passed_tests ?? '?'}/{run.collected_tests ?? '?'} passed{run.failed_tests ? ` · ${run.failed_tests} failed` : ''}</span>
        <span className="sg-muted">{seconds(run.duration_seconds)}</span>
      </li>)}
    </ol> : <p className="sg-muted">Collection: {suite.collection_status.replace('_', ' ')}. No baseline repeats recorded.</p>}
  </article>;
}

function Cell({ value, zeroMuted = true }: { value: number | null | undefined; zeroMuted?: boolean }) {
  if (value == null) return <td className="sg-muted">—</td>;
  return <td className={zeroMuted && value === 0 ? 'sg-muted' : undefined}>{value}</td>;
}

/**
 * Methodology requirement: show both suites' collected counts, baseline results, every outcome category,
 * the denominator and the score. Rows are metrics, columns are suites, so it fits a phone without scrolling.
 */
export function SuiteComparison({ report, terminal, stopped = false, mutating = false, timings }: {
  report: Report; terminal: boolean; stopped?: boolean; mutating?: boolean; timings: Record<string, number>;
}) {
  const { native, generated } = report;
  const sameInventory = native.mutation && generated.mutation
    ? native.mutation.inventory_sha256 === generated.mutation.inventory_sha256 && native.mutation.configuration_sha256 === generated.mutation.configuration_sha256
    : null;
  return <>
    <div className="sg-suites">
      {SUITES.map(s => <SuitePanel key={s.key} name={s.name} role={s.role} suite={report[s.key]} required={report.required_baseline_repeats}
        terminal={terminal} stopped={stopped} mutating={mutating} timing={{ baseline: timings[`${s.key}_baseline`], mutation: timings[`${s.key}_mutation`] }} />)}
    </div>

    {sameInventory !== null && <p className={`sg-fairness ${sameInventory ? 'is-ok' : 'is-bad'}`}>
      {sameInventory ? <CheckCircle2 size={14} aria-hidden="true" /> : <AlertTriangle size={14} aria-hidden="true" />}
      {sameInventory
        ? <>Same mutant inventory <code>{shortHash(native.mutation!.inventory_sha256)}</code> and configuration <code>{shortHash(native.mutation!.configuration_sha256)}</code> for both suites.</>
        : <>Inventory or configuration hashes differ. These results are not a fair comparison.</>}
    </p>}

    <div className="sg-table-wrap">
      <table className="sg-compare">
        <caption>Native versus generated, by outcome</caption>
        <thead><tr><th scope="col">Measure</th><th scope="col">Native</th><th scope="col">Generated fixture</th></tr></thead>
        <tbody>
          <tr><th scope="row">Collection</th><td><ExecStatus status={native.collection_status} /></td><td><ExecStatus status={generated.collection_status} /></td></tr>
          <tr><th scope="row">Collected tests</th><Cell value={native.collected_tests} zeroMuted={false} /><Cell value={generated.collected_tests} zeroMuted={false} /></tr>
          <tr><th scope="row">Baseline pass rate</th>
            <td>{percent(native.baseline_pass_rate, 0)}</td><td>{percent(generated.baseline_pass_rate, 0)}</td></tr>
          {OUTCOMES.map(outcome => <tr key={outcome} className={`sg-row-${outcome}`}>
            <th scope="row"><span className={`sg-legend sg-o-${outcome}`} aria-hidden="true" />
              <span title={OUTCOME_HELP[outcome]}>{OUTCOME_LABEL[outcome]}</span>
              {outcome !== 'killed' && outcome !== 'survived' && <span className="sg-excl">excluded</span>}</th>
            <Cell value={native.mutation?.[outcome]} /><Cell value={generated.mutation?.[outcome]} />
          </tr>)}
          <tr className="sg-row-total"><th scope="row">Mutants generated</th><Cell value={native.mutation?.generated} zeroMuted={false} /><Cell value={generated.mutation?.generated} zeroMuted={false} /></tr>
          <tr><th scope="row">Denominator <span className="sg-muted">killed + survived</span></th><Cell value={native.mutation?.denominator} zeroMuted={false} /><Cell value={generated.mutation?.denominator} zeroMuted={false} /></tr>
          <tr className="sg-row-score"><th scope="row">Mutation score</th><td>{scoreText(native.mutation)}</td><td>{scoreText(generated.mutation)}</td></tr>
        </tbody>
      </table>
    </div>
    <p className="sg-note">Mutation score = killed / (killed + survived). Timed-out, invalid, error and suspicious mutants are never counted as kills or survivors. A score measures sensitivity to these mutants, not correctness, and is separate from manual QA heuristic coverage.</p>
  </>;
}
