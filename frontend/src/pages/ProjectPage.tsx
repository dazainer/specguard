import { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Upload, FileText, ChevronRight, Trash2, BarChart3 } from 'lucide-react';
import { api } from '../api/client';
import type { Project, DocumentListItem, ProjectStats } from '../types';

export function ProjectPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [docs, setDocs] = useState<DocumentListItem[]>([]);
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [dragging, setDragging] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    if (!projectId) return;
    try {
      const [p, d, s] = await Promise.all([
        api.projects.get(projectId),
        api.documents.list(projectId),
        api.projects.stats(projectId).catch(() => null),
      ]);
      setProject(p);
      setDocs(d);
      setStats(s);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [projectId]);

  const handleUpload = async (file: File) => {
    if (!projectId) return;
    setUploading(true);
    setUploadError('');
    try {
      await api.documents.upload(projectId, file);
      await load();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleUpload(file);
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('Delete this document and all its test suites?')) return;
    try {
      await api.documents.delete(docId);
      await load();
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) return <div className="loading"><div className="loading-spinner" /> Loading...</div>;
  if (!project) return <div className="empty-state">Project not found</div>;

  const fileTypeIcon: Record<string, string> = { txt: '📄', md: '📝', pdf: '📕' };

  return (
    <>
      <div className="breadcrumbs">
        <Link to="/">Projects</Link>
        <span className="sep">/</span>
        <span className="current">{project.name}</span>
      </div>

      <div className="page-header">
        <div>
          <h1 className="page-title">{project.name}</h1>
          {project.description && <div className="page-subtitle">{project.description}</div>}
        </div>
      </div>

      {/* Stats Dashboard */}
      {stats && stats.total_test_cases > 0 && (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-label">Documents</div>
            <div className="stat-value">{stats.total_documents}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Requirements</div>
            <div className="stat-value stat-accent">{stats.total_requirements}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Test Cases</div>
            <div className="stat-value stat-amber">{stats.total_test_cases}</div>
          </div>
          <div className="stat-card">
            <div className="stat-label">Avg Coverage</div>
            <div className="stat-value">
              {stats.avg_coverage_score !== null
                ? `${Math.round(stats.avg_coverage_score * 100)}%`
                : '—'}
            </div>
          </div>
          {Object.keys(stats.test_type_breakdown).length > 0 && (
            <div className="stat-card">
              <div className="stat-label">Test Breakdown</div>
              <div style={{ display: 'flex', gap: 8, marginTop: 6, flexWrap: 'wrap' }}>
                {stats.test_type_breakdown.functional != null && (
                  <span className="badge badge-functional">{stats.test_type_breakdown.functional} func</span>
                )}
                {stats.test_type_breakdown.edge_case != null && (
                  <span className="badge badge-edge_case">{stats.test_type_breakdown.edge_case} edge</span>
                )}
                {stats.test_type_breakdown.negative != null && (
                  <span className="badge badge-negative">{stats.test_type_breakdown.negative} neg</span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Upload Zone */}
      <div
        className={`upload-zone ${dragging ? 'dragging' : ''}`}
        onClick={() => fileRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileRef}
          type="file"
          accept=".txt,.md,.pdf"
          style={{ display: 'none' }}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleUpload(f);
            e.target.value = '';
          }}
        />
        <div className="upload-zone-icon"><Upload size={28} /></div>
        {uploading ? (
          <div className="upload-zone-text">Uploading...</div>
        ) : (
          <>
            <div className="upload-zone-text">Drop a spec file here or click to upload</div>
            <div className="upload-zone-hint">.txt, .md, .pdf — max 5MB</div>
          </>
        )}
      </div>

      {uploadError && (
        <div style={{ color: 'var(--red)', fontSize: 13, fontFamily: 'var(--font-mono)', marginTop: 8 }}>
          {uploadError}
        </div>
      )}

      {/* Documents Section */}
      <div className="section-header">
        <div className="section-title">
          <FileText size={14} />
          Documents
          <span className="section-count">{docs.length}</span>
        </div>
        <div className="section-line" />
      </div>

      {docs.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon"><FileText size={36} /></div>
          <div className="empty-state-text">No documents yet. Upload a spec to get started.</div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {docs.map((doc) => (
            <div key={doc.id} className="card card-accent" style={{ padding: '14px 20px' }}>
              <div className="flex-between">
                <Link
                  to={`/documents/${doc.id}`}
                  style={{ textDecoration: 'none', color: 'inherit', display: 'flex', alignItems: 'center', gap: 12, flex: 1 }}
                >
                  <span style={{ fontSize: 20 }}>{fileTypeIcon[doc.file_type] || '📄'}</span>
                  <div style={{ flex: 1 }}>
                    <div className="card-title" style={{ marginBottom: 2 }}>{doc.filename}</div>
                    <div className="card-meta">
                      <span>{doc.requirement_count} requirements</span>
                      <span>{new Date(doc.uploaded_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                  <ChevronRight size={16} color="var(--text-muted)" />
                </Link>
                <button
                  className="btn btn-sm btn-ghost btn-danger"
                  onClick={() => handleDelete(doc.id)}
                  style={{ marginLeft: 8 }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
