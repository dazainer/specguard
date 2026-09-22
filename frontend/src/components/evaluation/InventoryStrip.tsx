import type { MutationSummary } from '../../api/evaluations';
import { OUTCOMES, OUTCOME_LABEL } from '../../evaluation/format';

/**
 * One bar per suite, one cell per mutant, drawn over the full generated inventory. Because native and
 * generated share one inventory, their strips have the same length and line up cell for cell by count:
 * the categories partition the inventory, and excluded outcomes stay visible instead of vanishing
 * from a percentage.
 */
export function InventoryStrip({ mutation, name }: { mutation: MutationSummary; name: string }) {
  const parts = OUTCOMES.filter(outcome => mutation[outcome] > 0);
  const description = `${name}: ${mutation.generated} mutants — ` +
    OUTCOMES.map(outcome => `${mutation[outcome]} ${OUTCOME_LABEL[outcome].toLowerCase()}`).join(', ');
  return <div className="sg-strip" role="img" aria-label={description} title={description}>
    {mutation.generated === 0 ? <span className="sg-strip-empty">No mutants</span> :
      parts.map(outcome => <span key={outcome} className={`sg-strip-part sg-o-${outcome}`}
        style={{ flexGrow: mutation[outcome], ['--cells' as string]: mutation[outcome] }} />)}
  </div>;
}
