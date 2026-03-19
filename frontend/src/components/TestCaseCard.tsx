import { Check, X } from 'lucide-react';
import type { TestCase } from '../types';
import { api } from '../api/client';

interface TestCaseCardProps {
  tc: TestCase;
  onUpdate: (updated: TestCase) => void;
}

export function TestCaseCard({ tc, onUpdate }: TestCaseCardProps) {
  const handleStatus = async (status: 'approved' | 'rejected') => {
    try {
      const updated = await api.testCases.update(tc.id, { status });
      onUpdate(updated);
    } catch (e) {
      console.error('Failed to update test case:', e);
    }
  };

  return (
    <div className="tc-card">
      <div className="tc-header">
        <div className="tc-title">{tc.title}</div>
        <div className="tc-badges">
          <span className={`badge badge-${tc.test_type}`}>{tc.test_type.replace('_', ' ')}</span>
          <span className={`badge badge-${tc.priority}`}>{tc.priority}</span>
        </div>
      </div>

      <div className="tc-body">
        <div className="tc-description">{tc.description}</div>

        {tc.preconditions && tc.preconditions !== 'None' && (
          <>
            <div className="tc-section-label">Preconditions</div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{tc.preconditions}</div>
          </>
        )}

        <div className="tc-section-label">Steps</div>
        <ol className="tc-steps">
          {tc.steps.map((step, i) => (
            <li key={i}>{step}</li>
          ))}
        </ol>

        <div className="tc-section-label">Expected Result</div>
        <div className="tc-expected">{tc.expected_result}</div>
      </div>

      <div className="tc-footer">
        <div className="tc-tags">
          {tc.tags.map((tag) => (
            <span key={tag} className="tag">{tag}</span>
          ))}
        </div>
        <div className="tc-actions">
          <span className={`badge badge-${tc.status}`} style={{ marginRight: 8 }}>
            {tc.status}
          </span>
          {tc.status === 'generated' && (
            <>
              <button className="btn btn-sm btn-ghost" onClick={() => handleStatus('approved')} title="Approve">
                <Check size={14} color="var(--green)" />
              </button>
              <button className="btn btn-sm btn-ghost" onClick={() => handleStatus('rejected')} title="Reject">
                <X size={14} color="var(--red)" />
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
