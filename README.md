# SpecGuard: AI Test Intelligence Platform

An AI-powered internal engineering tool that ingests product specifications and generates **schema-validated test suites** with functional tests, edge cases, negative tests, and coverage analysis.

Built with a multi-stage processing pipeline: document parsing → requirement extraction → test generation → validation → coverage scoring.

## Architecture

```
React + TypeScript frontend
        │
        ▼  REST API
Python + FastAPI backend
   │         │
   │    AI Pipeline (4 stages)
   │    ├── Parse document
   │    ├── Extract requirements (OpenAI)
   │    ├── Generate tests per requirement (OpenAI)
   │    └── Validate (Pydantic) + Score
   │
   └── PostgreSQL / SQLite
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, Vite, Lucide Icons |
| Backend | Python, FastAPI, Pydantic v2, SQLAlchemy 2.0 |
| Database | PostgreSQL (prod) / SQLite (dev) |
| AI | OpenAI gpt-4o-mini, structured JSON output |
| Testing | pytest |

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- An OpenAI API key

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
cp ../.env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start the server
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000` with auto-generated Swagger docs at `/docs`.

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173` and proxies API requests to the backend.

### Run Tests

```bash
cd backend
pytest tests/ -v
```

## How It Works

1. **Upload a spec** — feature spec, user story, API docs, or release notes (.txt, .md, .pdf)
2. **Extract requirements** — AI parses the document into individual testable requirements, validated against a Pydantic schema
3. **Generate test cases** — For each requirement, AI generates functional tests, edge cases, and negative tests with retry logic on validation failure
4. **Score and review** — Coverage score computed across 4 heuristics; review, approve/reject, and export test cases

## Key Engineering Decisions

- **Multi-stage pipeline** over single-prompt generation for better reliability and debuggability
- **Pydantic schema validation** on every AI output with automatic retry + error feedback
- **Per-requirement generation** to reduce hallucination (smaller context per call)
- **Coverage scoring** as a heuristic quality metric (requirement coverage, edge case density, negative test ratio, step completeness)
- **SQLite for development** with PostgreSQL-compatible schema for production

## Project Structure

```
specguard/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app
│   │   ├── config.py            # Settings
│   │   ├── database.py          # SQLAlchemy async setup
│   │   ├── models/              # Database models
│   │   ├── schemas/             # Pydantic schemas (API + AI output)
│   │   ├── routes/              # API endpoints
│   │   ├── services/            # Business logic
│   │   │   ├── ai_client.py     # OpenAI wrapper + retry
│   │   │   ├── pipeline.py      # Multi-stage orchestrator
│   │   │   ├── file_parser.py   # Document ingestion
│   │   │   └── scorer.py        # Coverage scoring
│   │   └── prompts/             # AI prompt templates
│   └── tests/                   # pytest test suite
├── frontend/
│   └── src/
│       ├── api/client.ts        # Typed API client
│       ├── types/index.ts       # TypeScript types
│       ├── components/          # Reusable components
│       └── pages/               # Route pages
└── sample_docs/                 # Example specs for testing
```

## License

MIT
