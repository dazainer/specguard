import { useEffect, useRef, useState } from 'react';
import { FileCode2, X } from 'lucide-react';
import { evaluations, type Artifact, type EvaluationRun, type Log, type Target } from '../../api/evaluations';
import { STRATEGY_LABEL, bytes, errorText, label, parseLogStage, seconds, shortHash, timestamp } from '../../evaluation/format';
import { ExecStatus } from './Badges';
import { OutputBlocks } from './MutantExplorer';

export function ArtifactViewer({ runId, artifacts, pruned }: { runId: string; artifacts: Artifact[]; pruned: boolean }) {
  const [open, setOpen] = useState<{ path: string; content: string } | null>(null);
  const [error, setError] = useState('');
  const request = useRef(0);
  useEffect(() => {
    request.current++; setOpen(null); setError('');
    return () => { request.current++; };
  }, [runId, pruned]);
  const view = (path: string) => {
    const current = ++request.current;
    if (open?.path === path) { setOpen(null); return; }
    evaluations.artifact(runId, path).then(data => {
      if (current === request.current) { setOpen({ path, content: data.content }); setError(''); }
    }).catch(e => { if (current === request.current) setError(errorText(e)); });
  };
  if (pruned) return <p className="sg-empty">Raw artifacts expired under the retention policy. Hashes remain in the JSON report.</p>;
  if (!artifacts.length) return <p className="sg-empty">Generated test files appear here once generation finishes.</p>;
  return <>
    {error && <p role="alert" className="sg-alert is-bad">{error}</p>}
    <ul className="sg-artifacts">
      {artifacts.map(a => <li key={a.path} className={open?.path === a.path ? 'is-open' : undefined}>
        <button type="button" className="sg-artifact-btn" aria-expanded={open?.path === a.path} aria-controls="artifact-source" onClick={() => view(a.path)}>
          <FileCode2 size={15} aria-hidden="true" /><code>{a.path}</code>
        </button>
        <span className={a.accepted ? 'sg-tone-ok' : 'sg-tone-bad'}>{a.accepted ? 'Accepted by baseline' : 'Not accepted'}</span>
        <span className="sg-muted">{bytes(a.size_bytes)}</span>
        <code className="sg-hash" title={`SHA-256 ${a.sha256}`}>sha256 {shortHash(a.sha256, 16)}</code>
      </li>)}
    </ul>
    {open && <section id="artifact-source" className="sg-source" aria-label={`Source of ${open.path}`}>
      <header><code>{open.path}</code><span className="sg-muted">scrubbed view · displayed as text, never executed</span>
        <button type="button" className="sg-icon-btn" onClick={() => { request.current++; setOpen(null); }} aria-label="Close source"><X size={15} aria-hidden="true" /></button></header>
      <pre className="sg-code sg-numbered" tabIndex={0}>{open.content.replace(/\n$/, '').split('\n').map((line, i) => <span key={i}>{line}{'\n'}</span>)}</pre>
    </section>}
  </>;
}

export function LogViewer({ logs, pruned }: { logs: Log[]; pruned: boolean }) {
  if (pruned) return <p className="sg-empty">Execution logs expired under the retention policy.</p>;
  if (!logs.length) return <p className="sg-empty">Collection and baseline logs appear as each step finishes.</p>;
  return <ul className="sg-logs">
    {logs.map(log => {
      const stage = parseLogStage(log.stage);
      return <li key={log.stage}><details className="sg-log">
        <summary>
          {stage.suite && <span className={`sg-suite-tag is-${stage.suite}`}>{stage.suite === 'native' ? 'Native' : 'Generated'}</span>}
          <span>{stage.kind}{stage.repeat ? ` · repeat ${stage.repeat}` : ''}</span>
          <ExecStatus status={log.status} />
          {log.output_truncated && <span className="sg-warn-text">truncated</span>}
        </summary>
        <OutputBlocks stdout={log.stdout} stderr={log.stderr} truncated={log.output_truncated} />
      </details></li>;
    })}
  </ul>;
}

function Row({ term, children }: { term: string; children: React.ReactNode }) {
  return <div><dt>{term}</dt><dd>{children}</dd></div>;
}

