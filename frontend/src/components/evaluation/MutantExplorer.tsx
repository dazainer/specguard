import { useEffect, useMemo, useState } from 'react';
import { evaluations, type Execution, type Mutant } from '../../api/evaluations';
import { OUTCOMES, OUTCOME_LABEL, errorText, seconds, shortId, type Outcome } from '../../evaluation/format';
import { ExecStatus, OutcomeBadge } from './Badges';

type SuiteKey = 'native' | 'generated';
const PAGE = 20;
const SUITE_NAME: Record<SuiteKey, string> = { native: 'Native', generated: 'Generated fixture' };

export function DiffView({ diff }: { diff: string }) {
  const lines = diff.replace(/\n$/, '').split('\n');
  return <pre className="sg-code sg-diff" tabIndex={0} aria-label="Mutant diff">
    {lines.map((line, i) => {
      const kind = line.startsWith('+++') || line.startsWith('---') ? 'file' : line.startsWith('@@') ? 'hunk' : line.startsWith('+') ? 'add' : line.startsWith('-') ? 'del' : 'ctx';
      return <span key={i} className={`sg-diff-${kind}`}>
        {(kind === 'add' || kind === 'del') && <span className="sg-sr">{kind === 'add' ? 'Added: ' : 'Removed: '}</span>}
        {line}{'\n'}
      </span>;
    })}
  </pre>;
}

