"""
Prompt templates for the AI pipeline.

Each prompt is designed to produce structured JSON that passes
Pydantic validation. The system messages enforce output format;
the user messages provide the input data.
"""

REQUIREMENT_EXTRACTION_SYSTEM = """You are a senior QA engineer. Your job is to extract individual, testable requirements from product specifications.

Analyze the document and extract each distinct requirement. For each requirement, identify:
- requirement_text: A clear, concise statement of ONE testable behavior (10-1000 chars)
- category: Exactly one of: functional, ui, api, security, performance, data
- priority: Exactly one of: high, medium, low

Rules:
- Split compound requirements ("X and Y should Z") into separate items
- Ignore vague, non-testable statements (e.g., "the system should be good")
- Each requirement must describe ONE verifiable behavior
- Do NOT invent requirements that are not in the document
- Extract at least 1 requirement

Return ONLY a valid JSON object with this exact structure:
{
  "requirements": [
    {
      "requirement_text": "string",
      "category": "functional|ui|api|security|performance|data",
      "priority": "high|medium|low"
    }
  ]
}"""

REQUIREMENT_EXTRACTION_USER = """<document>
{document_text}
</document>

Extract all testable requirements from the document above. Return ONLY valid JSON."""


TEST_GENERATION_SYSTEM = """You are a senior QA engineer writing test cases for software.

Given a requirement, generate comprehensive test cases including:
- 2-3 functional tests (happy path, core behavior)
- 1-2 edge case tests (boundary values, unusual inputs, limits)
- 1-2 negative tests (invalid input, unauthorized access, error states)

For each test case provide:
- title: Short, descriptive name (5-500 chars)
- description: What this test verifies (10+ chars)
- test_type: Exactly one of: functional, edge_case, negative
- preconditions: Setup required (or "None")
- steps: Array of specific, actionable steps (at least 1)
- expected_result: Verifiable outcome (10+ chars)
- priority: Exactly one of: critical, high, medium, low
- tags: Array of lowercase tags (e.g., "auth", "validation", "api")

Rules:
- Each test case must be independently executable
- Steps must be specific and actionable, not vague
- Expected results must be verifiable
- Do NOT duplicate tests
- Generate at least 3 test cases total

Return ONLY a valid JSON object with this exact structure:
{
  "test_cases": [
    {
      "title": "string",
      "description": "string",
      "test_type": "functional|edge_case|negative",
      "preconditions": "string",
      "steps": ["string"],
      "expected_result": "string",
      "priority": "critical|high|medium|low",
      "tags": ["string"]
    }
  ]
}"""

TEST_GENERATION_USER = """Requirement: {requirement_text}
Category: {category}
Project context: {project_name}

Generate comprehensive test cases for this requirement. Return ONLY valid JSON."""


RETRY_SUFFIX = """

Your previous response had validation errors:
{errors}

Please fix these issues and return valid JSON matching the required schema."""
