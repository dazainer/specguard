import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Shield, BookOpen } from 'lucide-react';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectPage } from './pages/ProjectPage';
import { DocumentPage } from './pages/DocumentPage';
import { EvaluationsPage, EvaluationPage } from './pages/EvaluationsPage';

function AppLayout({ children }: { children: React.ReactNode }) {
  const { pathname } = useLocation();
  const evaluationsActive = pathname === '/' || pathname.startsWith('/evaluations');
  const manualActive = pathname.startsWith('/projects') || pathname.startsWith('/documents');
  return (
    <div className="app-layout">
      <a href="#main" className="skip-link">Skip to content</a>
      <header className="app-header">
        <div className="app-header-left">
          <Link to="/" className="app-logo" aria-label="SpecGuard evaluations home">
            <div className="app-logo-icon" aria-hidden="true">
              <Shield size={22} color="#0a0e14" strokeWidth={2.5} />
            </div>
            <span className="app-logo-text">SpecGuard</span>
          </Link>
          <div className="app-logo-divider" aria-hidden="true" />
          <span className="app-logo-tag">Executable evaluation</span>
        </div>
        <nav className="app-header-right" aria-label="Primary">
          <Link to="/" className="app-header-link" aria-current={evaluationsActive ? 'page' : undefined}>Evaluations</Link>
          <Link to="/projects" className="app-header-link" aria-current={manualActive ? 'page' : undefined}>Manual QA</Link>
          <a
            href={import.meta.env.VITE_API_DOCS_URL || 'http://localhost:8000/docs'}
            target="_blank"
            rel="noreferrer"
            className="app-header-link"
          >
            <BookOpen size={14} aria-hidden="true" /> API docs<span className="sg-sr"> (opens in a new tab)</span>
          </a>
        </nav>
      </header>

      <main id="main" className="app-main" tabIndex={-1}>{children}</main>

      <footer className="app-footer">
        <span>SpecGuard — Executable test evaluation</span>
        <div className="app-footer-stack">
          <span className="tech-pill">React</span>
          <span className="tech-pill">FastAPI</span>
          <span className="tech-pill">Pydantic</span>
          <span className="tech-pill">Docker</span>
          <span className="tech-pill">SQLite</span>
        </div>
      </footer>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/" element={<EvaluationsPage />} />
          <Route path="/evaluations/:runId" element={<EvaluationPage />} />
          <Route path="/projects" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
          <Route path="/documents/:documentId" element={<DocumentPage />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}