export function OutputBlocks({ stdout, stderr, truncated }: { stdout: string; stderr: string; truncated: boolean }) {
  return <div className="sg-output">
    <section aria-label="Standard output"><h5>stdout</h5>
      {stdout ? <pre className="sg-code" tabIndex={0}>{stdout}</pre> : <p className="sg-muted">Empty</p>}</section>
    {stderr && <section aria-label="Standard error"><h5>stderr</h5><pre className="sg-code sg-code-err" tabIndex={0}>{stderr}</pre></section>}
    {truncated && <p className="sg-warn-text">Output was truncated at the runner's output limit.</p>}
  </div>;
}

function ExecutionDetail({ execution }: { execution: Execution }) {
  return <details className="sg-subdetails">
    <summary>Runner output · <ExecStatus status={execution.status} /> · exit {execution.exit_code ?? '—'}{execution.oom_killed ? ' · out of memory' : ''}</summary>
    {execution.error_message && <p className="sg-warn-text">{execution.error_message}</p>}
    <OutputBlocks stdout={execution.stdout} stderr={execution.stderr} truncated={execution.output_truncated} />
  </details>;
}

interface Row { id: string; native?: Mutant; generated?: Mutant }

/**
 * Both suites run against the same inventory, so mutants are joined by id. That makes the question a
 * reviewer actually asks — which mutants does native kill that the generated suite misses? — one filter.
 */
export function MutantExplorer({ runId, available, emptyReason }: { runId: string; available: boolean; emptyReason: string }) {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [error, setError] = useState('');
  const [suite, setSuite] = useState<SuiteKey>('generated');
  const [outcome, setOutcome] = useState<Outcome | ''>('');
  const [disagree, setDisagree] = useState(false);
  const [page, setPage] = useState(0);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setRows(null); setError(''); setPage(0);
    if (!available) { setRows(null); return; }
    Promise.all([evaluations.allMutants(runId, 'native'), evaluations.allMutants(runId, 'generated')]).then(([native, generated]) => {
      if (!active) return;
      const byId = new Map<string, Row>();
      for (const m of native) byId.set(m.id, { id: m.id, native: m });
      for (const m of generated) byId.set(m.id, { ...(byId.get(m.id) ?? { id: m.id }), generated: m });
      const sorted = [...byId.values()].sort((a, b) => {
        const x = (a.generated ?? a.native)!, y = (b.generated ?? b.native)!;
        return x.source_file.localeCompare(y.source_file) || x.line - y.line || a.id.localeCompare(b.id);
      });
      setRows(sorted); setError('');
    }).catch(e => { if (active) setError(errorText(e)); });
    return () => { active = false; };
  }, [runId, available, retry]);

  const counts = useMemo(() => {
    const result = Object.fromEntries(OUTCOMES.map(o => [o, 0])) as Record<Outcome, number>;
    for (const row of rows ?? []) { const s = row[suite]?.status as Outcome | undefined; if (s && s in result) result[s]++; }
    return result;
  }, [rows, suite]);
  const withSuite = (rows ?? []).filter(row => row[suite]);
  const disagreements = withSuite.filter(row => row.native && row.generated && row.native.status !== row.generated.status).length;
  const filtered = withSuite.filter(row => (!outcome || row[suite]!.status === outcome)
    && (!disagree || (row.native && row.generated && row.native.status !== row.generated.status)));
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const current = Math.min(page, pages - 1);
  const visible = filtered.slice(current * PAGE, current * PAGE + PAGE);
  const other: SuiteKey = suite === 'native' ? 'generated' : 'native';
  const reset = () => setPage(0);

  if (!available) return <p className="sg-empty">{emptyReason}</p>;
  if (error) return <div role="alert" className="sg-alert is-bad">Mutant details could not be loaded: {error} <button type="button" onClick={() => setRetry(value => value + 1)}>Retry mutants</button></div>;
  if (!rows) return <p role="status" className="sg-muted">Loading mutants…</p>;
  if (!rows.length) return <p className="sg-empty">No mutants were recorded for this run.</p>;

  return <div className="sg-explorer">
    <div className="sg-filters">
      <fieldset className="sg-segmented">
        <legend>Suite</legend>
        {(['generated', 'native'] as const).map(key => <label key={key} className={suite === key ? 'is-on' : undefined}>
          <input type="radio" name="mutant-suite" value={key} checked={suite === key} onChange={() => { setSuite(key); reset(); }} />
          {SUITE_NAME[key]}
        </label>)}
      </fieldset>
      <fieldset className="sg-chips">
        <legend>Outcome</legend>
        <label className={!outcome ? 'is-on' : undefined}>
          <input type="radio" name="mutant-outcome" value="" checked={!outcome} onChange={() => { setOutcome(''); reset(); }} />
          All <span className="sg-chip-n">{withSuite.length}</span>
        </label>
        {OUTCOMES.map(o => <label key={o} className={`${outcome === o ? 'is-on' : ''}${counts[o] ? '' : ' is-zero'}`}>
          <input type="radio" name="mutant-outcome" value={o} checked={outcome === o} onChange={() => { setOutcome(o); reset(); }} />
          <span className={`sg-swatch sg-o-${o}`} aria-hidden="true" />{OUTCOME_LABEL[o]} <span className="sg-chip-n">{counts[o]}</span>
        </label>)}
      </fieldset>
      <label className="sg-toggle">
        <input type="checkbox" checked={disagree} onChange={e => { setDisagree(e.target.checked); reset(); }} />
        Only where suites disagree <span className="sg-chip-n">{disagreements}</span>
      </label>
    </div>

    <p className="sg-muted" role="status">{filtered.length
      ? `Showing ${current * PAGE + 1}–${Math.min(filtered.length, current * PAGE + PAGE)} of ${filtered.length} ${SUITE_NAME[suite].toLowerCase()} mutants`
      : 'No mutants match these filters.'}</p>

    <ul className="sg-mutants">
      {visible.map(row => {
        const m = row[suite]!; const peer = row[other];
        return <li key={row.id}>
          <details className="sg-mutant">
            <summary>
              <OutcomeBadge outcome={m.status} />
              <code className="sg-loc">{m.source_file}:{m.line}</code>
              <span className="sg-op">{m.operator}</span>
              {peer && <span className={`sg-peer${peer.status !== m.status ? ' is-diff' : ''}`}>
                {SUITE_NAME[other]}: <OutcomeBadge outcome={peer.status} compact />
              </span>}
            </summary>
            <div className="sg-mutant-body">
              <dl className="sg-kv">
                <div><dt>Mutant</dt><dd><code title={m.id}>{shortId(m.id)}</code></dd></div>
                <div><dt>Duration</dt><dd>{seconds(m.duration_seconds)}</dd></div>
                <div><dt>Killing test</dt><dd>{m.killing_test ? <code>{m.killing_test}</code> : '—'}</dd></div>
                <div><dt>Manual review</dt><dd>{m.manual_review}</dd></div>
              </dl>
              <DiffView diff={m.diff} />
              {m.execution ? <ExecutionDetail execution={m.execution} /> : <p className="sg-muted">Not executed{m.status === 'invalid' ? ': mutmut marked this variant invalid.' : '.'}</p>}
            </div>
          </details>
        </li>;
      })}
    </ul>

    {pages > 1 && <nav className="sg-pager" aria-label="Mutant pages">
      <button type="button" disabled={current === 0} onClick={() => setPage(current - 1)}>Previous</button>
      <span>Page {current + 1} of {pages}</span>
      <button type="button" disabled={current >= pages - 1} onClick={() => setPage(current + 1)}>Next</button>
    </nav>}
  </div>;
}
