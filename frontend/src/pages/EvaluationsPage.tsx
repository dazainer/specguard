import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Download } from 'lucide-react';
import { evaluations, type Artifact, type CatalogEntry, type EvaluationRun, type Log, type Target } from '../api/evaluations';
import { FixtureBadge, RunStatus } from '../components/evaluation/Badges';
import { InventoryStrip } from '../components/evaluation/InventoryStrip';
import { MutantExplorer } from '../components/evaluation/MutantExplorer';
import { ArtifactViewer, LogViewer, RunContext } from '../components/evaluation/RunEvidence';
import { StageTrack } from '../components/evaluation/StageTrack';
import { SuiteComparison } from '../components/evaluation/SuiteComparison';
import { STRATEGY_LABEL, TERMINAL, eligibility, errorText, label, scopeText, shortHash, shortId, timestamp } from '../evaluation/format';
import { useDocumentTitle } from '../hooks/useDocumentTitle';

function SuiteCell({ run, suite }: { run: EvaluationRun; suite: 'native' | 'generated' }) {
  const report = run.report;
  if (!report) return <span className="sg-muted">—</span>;
  const m = report[suite].mutation;
  if (m) return <div className="sg-cell-score">
    <span>{m.score == null ? 'Unmeasured' : `${(m.score * 100).toFixed(1)}%`} <span className="sg-muted">{m.killed}/{m.denominator}</span></span>
    <InventoryStrip mutation={m} name={suite === 'native' ? 'Native' : 'Generated fixture'} />
  </div>;
  const stopped = run.status === 'failed' || run.status === 'cancelled';
  const gate = eligibility(report[suite], report.required_baseline_repeats, TERMINAL.has(run.status), stopped);
  const unscored = gate.state === 'eligible' && !run.options.baseline_only && TERMINAL.has(run.status);
  return <span className={unscored ? 'sg-muted' : gate.state === 'eligible' ? 'sg-tone-ok' : gate.state === 'rejected' ? 'sg-tone-bad' : 'sg-muted'}>
    {gate.state !== 'eligible' ? gate.reason : unscored ? 'Baseline passed · not scored' : 'Baseline passed'}
  </span>;
}

