import { AlertTriangle, Ban, CheckCircle2, CircleDashed, Clock, Loader, XCircle, type LucideIcon } from 'lucide-react';
import { OUTCOME_LABEL, STAGE_LABEL, label, type Outcome } from '../../evaluation/format';

const STATUS_ICON: Record<string, LucideIcon> = {
  completed: CheckCircle2, failed: XCircle, cancelled: Ban, queued: Clock,
};

/** Run lifecycle state. Text always accompanies the icon and colour. */
export function RunStatus({ status }: { status: string }) {
  const Icon = STATUS_ICON[status] ?? Loader;
  const tone = status === 'completed' ? 'ok' : status === 'failed' ? 'bad' : status === 'cancelled' ? 'warn' : status === 'queued' ? 'idle' : 'active';
  return <span className={`sg-status sg-tone-${tone}`}>
    <Icon size={13} aria-hidden="true" className={tone === 'active' ? 'sg-spin' : undefined} />
    {STAGE_LABEL[status] ?? label(status)}
  </span>;
}

/** A mutant outcome. The swatch colour matches the inventory strip; the text label carries the meaning. */
export function OutcomeBadge({ outcome, compact = false }: { outcome: string; compact?: boolean }) {
  const known = outcome in OUTCOME_LABEL;
  return <span className={`sg-outcome sg-o-${known ? outcome : 'unknown'}${compact ? ' sg-outcome-compact' : ''}`}>
    <span className="sg-swatch" aria-hidden="true" />
    {known ? OUTCOME_LABEL[outcome as Outcome] : label(outcome)}
  </span>;
}

/** Execution result from the container runner (collection or baseline). */
export function ExecStatus({ status }: { status: string }) {
  const ok = status === 'passed';
  const Icon = ok ? CheckCircle2 : status === 'timeout' ? Clock : status === 'not_run' ? CircleDashed : AlertTriangle;
  return <span className={`sg-exec ${ok ? 'sg-tone-ok' : status === 'not_run' ? 'sg-tone-idle' : 'sg-tone-bad'}`}>
    <Icon size={13} aria-hidden="true" />{label(status)}
  </span>;
}

export function FixtureBadge() {
  return <span className="sg-fixture" title="Handwritten fixture tests stand in for model output. They demonstrate the pipeline, not AI test quality.">
    Fixture · not model output
  </span>;
}
