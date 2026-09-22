import type { EvaluationRun } from '../../api/evaluations';
import { STAGES, STAGE_LABEL, TERMINAL, seconds } from '../../evaluation/format';

type NodeState = 'done' | 'current' | 'stopped' | 'skipped' | 'upcoming';

/**
 * The worker's real lifecycle, from recorded events. Order matters here: a failed or cancelled run
 * shows the stage it stopped at, and a baseline-only run shows mutation as skipped rather than missing.
 */
export function StageTrack({ run }: { run: EvaluationRun }) {
  const events = run.events ?? [];
  const firstAt = new Map<string, number>();
  for (const event of events) if (!firstAt.has(event.stage)) firstAt.set(event.stage, event.at);
  const terminal = TERMINAL.has(run.status);
  const reached = STAGES.filter(stage => firstAt.has(stage));
  const last = reached[reached.length - 1];
  const origin = run.created_at;

  const nodes = STAGES.map(stage => {
    let state: NodeState = 'upcoming';
    if (stage === 'mutating' && run.options.baseline_only) state = 'skipped';
    else if (!terminal && stage === run.status) state = 'current';
    else if (terminal && run.status !== 'completed' && stage === last) state = 'stopped';
    else if (firstAt.has(stage)) state = 'done';
    return { stage, state, at: firstAt.get(stage) };
  });
  const end = terminal ? run.status : null;

  return <ol className="sg-track" aria-label="Evaluation progress">
    {nodes.map(({ stage, state, at }) => <li key={stage} className={`sg-track-node is-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
      <span className="sg-track-dot" aria-hidden="true" />
      <span className="sg-track-name">{STAGE_LABEL[stage]}</span>
      <span className="sg-track-meta">
        {state === 'skipped' ? 'Skipped · baseline only' : state === 'stopped' ? `Stopped here · +${seconds(at! - origin)}` :
          state === 'current' ? 'In progress' : at != null ? `+${seconds(at - origin)}` : 'Not reached'}
      </span>
    </li>)}
    <li className={`sg-track-node is-end is-${end ?? 'upcoming'}`}>
      <span className="sg-track-dot" aria-hidden="true" />
      <span className="sg-track-name">{end ? STAGE_LABEL[end] : 'Result'}</span>
      <span className="sg-track-meta">{end && run.finished_at ? `+${seconds(run.finished_at - origin)}` : 'Pending'}</span>
    </li>
  </ol>;
}