export function EvaluationsPage() {
  useDocumentTitle('Evaluations');
  const [targets, setTargets] = useState<Target[]>([]);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [runs, setRuns] = useState<EvaluationRun[]>([]);
  const [subject, setSubject] = useState('');
  const [target, setTarget] = useState('');
  const [strategy, setStrategy] = useState('contract-v1');
  const [baseline, setBaseline] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState<boolean | null>(null);
  const submission = useRef<{key: string; identity: string} | null>(null);
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const [t, c, r, health] = await Promise.all([evaluations.targets(), evaluations.catalog(), evaluations.runs(), evaluations.ready()]);
        if (active) { setTargets(t); setCatalog(c); setRuns(r); setReady(health); setError(''); }
      } catch (e) { if (active) setError(errorText(e)); }
      finally { if (active) setLoading(false); }
    };
    void refresh(); const timer = window.setInterval(refresh, 3000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const register = async () => {
    setBusy(true); setError(''); setNotice('');
    try {
      const created = await evaluations.createTarget(label(subject), subject);
      setTargets(t => [created, ...t]); setTarget(created.id); setSubject('');
      setNotice(`Registered ${created.name} at ${shortHash(created.manifest.repository.commit, 8)}. It is selected below.`);
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
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
  const targetName = (id: string) => targets.find(t => t.id === id)?.name ?? shortId(id);
  const runsFor = (id: string) => runs.filter(r => r.target_id === id).length;

  return <div className="sg-page">
    <header className="sg-hero">
      <p className="sg-eyebrow">Executable evaluation</p>
      <h1>From specification to tested evidence</h1>
      <p className="sg-lede">Collect a suite, require repeated passing baselines on the pinned original code, then run native and generated tests against the same mutant inventory.</p>
      <div className="sg-hero-meta">
        <FixtureBadge />
        {ready !== null && <span className={`sg-ready ${ready ? 'is-ok' : 'is-bad'}`}>
          <span className="sg-ready-dot" aria-hidden="true" />{ready ? 'Worker ready' : 'Worker not ready'}
        </span>}
      </div>
    </header>

    <p className="sg-alert is-info">Local fixture mode with five pinned synthetic subjects. Generated suites are handwritten fixtures: they demonstrate the pipeline and do not measure AI test quality.</p>
    {error && <p role="alert" className="sg-alert is-bad">{error}</p>}
    {ready === false && <p role="status" className="sg-alert is-warn">The evaluation worker is not ready, so new runs will stay queued. Check database migrations, the runner image ID and that the worker process is running (see the operations guide).</p>}

    <div className="sg-setup">
      <section className="sg-panel" aria-labelledby="register-heading">
        <p className="sg-step">Step 1</p>
        <h2 id="register-heading">Register a target</h2>
        <p className="sg-muted">A target pins a curated subject: its specification, interface, source and native tests at one commit.</p>
        <label htmlFor="subject">Curated subject</label>
        <select id="subject" value={subject} onChange={e => setSubject(e.target.value)}>
          <option value="">Choose a subject</option>
          {catalog.map(c => <option key={c.subject} value={c.subject}>{label(c.subject)} · {c.commit.slice(0, 8)}</option>)}
        </select>
        <button type="button" className="sg-btn" disabled={!subject || busy} onClick={register}>Register target</button>
        <p role="status" className="sg-success">{notice}</p>
      </section>

      <section className="sg-panel" aria-labelledby="start-heading">
        <p className="sg-step">Step 2</p>
        <h2 id="start-heading">Start an evaluation</h2>
        <label htmlFor="target">Target</label>
        <select id="target" value={target} onChange={e => setTarget(e.target.value)}>
          <option value="">{targets.length ? 'Choose a registered target' : 'Register a target first'}</option>
          {targets.map(t => <option key={t.id} value={t.id}>{t.name} · {t.manifest.repository.commit.slice(0, 8)}</option>)}
        </select>
        <label htmlFor="strategy">Prompt configuration</label>
        <select id="strategy" value={strategy} onChange={e => setStrategy(e.target.value)}>
          <option value="contract-v1">Contract coverage (contract-v1)</option>
          <option value="boundary-v1">Boundary coverage (boundary-v1)</option>
        </select>
        <fieldset className="sg-scope">
          <legend>Scope</legend>
          <label className={baseline ? 'is-on' : undefined}>
            <input type="radio" name="scope" checked={baseline} onChange={() => setBaseline(true)} />
            <span><strong>Baseline check</strong><span className="sg-muted">Collection and repeated baselines only. Fast; produces no mutation score.</span></span>
          </label>
          <label className={!baseline ? 'is-on' : undefined}>
            <input type="radio" name="scope" checked={!baseline} onChange={() => setBaseline(false)} />
            <span><strong>Mutation comparison</strong><span className="sg-muted">Adds native and generated runs against every mutant. Takes minutes.</span></span>
          </label>
        </fieldset>
        <button type="button" className="sg-btn is-primary" disabled={!target || busy} onClick={start}>{busy ? 'Starting…' : baseline ? 'Start baseline check' : 'Start mutation comparison'}</button>
      </section>
    </div>

    <section aria-labelledby="runs-heading">
      <div className="sg-section-head"><h2 id="runs-heading">Recent evaluations</h2><span className="sg-count">{runs.length}</span></div>
      {loading ? <p role="status" className="sg-muted">Loading evaluations…</p> : !runs.length ? <p className="sg-empty">No evaluations yet. Register a target, then start a baseline check.</p> :
        <div className="sg-table-wrap is-cards"><table className="sg-runs">
          <caption className="sg-sr">Recent evaluation runs with native and generated mutation results</caption>
          <thead><tr><th scope="col">Run</th><th scope="col">Target</th><th scope="col">Status</th><th scope="col">Scope</th><th scope="col">Native</th><th scope="col">Generated fixture</th><th scope="col">Created</th></tr></thead>
          <tbody>{runs.map(run => <tr key={run.id}>
            <th scope="row" data-label="Run"><Link to={`/evaluations/${run.id}`} aria-label={`Open run ${shortId(run.id)} for ${targetName(run.target_id)}`}><code>{shortId(run.id)}</code></Link></th>
            <td data-label="Target">{targetName(run.target_id)}</td>
            <td data-label="Status"><div><RunStatus status={run.status} />{run.failure_reason && run.status !== 'cancelled' && <span className="sg-reason">{label(run.failure_reason)}</span>}</div></td>
            <td data-label="Scope"><div>{scopeText(run)}<span className="sg-muted sg-block">{STRATEGY_LABEL[run.options.strategy] ?? run.options.strategy}</span></div></td>
            <td data-label="Native"><SuiteCell run={run} suite="native" /></td>
            <td data-label="Generated"><SuiteCell run={run} suite="generated" /></td>
            <td data-label="Created">{timestamp(run.created_at)}</td>
          </tr>)}</tbody>
        </table></div>}
    </section>

    {targets.length > 0 && <section aria-labelledby="targets-heading">
      <div className="sg-section-head"><h2 id="targets-heading">Registered targets</h2><span className="sg-count">{targets.length}</span></div>
      <div className="sg-table-wrap is-cards"><table className="sg-targets">
        <caption className="sg-sr">Registered targets and their pinned specifications</caption>
        <thead><tr><th scope="col">Target</th><th scope="col">Commit</th><th scope="col">Specification</th><th scope="col">Context</th><th scope="col">Runs</th></tr></thead>
        <tbody>{targets.map(t => <tr key={t.id}>
          <th scope="row" data-label="Target">{t.name}</th>
          <td data-label="Commit"><code title={t.manifest.repository.commit}>{t.manifest.repository.commit.slice(0, 8)}</code></td>
          <td data-label="Specification"><code>{t.subject}/{t.manifest.specification.path}</code></td>
          <td data-label="Context"><span>{label(t.manifest.context.mode)} · <code>{t.manifest.context.source_files.join(', ')}</code></span></td>
          <td data-label="Runs">{runsFor(t.id)}</td>
        </tr>)}</tbody>
      </table></div>
    </section>}
  </div>;
}

const SECTIONS = [['results', 'Results'], ['mutants', 'Mutants'], ['artifacts', 'Artifacts'], ['logs', 'Logs'], ['context', 'Context']] as const;

export function EvaluationPage() {
  const {runId = ''} = useParams();
  return <EvaluationDetail key={runId} runId={runId} />;
}

function EvaluationDetail({ runId }: { runId: string }) {
  const [run, setRun] = useState<EvaluationRun | null>(null);
  const [target, setTarget] = useState<Target | undefined>();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [logs, setLogs] = useState<Log[]>([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const terminal = !!run && TERMINAL.has(run.status);
  useDocumentTitle(run ? `${target?.name ?? 'Run'} ${shortId(runId)} · ${label(run.status)}` : `Run ${shortId(runId)}`);

  useEffect(() => {
    let active = true; let timer = 0;
    const refresh = async () => {
      let next = 2500;
      try {
        const result = await evaluations.run(runId);
        if (!active) return;
        setRun(result); setError('');
        if (TERMINAL.has(result.status)) next = 15000;
        if (!result.pruned) {
          const [a, l] = await Promise.all([evaluations.artifacts(runId), evaluations.logs(runId)]);
          if (active) { setArtifacts(a); setLogs(l); }
        } else { setArtifacts([]); setLogs([]); }
      } catch (e) { if (active) setError(errorText(e)); }
      if (active) timer = window.setTimeout(refresh, next);
    };
    void refresh();
    return () => { active = false; window.clearTimeout(timer); };
  }, [runId]);
  useEffect(() => {
    if (!run) return;
    let active = true;
    evaluations.target(run.target_id).then(value => { if (active) setTarget(value); }).catch(() => { if (active) setTarget(undefined); });
    return () => { active = false; };
  }, [run?.target_id]);

  const cancel = async () => {
    setBusy(true);
    try { setRun(await evaluations.cancel(runId)); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  };

  if (!run) return <div className="sg-page">
    <Link to="/" className="sg-back">← All evaluations</Link>
    {error ? <p role="alert" className="sg-alert is-bad">{error}</p> : <p role="status" className="sg-muted">Loading run {shortId(runId)}…</p>}
  </div>;

  const report = run.report;
  const hasMutation = !!(report?.native.mutation || report?.generated.mutation);
  const formats = run.pruned || !terminal ? (['json'] as const) : (['json', 'md', 'csv'] as const);
  const mutantReason = run.pruned ? 'Mutant details expired under the retention policy. Summary counts remain in the report.'
    : run.options.baseline_only ? 'This was a baseline check. No mutants were generated; start a mutation comparison to see them.'
    : !terminal ? 'Mutant details are indexed when the run finishes.'
    : 'No suite reached mutation. See the baseline gates above for why.';

  return <div className="sg-page">
    <Link to="/" className="sg-back">← All evaluations</Link>
    <header className="sg-run-head">
      <div className="sg-run-title">
        <p className="sg-eyebrow">Run <code>{shortId(run.id)}</code> · {scopeText(run)}</p>
        <h1>{target?.name ?? 'Evaluation'} <span className="sg-muted">@ {shortHash(report?.provenance.repository_commit ?? target?.manifest.repository.commit, 8)}</span></h1>
        <p className="sg-run-sub">
          <RunStatus status={run.status} />
          <span>{STRATEGY_LABEL[run.options.strategy] ?? run.options.strategy}</span>
          {target && <span>spec <code>{target.subject}/{target.manifest.specification.path}</code></span>}
          <FixtureBadge />
        </p>
        <p className="sg-sr" role="status">Run status: {label(run.status)}</p>
      </div>
      <div className="sg-actions">
        {!terminal && <button type="button" className="sg-btn is-danger" onClick={cancel} disabled={busy || !!run.cancel_requested}>{run.cancel_requested ? 'Cancelling…' : 'Cancel run'}</button>}
        {report && <div className="sg-exports" role="group" aria-label="Download report">
          <span className="sg-muted">Report</span>
          {formats.map(format => <a key={format} className="sg-btn is-small" href={evaluations.exportUrl(runId, format)} download>
            <Download size={13} aria-hidden="true" />{format === 'md' ? 'Markdown' : format.toUpperCase()}</a>)}
        </div>}
      </div>
    </header>

    {error && <p role="alert" className="sg-alert is-bad">Could not refresh this run: {error}</p>}
    {run.failure_reason && <p role="alert" className={`sg-alert ${run.status === 'cancelled' ? 'is-warn' : 'is-bad'}`}>
      <strong>{run.status === 'cancelled' ? 'Cancelled' : 'Failed'}: {label(run.failure_reason)}.</strong> Partial observations are kept below. An incomplete run is not a successful evaluation and has no valid comparison.</p>}
    {!!run.pruned && <p className="sg-alert is-info">Raw artifacts, logs and mutant details expired under the retention policy. The JSON report and summary counts remain.</p>}

    <StageTrack run={run} />

    <nav className="sg-jump" aria-label="Sections of this run">
      {SECTIONS.map(([id, name]) => <a key={id} href={`#${id}`}>{name}</a>)}
    </nav>

    <section id="results" aria-labelledby="results-heading" className="sg-section">
      <div className="sg-section-head"><h2 id="results-heading">Native versus generated</h2></div>
      {report ? <SuiteComparison report={report} terminal={terminal} stopped={run.status === 'failed' || run.status === 'cancelled'} mutating={run.status === 'mutating'} timings={run.timings ?? {}} />
        : <p className="sg-empty">{terminal ? 'This run ended before a report was written.' : 'Results appear once the suites are collected.'}</p>}
    </section>

    <section id="mutants" aria-labelledby="mutants-heading" className="sg-section">
      <div className="sg-section-head"><h2 id="mutants-heading">Mutants</h2></div>
      <MutantExplorer runId={runId} available={terminal && !run.pruned && hasMutation} emptyReason={mutantReason} />
    </section>

    <section id="artifacts" aria-labelledby="artifacts-heading" className="sg-section">
      <div className="sg-section-head"><h2 id="artifacts-heading">Generated artifacts</h2><span className="sg-count">{artifacts.length}</span></div>
      <ArtifactViewer runId={runId} artifacts={artifacts} pruned={!!run.pruned} />
    </section>

    <section id="logs" aria-labelledby="logs-heading" className="sg-section">
      <div className="sg-section-head"><h2 id="logs-heading">Execution logs</h2><span className="sg-count">{logs.length}</span></div>
      <p className="sg-muted">Collection and baseline runs, scrubbed and capped. Per-mutant runner output is inside each mutant above.</p>
      <LogViewer logs={logs} pruned={!!run.pruned} />
    </section>

    <section id="context" aria-labelledby="context-heading" className="sg-section">
      <div className="sg-section-head"><h2 id="context-heading">Context and provenance</h2></div>
      <RunContext run={run} target={target} />
    </section>
  </div>;
}
