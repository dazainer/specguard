import type {
  Project,
  ProjectListItem,
  Document,
  DocumentListItem,
  Requirement,
  TestSuiteListItem,
  TestSuite,
  TestCase,
  GenerationStatus,
  ProjectStats,
} from '../types';

const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// ── Projects ────────────────────────────────
export const api = {
  projects: {
    list: () => request<ProjectListItem[]>('/projects'),
    get: (id: string) => request<Project>(`/projects/${id}`),
    create: (name: string, description?: string) =>
      request<Project>('/projects', {
        method: 'POST',
        body: JSON.stringify({ name, description }),
      }),
    update: (id: string, data: { name?: string; description?: string }) =>
      request<Project>(`/projects/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<void>(`/projects/${id}`, { method: 'DELETE' }),
    stats: (id: string) => request<ProjectStats>(`/projects/${id}/stats`),
  },

  // ── Documents ───────────────────────────────
  documents: {
    list: (projectId: string) =>
      request<DocumentListItem[]>(`/projects/${projectId}/documents`),
    get: (id: string) => request<Document>(`/documents/${id}`),
    upload: async (projectId: string, file: File): Promise<Document> => {
      const form = new FormData();
      form.append('file', file);
      const res = await fetch(`${BASE}/projects/${projectId}/documents`, {
        method: 'POST',
        body: form,
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(body.detail || 'Upload failed');
      }
      return res.json();
    },
    delete: (id: string) =>
      request<void>(`/documents/${id}`, { method: 'DELETE' }),
  },

  // ── Generation ──────────────────────────────
  generation: {
    start: (documentId: string) =>
      request<{ test_suite_id: string; status: string; message: string }>(
        `/documents/${documentId}/generate`,
        { method: 'POST' }
      ),
    status: (documentId: string) =>
      request<GenerationStatus>(`/documents/${documentId}/generate/status`),
    requirements: (documentId: string) =>
      request<Requirement[]>(`/documents/${documentId}/requirements`),
  },

  // ── Test Suites ─────────────────────────────
  testSuites: {
    list: (documentId: string) =>
      request<TestSuiteListItem[]>(`/documents/${documentId}/test-suites`),
    get: (id: string) => request<TestSuite>(`/test-suites/${id}`),
    testCases: (suiteId: string, filters?: { test_type?: string; status?: string; priority?: string }) => {
      const params = new URLSearchParams();
      if (filters?.test_type) params.set('test_type', filters.test_type);
      if (filters?.status) params.set('status', filters.status);
      if (filters?.priority) params.set('priority', filters.priority);
      const qs = params.toString();
      return request<TestCase[]>(`/test-suites/${suiteId}/test-cases${qs ? `?${qs}` : ''}`);
    },
    export: (suiteId: string, format: 'json' | 'md' = 'json') =>
      `${BASE}/test-suites/${suiteId}/export?format=${format}`,
  },

  // ── Test Cases ──────────────────────────────
  testCases: {
    update: (id: string, data: Partial<Pick<TestCase, 'status' | 'title' | 'description' | 'steps' | 'expected_result' | 'priority'>>) =>
      request<TestCase>(`/test-cases/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(data),
      }),
  },
};
