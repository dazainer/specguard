import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { Shield, BookOpen, Github } from 'lucide-react';
import { ProjectsPage } from './pages/ProjectsPage';
import { ProjectPage } from './pages/ProjectPage';
import { DocumentPage } from './pages/DocumentPage';

function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-layout">
      <header className="app-header">
        <div className="app-header-left">
          <Link to="/" className="app-logo">
            <div className="app-logo-icon">
              <Shield size={22} color="#0a0e14" strokeWidth={2.5} />
            </div>
            <span className="app-logo-text">SpecGuard</span>
          </Link>
          <div className="app-logo-divider" />
          <span className="app-logo-tag">AI Test Intelligence</span>
        </div>
        <div className="app-header-right">
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            className="app-header-link"
          >
            <BookOpen size={14} /> API Docs
          </a>
        </div>
      </header>

      <main className="app-main">{children}</main>

      <footer className="app-footer">
        <span>SpecGuard v0.1.0 — AI-Powered Test Intelligence</span>
        <div className="app-footer-stack">
          <span className="tech-pill">React</span>
          <span className="tech-pill">FastAPI</span>
          <span className="tech-pill">Pydantic</span>
          <span className="tech-pill">OpenAI</span>
          <span className="tech-pill">PostgreSQL</span>
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
          <Route path="/" element={<ProjectsPage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
          <Route path="/documents/:documentId" element={<DocumentPage />} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}
