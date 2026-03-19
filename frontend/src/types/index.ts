// ──────────────────────────────────────────────
// Project
// ──────────────────────────────────────────────
export interface Project {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
  document_count: number;
  total_test_cases: number;
}

export interface ProjectListItem {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  document_count: number;
}

// ──────────────────────────────────────────────
// Document
// ──────────────────────────────────────────────
export interface Document {
  id: string;
  project_id: string;
  filename: string;
  file_type: string;
  raw_text: string;
  uploaded_at: string;
  requirement_count: number;
  test_suite_count: number;
}

export interface DocumentListItem {
  id: string;
  filename: string;
  file_type: string;
  uploaded_at: string;
  requirement_count: number;
}

// ──────────────────────────────────────────────
// Requirement
// ──────────────────────────────────────────────
export interface Requirement {
  id: string;
  requirement_text: string;
  category: string;
  priority: string;
  order_index: number;
}

// ──────────────────────────────────────────────
// Test Suite
// ──────────────────────────────────────────────
export interface TestSuiteListItem {
  id: string;
  version: number;
  status: string;
  coverage_score: number | null;
  created_at: string;
  test_case_count: number;
}

export interface TestSuite {
  id: string;
  document_id: string;
  version: number;
  status: string;
  coverage_score: number | null;
  score_breakdown: ScoreBreakdown | null;
  metadata_: GenerationMetadata | null;
  error_message: string | null;
  created_at: string;
}

export interface ScoreBreakdown {
  overall: number;
  requirement_coverage: number;
  edge_case_ratio: number;
  negative_test_ratio: number;
  step_completeness: number;
  total_test_cases: number;
  total_requirements: number;
  edge_case_count: number;
  negative_test_count: number;
}

export interface GenerationMetadata {
  total_requirements: number;
  total_test_cases: number;
  generation_time_seconds: number;
  model: string;
}

// ──────────────────────────────────────────────
// Test Case
// ──────────────────────────────────────────────
export interface TestCase {
  id: string;
  test_suite_id: string;
  requirement_id: string | null;
  title: string;
  description: string;
  test_type: 'functional' | 'edge_case' | 'negative';
  preconditions: string;
  steps: string[];
  expected_result: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  status: 'generated' | 'approved' | 'rejected' | 'edited';
  tags: string[];
}

// ──────────────────────────────────────────────
// Generation
// ──────────────────────────────────────────────
export interface GenerationStatus {
  test_suite_id: string;
  status: 'generating' | 'completed' | 'failed';
  coverage_score: number | null;
  test_case_count: number;
  error_message: string | null;
}

// ──────────────────────────────────────────────
// Stats
// ──────────────────────────────────────────────
export interface ProjectStats {
  project_id: string;
  project_name: string;
  total_documents: number;
  total_requirements: number;
  total_test_suites: number;
  total_test_cases: number;
  avg_coverage_score: number | null;
  test_type_breakdown: Record<string, number>;
  status_breakdown: Record<string, number>;
  recent_generations: TestSuiteListItem[];
}
