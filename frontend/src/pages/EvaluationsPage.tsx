import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { evaluations, type Artifact, type EvaluationRun, type Log, type Mutant, type Suite, type Target } from '../api/evaluations';

const terminal = new Set(['completed', 'failed', 'cancelled']);
const label = (value: string) => value.replace(/_/g, ' ');
const errorText = (error: unknown) => error instanceof Error ? error.message : 'Request failed';

export function EvaluationsPage() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [catalog, setCatalog] = useState<{subject: string; commit: string}[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [subject, setSubject] = useState('');
  const [target, setTarget] = useState('');
  const [strategy, setStrategy] = useState('contract-v1');
  const [baseline, setBaseline] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);
  const submission = useRef<{key: string; identity: string} | null>(null);
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const [t, c, r, health] = await Promise.all([evaluations.targets(), evaluations.catalog(), evaluations.runs(), fetch('/api/evaluations/ready')]);
        if (active) { setTargets(t); setCatalog(c); setRuns(r); setReady(health.ok); setError(''); }
      } catch (e) { if (active) setError(errorText(e)); }
      finally { if (active) setLoading(false); }
    };
    void refresh(); const timer = window.setInterval(refresh, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const register = async () => {
    setBusy(true); setError('');
    try { const created = await evaluations.createTarget(label(subject), subject); setTargets(t => [created, ...t]); setTarget(created.id); }
    catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  const start = async () => {
    setBusy(true); setError('');
    const identity = JSON.stringify([target, strategy, baseline]);
    if (submission.current?.identity !== identity) submission.current = {key: crypto.randomUUID(), identity};
    try {
      const run = await evaluations.start(target, strategy, baseline, submission.current.key);
      submission.current = null; navigate(`/evaluations/${run.id}`);
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  return <section className="evaluation-page">
    <div className="evaluation-heading"><span className="evaluation-eyebrow">EXECUTABLE EVALUATION</span><h1>From specification to tested evidence</h1>
      <p>Collect tests, verify repeated baselines, and compare native and generated suites against identical mutants.</p></div>
    <p className="evaluation-notice">Local fixture mode · Five pinned synthetic subjects · Handwritten fixtures demonstrate the pipeline, not AI test quality.</p>
    {error && <p role="alert" className="evaluation-error">{error}</p>}
    {!loading && !ready && <p role="status" className="evaluation-notice">The evaluation worker is not ready. Runs remain queued until it is available. Check the setup guide for migrations, image configuration and worker startup.</p>}
    <div className="evaluation-grid">
      <div className="evaluation-panel"><h2>Register a target</h2><label htmlFor="subject">Curated subject</label>
        <select id="subject" value={subject} onChange={e => setSubject(e.target.value)}><option value="">Choose a subject</option>{catalog.map(c => <option key={c.subject} value={c.subject}>{label(c.subject)} · {c.commit.slice(0, 8)}</option>)}</select>
        <button disabled={!subject || busy} onClick={register}>Register pinned target</button></div>
      <div className="evaluation-panel"><h2>Start an evaluation</h2><label htmlFor="target">Target</label>
        <select id="target" value={target} onChange={e => setTarget(e.target.value)}><option value="">Choose a registered target</option>{targets.map(t => <option key={t.id} value={t.id}>{t.name} · {t.manifest.repository.commit.slice(0, 8)}</option>)}</select>
        <label htmlFor="strategy">Prompt configuration</label><select id="strategy" value={strategy} onChange={e => setStrategy(e.target.value)}><option value="contract-v1">Contract coverage</option><option value="boundary-v1">Boundary coverage</option></select>
        <label className="evaluation-check"><input type="checkbox" checked={baseline} onChange={e => setBaseline(e.target.checked)} />Baseline only — a quick collection and repeatability check</label>
        <button disabled={!target || busy} onClick={start}>{busy ? 'Submitting…' : 'Start evaluation'}</button></div>
    </div>
    <h2>Recent evaluations</h2>
    {loading ? <p role="status">Loading evaluations…</p> : !runs.length ? <p>No evaluations yet. Register a target and start a baseline check.</p> :
      <div className="evaluation-table-wrap"><table><thead><tr><th>Run</th><th>Target</th><th>Status</th><th>Scope</th><th>Started</th></tr></thead><tbody>{runs.map(run => <tr key={run.id}>
        <td><Link to={`/evaluations/${run.id}`}>{run.id.slice(0, 8)}</Link></td><td>{targets.find(t => t.id === run.target_id)?.name || run.target_id.slice(0, 8)}</td>
        <td><span className={`evaluation-state ${run.status}`}>{label(run.status)}</span></td><td>{run.options.baseline_only ? 'Baseline' : 'Full mutation comparison'}</td><td>{new Date(run.created_at * 1000).toLocaleString()}</td>
      </tr>)}</tbody></table></div>}
  </section>;
}

function SuiteRow({name, suite}: {name: string; suite: Suite}) {
  const m = suite.mutation;
  return <tr><th scope="row">{name}</th><td>{suite.collected_tests ?? '—'}</td><td>{suite.baseline_pass_rate === null ? 'Not run' : `${Math.round(suite.baseline_pass_rate * 100)}%`}</td>
    {(['killed', 'survived', 'timed_out', 'invalid', 'errors', 'suspicious'] as const).map(key => <td key={key}>{m?.[key] ?? '—'}</td>)}
    <td>{m?.score == null ? 'Unmeasured' : `${(m.score * 100).toFixed(1)}% (${m.killed}/${m.denominator})`}</td></tr>;
}

export function EvaluationPage() {
  const {runId = ''} = useParams();
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [content, setContent] = useState('');
  const [logs, setLogs] = useState<Log[]>([]);
  const [error, setError] = useState('');
  const [mutants, setMutants] = useState<Mutant[]>([]);
  const [total, setTotal] = useState(0);
  const [suite, setSuite] = useState('generated');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const result = await evaluations.run(runId);
        if (!active) return;
        setRun(result);
        if (!result.pruned) {
          const [a, l] = await Promise.all([evaluations.artifacts(runId), evaluations.logs(runId)]);
          if (active) { setArtifacts(a); setLogs(l); }
        } else if (active) {
          setArtifacts([]); setLogs([]); setContent(''); setMutants([]); setTotal(0);
        }
      } catch (e) { if (active) setError(errorText(e)); }
    };
    void refresh(); const timer = window.setInterval(refresh, 2500);
    return () => { active = false; window.clearInterval(timer); };
  }, [runId]);
  useEffect(() => {
    let active = true;
    if (run && terminal.has(run.status) && !run.pruned) {
      evaluations.mutants(runId, suite, status, offset).then(data => { if (active) { setMutants(data.items); setTotal(data.total); } }).catch(e => { if (active) setError(errorText(e)); });
    }
    return () => { active = false; };
  }, [runId, run?.status, run?.pruned, suite, status, offset]);
  const cancel = async () => {
    setBusy(true);
    try { setRun(await evaluations.cancel(runId)); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };
  return <section className="evaluation-page">
    <Link to="/">← Evaluations</Link><h1>Evaluation {runId.slice(0, 8)}</h1>
    {error && <p role="alert" className="evaluation-error">{error}</p>}
    {!run ? <p role="status">Loading run…</p> : <>
      <div className="evaluation-toolbar"><span role="status" className={`evaluation-state ${run.status}`}>{label(run.status)}</span>
        {!terminal.has(run.status) && <button onClick={cancel} disabled={busy || !!run.cancel_requested}>{run.cancel_requested ? 'Cancellation requested…' : 'Cancel evaluation'}</button>}
        {run.report && (run.pruned || !terminal.has(run.status) ? ['json'] : ['json', 'md', 'csv']).map(format => <a key={format} href={`/api/evaluations/runs/${runId}/export?format=${format}`}>Download {format.toUpperCase()}</a>)}
      </div>
      {run.failure_reason && <p role="alert" className="evaluation-error">Run ended: {label(run.failure_reason)}. Partial observations are retained; an incomplete run is not a successful evaluation.</p>}
      {!!run.pruned && <p className="evaluation-notice">Raw artifacts expired under the retention policy. The JSON report and summary metrics remain available.</p>}
      <p>Fixture provider · {run.options.strategy} · {run.options.baseline_only ? 'Baseline check' : 'Full inventory'} · Queue time {run.queue_seconds.toFixed(1)} s</p>
      {run.report && <><div className="evaluation-table-wrap"><table><caption>Native versus generated observations</caption><thead><tr><th>Suite</th><th>Collected</th><th>Baseline pass</th><th>Killed</th><th>Survived</th><th>Timeout</th><th>Invalid</th><th>Error</th><th>Suspicious</th><th>Mutation score</th></tr></thead>
        <tbody><SuiteRow name="Native" suite={run.report.native} /><SuiteRow name="Generated fixture" suite={run.report.generated} /></tbody></table></div>
        <p className="evaluation-note">Mutation score = killed / (killed + survived). Excluded outcomes stay visible. A baseline-only run has no mutation score. These measurements are distinct from manual QA heuristic coverage.</p></>}
      <details><summary>Progress and timing</summary><ol>{run.events?.map((event, i) => <li key={i}>{new Date(event.at * 1000).toLocaleTimeString()} — {label(event.stage)}</li>)}</ol>
        <dl>{Object.entries(run.timings || {}).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd>{value.toFixed(2)} s</dd></div>)}</dl></details>
      <h2>Generated artifacts</h2><p>Source is displayed as text. Views are scrubbed; hashes describe the original stored files.</p>
      {!artifacts.length ? <p>Artifacts become available when the run finishes.</p> : artifacts.map(a => <div className="evaluation-artifact" key={a.path}><button onClick={() => evaluations.artifact(runId, a.path).then(data => setContent(data.content)).catch(e => setError(errorText(e)))}>{a.path}</button><span>{a.accepted ? 'Accepted baseline' : 'Not accepted'} · {a.size_bytes} bytes</span><code>SHA-256 {a.sha256}</code></div>)}
      {content && <pre className="evaluation-code" tabIndex={0}>{content}</pre>}
      <h2>Execution logs</h2>{!logs.length ? <p>No execution logs yet.</p> : logs.map(log => <details key={log.stage}><summary>{label(log.stage)} — {log.status}{log.output_truncated ? ' · truncated' : ''}</summary><pre className="evaluation-code" tabIndex={0}>{log.stdout}{log.stderr}</pre></details>)}
      <h2>Mutants</h2><div className="evaluation-toolbar"><label>Suite <select value={suite} onChange={e => {setSuite(e.target.value); setOffset(0);}}><option value="generated">Generated fixture</option><option value="native">Native</option></select></label>
        <label>Outcome <select value={status} onChange={e => {setStatus(e.target.value); setOffset(0);}}><option value="">All outcomes</option>{['killed','survived','timed_out','invalid','errors','suspicious'].map(value => <option key={value} value={value}>{label(value)}</option>)}</select></label></div>
      {!terminal.has(run.status) ? <p>Mutant details are indexed when execution finishes.</p> : !mutants.length ? <p>No mutants match this view.</p> : mutants.map(m => <details key={m.id}><summary>{m.status} · {m.source_file}:{m.line} · {m.operator}</summary><p>{m.duration_seconds.toFixed(2)} s · Review: {m.manual_review}{m.killing_test ? ` · Killing test: ${m.killing_test}` : ''}</p><pre className="evaluation-code" tabIndex={0}>{m.diff}</pre>{m.execution && <pre className="evaluation-code" tabIndex={0}>{m.execution.stdout}{m.execution.stderr}</pre>}</details>)}
      <div className="evaluation-toolbar"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 20))}>Previous</button><span>{total ? `${offset + 1}–${Math.min(offset + 20, total)} of ${total}` : '0 results'}</span><button disabled={offset + 20 >= total} onClick={() => setOffset(offset + 20)}>Next</button></div>
    </>}
  </section>;
}
