import { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Play, Download, Filter, RefreshCw, List, AlertTriangle, CheckCircle2, Clock, Cpu } from 'lucide-react';
import { api } from '../api/client';
import type {
  Document,
  Requirement,
  TestSuiteListItem,
  TestSuite,
  TestCase,
  GenerationStatus,
} from '../types';
import { ScoreRing } from '../components/ScoreRing';
import { TestCaseCard } from '../components/TestCaseCard';

export function DocumentPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const [doc, setDoc] = useState<Document | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [suites, setSuites] = useState<TestSuiteListItem[]>([]);
  const [activeSuite, setActiveSuite] = useState<TestSuite | null>(null);
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [generating, setGenerating] = useState(false);
  const [genStatus, setGenStatus] = useState<GenerationStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [typeFilter, setTypeFilter] = useState<string | null>(null);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!documentId) return;
    try {
      const [d, reqs, sl] = await Promise.all([
        api.documents.get(documentId),
        api.generation.requirements(documentId).catch(() => []),
        api.testSuites.list(documentId).catch(() => []),
      ]);
      setDoc(d);
      setRequirements(reqs);
      setSuites(sl);

      const latest = sl.find((s) => s.status === 'completed');
      if (latest) {
        const [suite, tcs] = await Promise.all([
          api.testSuites.get(latest.id),
          api.testSuites.testCases(latest.id),
        ]);
        setActiveSuite(suite);
        setTestCases(tcs);
      }

      const genSuite = sl.find((s) => s.status === 'generating');
      if (genSuite) {
        setGenerating(true);
        pollStatus();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => { load(); }, [load]);

  const pollStatus = useCallback(async () => {
    if (!documentId) return;
    const poll = async () => {
      try {
        const status = await api.generation.status(documentId);
        setGenStatus(status);
        if (status.status === 'generating') {
          setTimeout(poll, 2000);
        } else {
          setGenerating(false);
          setGenStatus(null);
          await load();
        }
      } catch {
        setGenerating(false);
      }
    };
    poll();
  }, [documentId, load]);

  const handleGenerate = async () => {
    if (!documentId) return;
    setError('');
    try {
      await api.generation.start(documentId);
      setGenerating(true);
      pollStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Generation failed');
    }
  };

  const handleLoadSuite = async (suiteId: string) => {
    try {
      const [suite, tcs] = await Promise.all([
        api.testSuites.get(suiteId),
        api.testSuites.testCases(suiteId),
      ]);
      setActiveSuite(suite);
      setTestCases(tcs);
      setTypeFilter(null);
    } catch (e) {
      console.error(e);
    }
  };

  const handleTestCaseUpdate = (updated: TestCase) => {
    setTestCases((prev) => prev.map((tc) => (tc.id === updated.id ? updated : tc)));
  };

  const filteredCases = typeFilter
    ? testCases.filter((tc) => tc.test_type === typeFilter)
    : testCases;

  const typeCounts = {
    all: testCases.length,
    functional: testCases.filter((tc) => tc.test_type === 'functional').length,
    edge_case: testCases.filter((tc) => tc.test_type === 'edge_case').length,
    negative: testCases.filter((tc) => tc.test_type === 'negative').length,
  };

  if (loading) return <div className="loading"><div className="loading-spinner" /> Loading document...</div>;
  if (!doc) return <div className="empty-state">Document not found</div>;

  return (
    <>
      <div className="breadcrumbs">
        <Link to="/">Projects</Link>
        <span className="sep">/</span>
        <Link to={`/projects/${doc.project_id}`}>Project</Link>
        <span className="sep">/</span>
        <span className="current">{doc.filename}</span>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">{doc.filename}</h1>
          <div className="page-subtitle">
            {doc.file_type.toUpperCase()} · {requirements.length} requirements · {suites.length} generation{suites.length !== 1 ? 's' : ''}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {activeSuite && (
            <>
              <a href={api.testSuites.export(activeSuite.id, 'json')} className="btn" target="_blank">
                <Download size={14} /> JSON
              </a>
              <a href={api.testSuites.export(activeSuite.id, 'md')} className="btn" target="_blank">
                <Download size={14} /> Markdown
              </a>
            </>
          )}
          <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
            {generating ? (
              <><RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} /> Generating...</>
            ) : suites.length > 0 ? (
              <><RefreshCw size={14} /> Regenerate</>
            ) : (
              <><Play size={14} /> Generate Tests</>
            )}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ color: 'var(--red)', fontSize: 13, fontFamily: 'var(--font-mono)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* Generating Progress */}
      {generating && (
        <div className="card" style={{ marginBottom: 24, borderColor: 'var(--amber-mid)' }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--amber)', display: 'flex', alignItems: 'center', gap: 8 }}>
            <RefreshCw size={14} style={{ animation: 'spin 1s linear infinite' }} />
            Pipeline running — extracting requirements and generating tests...
          </div>
          <div className="pulse-bar"><div className="pulse-bar-inner" /></div>
          {genStatus && (
            <div className="card-meta">
              <span>Status: {genStatus.status}</span>
              {genStatus.test_case_count > 0 && <span>{genStatus.test_case_count} test cases generated</span>}
            </div>
          )}
        </div>
      )}

      {/* Document Info Bar */}
      {activeSuite && activeSuite.metadata_ && (
        <div className="info-row">
          <div className="info-row-item">
            <Cpu size={13} color="var(--accent)" />
            <span>Model:</span>
            <span className="info-row-value">{activeSuite.metadata_.model}</span>
          </div>
          <div className="info-row-divider" />
          <div className="info-row-item">
            <Clock size={13} color="var(--amber)" />
            <span>Generation:</span>
            <span className="info-row-value">{activeSuite.metadata_.generation_time_seconds}s</span>
          </div>
          <div className="info-row-divider" />
          <div className="info-row-item">
            <span>Pipeline:</span>
            <span className="info-row-value">Parse → Extract → Generate → Validate</span>
          </div>
        </div>
      )}

      {/* Requirements Section */}
      {requirements.length > 0 && (
        <>
          <div className="section-header" style={{ marginTop: activeSuite ? 12 : 36 }}>
            <div className="section-title">
              <List size={14} />
              Extracted Requirements
              <span className="section-count">{requirements.length}</span>
            </div>
            <div className="section-line" />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 8 }}>
            {requirements.map((req, i) => (
              <div key={req.id} className="card" style={{ padding: '10px 16px', display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                <span style={{
                  fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600,
                  color: 'var(--accent)', background: 'var(--accent-dim)',
                  padding: '2px 8px', borderRadius: 4, flexShrink: 0, marginTop: 1,
                }}>
                  R{i + 1}
                </span>
                <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5 }}>{req.requirement_text}</div>
                <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                  <span className={`badge badge-${req.priority}`}>{req.priority}</span>
                  <span className="tag">{req.category}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Test Suite Results */}
      {activeSuite && (
        <>
          <div className="section-header" style={{ marginTop: 40 }}>
            <div className="section-title">
              <CheckCircle2 size={14} />
              Test Suite Results
            </div>
            <div className="section-line" />
          </div>

          <div className="score-block">
            {activeSuite.coverage_score !== null && (
              <ScoreRing score={activeSuite.coverage_score} size={80} strokeWidth={6} />
            )}
            <div className="score-block-details" style={{ flex: 1 }}>
              <h2>
                Test Suite v{activeSuite.version}
                <span className={`badge badge-${activeSuite.status}`}>{activeSuite.status}</span>
              </h2>
              <div className="card-meta" style={{ marginTop: 6 }}>
                <span>{testCases.length} test cases</span>
                {activeSuite.metadata_ && (
                  <span>{activeSuite.metadata_.total_requirements} requirements covered</span>
                )}
              </div>
              {activeSuite.score_breakdown && (
                <div style={{ display: 'flex', gap: 16, marginTop: 10 }}>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Req Coverage </span>
                    <span style={{ color: 'var(--accent)', fontWeight: 600 }}>
                      {Math.round(activeSuite.score_breakdown.requirement_coverage * 100)}%
                    </span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Edge Cases </span>
                    <span style={{ color: 'var(--yellow)', fontWeight: 600 }}>
                      {activeSuite.score_breakdown.edge_case_count}
                    </span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Negative Tests </span>
                    <span style={{ color: 'var(--red)', fontWeight: 600 }}>
                      {activeSuite.score_breakdown.negative_test_count}
                    </span>
                  </div>
                  <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Step Completeness </span>
                    <span style={{ color: 'var(--green)', fontWeight: 600 }}>
                      {Math.round(activeSuite.score_breakdown.step_completeness * 100)}%
                    </span>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Version Picker */}
          {suites.filter(s => s.status === 'completed').length > 1 && (
            <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
              {suites.filter((s) => s.status === 'completed').map((s) => (
                <button
                  key={s.id}
                  className={`filter-btn ${s.id === activeSuite.id ? 'active' : ''}`}
                  onClick={() => handleLoadSuite(s.id)}
                >
                  v{s.version} ({s.test_case_count})
                </button>
              ))}
            </div>
          )}

          {/* Filter Bar */}
          <div className="filter-bar">
            <Filter size={14} color="var(--text-muted)" />
            <button className={`filter-btn ${!typeFilter ? 'active' : ''}`} onClick={() => setTypeFilter(null)}>
              All ({typeCounts.all})
            </button>
            <button className={`filter-btn ${typeFilter === 'functional' ? 'active' : ''}`} onClick={() => setTypeFilter('functional')}>
              Functional ({typeCounts.functional})
            </button>
            <button className={`filter-btn ${typeFilter === 'edge_case' ? 'active' : ''}`} onClick={() => setTypeFilter('edge_case')}>
              Edge Cases ({typeCounts.edge_case})
            </button>
            <button className={`filter-btn ${typeFilter === 'negative' ? 'active' : ''}`} onClick={() => setTypeFilter('negative')}>
              Negative ({typeCounts.negative})
            </button>
          </div>

          {/* Test Cases */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {filteredCases.map((tc) => (
              <TestCaseCard key={tc.id} tc={tc} onUpdate={handleTestCaseUpdate} />
            ))}
          </div>

          {filteredCases.length === 0 && (
            <div className="empty-state">
              <div className="empty-state-text">No test cases match the current filter.</div>
            </div>
          )}
        </>
      )}

      {/* No suite yet and not generating */}
      {!activeSuite && !generating && requirements.length === 0 && (
        <div className="empty-state" style={{ marginTop: 32 }}>
          <div className="empty-state-icon"><Play size={40} color="var(--accent)" /></div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 15, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
            Ready to generate
          </div>
          <div className="empty-state-text">
            Click "Generate Tests" to run the AI pipeline on this document.
          </div>
        </div>
      )}
    </>
  );
}
