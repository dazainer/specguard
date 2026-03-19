import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FolderOpen, Plus, FileText, ChevronRight, Shield, FileSearch, Cpu, CheckCircle2, BarChart3 } from 'lucide-react';
import { api } from '../api/client';
import type { ProjectListItem } from '../types';
import { CreateProjectModal } from '../components/CreateProjectModal';

export function ProjectsPage() {
  const [projects, setProjects] = useState<ProjectListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const load = async () => {
    try {
      const data = await api.projects.list();
      setProjects(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const totalDocs = projects.reduce((sum, p) => sum + p.document_count, 0);

  return (
    <>
      {loading ? (
        <div className="loading"><div className="loading-spinner" /> Loading projects...</div>
      ) : projects.length === 0 ? (
        /* ── Welcome State ── */
        <>
          <div className="welcome-hero">
            <div className="welcome-icon">
              <Shield size={30} color="var(--accent)" />
            </div>
            <h1 className="welcome-title">Welcome to SpecGuard</h1>
            <p className="welcome-subtitle">
              Upload product specs, feature docs, or API documentation — and generate
              comprehensive, schema-validated test suites powered by AI.
            </p>
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
              <Plus size={16} /> Create Your First Project
            </button>
          </div>

          {/* Pipeline Visual */}
          <div className="section-header" style={{ marginTop: 20 }}>
            <div className="section-title">How It Works</div>
            <div className="section-line" />
          </div>

          <div className="pipeline-visual">
            <div className="pipeline-step">
              <div className="pipeline-step-number">1</div>
              <div className="pipeline-step-icon"><FileSearch size={20} color="var(--accent)" /></div>
              <div className="pipeline-step-title">Upload Spec</div>
              <div className="pipeline-step-desc">Upload .txt, .md, or .pdf product specs</div>
            </div>
            <div className="pipeline-step">
              <div className="pipeline-step-number">2</div>
              <div className="pipeline-step-icon"><Cpu size={20} color="var(--amber)" /></div>
              <div className="pipeline-step-title">Extract</div>
              <div className="pipeline-step-desc">AI extracts individual testable requirements</div>
            </div>
            <div className="pipeline-step">
              <div className="pipeline-step-number">3</div>
              <div className="pipeline-step-icon"><CheckCircle2 size={20} color="var(--green)" /></div>
              <div className="pipeline-step-title">Generate</div>
              <div className="pipeline-step-desc">Generate functional, edge case, and negative tests</div>
            </div>
            <div className="pipeline-step">
              <div className="pipeline-step-number">4</div>
              <div className="pipeline-step-icon"><BarChart3 size={20} color="var(--purple)" /></div>
              <div className="pipeline-step-title">Validate & Score</div>
              <div className="pipeline-step-desc">Schema validation + coverage scoring</div>
            </div>
          </div>

          <div style={{
            textAlign: 'center', padding: '16px 20px',
            background: 'var(--bg-card)', border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)', fontFamily: 'var(--font-mono)',
            fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.6,
          }}>
            Every AI output is validated against Pydantic schemas with automatic retry logic.
            <br />
            Invalid or malformed outputs are rejected and regenerated — ensuring reliable, structured test suites.
          </div>
        </>
      ) : (
        /* ── Projects Dashboard ── */
        <>
          <div className="page-header">
            <div>
              <h1 className="page-title">Projects</h1>
              <div className="page-subtitle">Organize your specs and generate test suites</div>
            </div>
            <button className="btn btn-primary" onClick={() => setShowCreate(true)}>
              <Plus size={16} /> New Project
            </button>
          </div>

          {/* Summary Stats */}
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-label">Projects</div>
              <div className="stat-value stat-accent">{projects.length}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Total Documents</div>
              <div className="stat-value">{totalDocs}</div>
            </div>
            <div className="stat-card">
              <div className="stat-label">Pipeline Status</div>
              <div className="stat-value stat-amber" style={{ fontSize: 16, marginTop: 4 }}>Ready</div>
            </div>
          </div>

          {/* Section Header */}
          <div className="section-header">
            <div className="section-title">
              <FolderOpen size={14} />
              All Projects
              <span className="section-count">{projects.length}</span>
            </div>
            <div className="section-line" />
          </div>

          {/* Project Cards */}
          <div className="card-grid">
            {projects.map((p) => (
              <Link key={p.id} to={`/projects/${p.id}`} className="card-link">
                <div className="card card-accent">
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
                    <div style={{ flex: 1 }}>
                      <div className="card-title">{p.name}</div>
                      {p.description && (
                        <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.5 }}>
                          {p.description}
                        </div>
                      )}
                      <div className="card-meta" style={{ marginTop: p.description ? 0 : 10 }}>
                        <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          <FileText size={12} /> {p.document_count} {p.document_count === 1 ? 'doc' : 'docs'}
                        </span>
                        <span>{new Date(p.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>
                    <ChevronRight size={18} color="var(--text-muted)" style={{ marginTop: 2, flexShrink: 0 }} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}

      {showCreate && (
        <CreateProjectModal
          onClose={() => setShowCreate(false)}
          onCreate={() => { setShowCreate(false); load(); }}
        />
      )}
    </>
  );
}
