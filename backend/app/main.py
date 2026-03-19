"""
SpecGuard — AI Test Intelligence Platform

Main application entry point.
Run with: uvicorn app.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routes import projects, documents, generation, test_suites
from app.services.ai_client import get_validation_stats

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    logger.info("Starting SpecGuard...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down SpecGuard")


app = FastAPI(
    title="SpecGuard",
    description="AI Test Intelligence Platform — Generate schema-validated test suites from product specs",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routes
app.include_router(projects.router)
app.include_router(documents.router)
app.include_router(generation.router)
app.include_router(test_suites.router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "specguard"}


@app.get("/api/stats/validation")
async def validation_stats():
    """Return AI output validation pass rate stats."""
    return get_validation_stats()