/** What was evaluated and under which pinned conditions. Hashes are shortened; full values are in titles and the JSON export. */
export function RunContext({ run, target }: { run: EvaluationRun; target?: Target }) {
  const r = run.report; const manifest = target?.manifest;
  return <div className="sg-context">
    <section aria-labelledby="ctx-target"><h3 id="ctx-target">Target and specification</h3><dl className="sg-kv">
      <Row term="Subject">{target ? <code>{target.subject}</code> : <span className="sg-muted">Target record unavailable</span>}</Row>
      <Row term="Commit"><code title={r?.provenance.repository_commit ?? manifest?.repository.commit}>{shortHash(r?.provenance.repository_commit ?? manifest?.repository.commit, 12)}</code></Row>
      {manifest && <Row term="Specification"><code>{manifest.specification.path}</code> + <code>{manifest.context.interface_path}</code></Row>}
      <Row term="Context mode">{label(r?.context_mode ?? manifest?.context.mode ?? '—')}</Row>
      {manifest && <Row term="Model-visible source">{manifest.context.source_files.map(f => <code key={f}>{f}</code>)}</Row>}
      {manifest && <Row term="Mutated source">{manifest.mutation.source_paths.map(f => <code key={f}>{f}</code>)}</Row>}
      {manifest && <Row term="Native tests">{manifest.tests.native_paths.map(f => <code key={f}>{f}</code>)}</Row>}
    </dl></section>

    <section aria-labelledby="ctx-gen"><h3 id="ctx-gen">Generation</h3><dl className="sg-kv">
      <Row term="Provider">{r?.generation_config.provider ?? 'fixture'}</Row>
      <Row term="Model"><code>{r?.generation_config.model ?? '—'}</code></Row>
      <Row term="Prompt configuration">{STRATEGY_LABEL[run.options.strategy] ?? run.options.strategy} <code>{run.options.strategy}</code></Row>
      <Row term="Tokens / cost">{r?.generation.input_tokens == null ? 'Not reported (fixture)' : `${r.generation.input_tokens} in · ${r.generation.output_tokens} out`}</Row>
    </dl></section>

    <section aria-labelledby="ctx-env"><h3 id="ctx-env">Execution environment</h3><dl className="sg-kv">
      <Row term="Runner image"><code title={run.image}>{shortHash(r?.provenance.runner_image_digest ?? run.image, 12)}</code></Row>
      {r && <Row term="Python">{r.provenance.python_version}</Row>}
      {r && Object.keys(r.provenance.tool_versions).length > 0 && <Row term="Tools">{['pytest', 'mutmut', 'docker', 'platform'].filter(k => r.provenance.tool_versions[k]).map(k => <span key={k} className="sg-tag">{k} {r.provenance.tool_versions[k]}</span>)}</Row>}
      {manifest && <Row term="Limits">{manifest.limits.memory_mb} MB · {manifest.limits.cpus} CPU · {manifest.limits.pids} PIDs · {manifest.tests.timeout_seconds} s test / {manifest.mutation.timeout_seconds} s mutant timeout</Row>}
      <Row term="Run deadline">{seconds(run.max_seconds)}</Row>
    </dl></section>

    <section aria-labelledby="ctx-time"><h3 id="ctx-time">Timing</h3><dl className="sg-kv">
      <Row term="Created">{timestamp(run.created_at)}</Row>
      <Row term="Queue wait">{seconds(run.queue_seconds)}</Row>
      {Object.entries(run.timings ?? {}).map(([key, value]) => <Row key={key} term={label(key)}>{seconds(value)}</Row>)}
    </dl></section>

    {r && <details className="sg-subdetails sg-hashes"><summary>Input hashes</summary><dl className="sg-kv">
      {(['manifest_sha256', 'specification_sha256', 'context_sha256', 'dependency_lock_sha256'] as const).map(key =>
        <Row key={key} term={label(key.replace('_sha256', ''))}><code className="sg-hash-full">{r.provenance[key]}</code></Row>)}
    </dl></details>}
  </div>;
}
