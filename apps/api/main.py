"""
DHAAL API — FastAPI application entry point.

Design rules enforced here:
- No PII in logs.
- All errors return the ApiError shape: { error, message, code }.
- InvariantError always produces a 500 — the result is never rendered.
- CORS is permissive for local dev; tightened for production via env var.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db.session_store import init_db
from routes.session import router as session_router
from routes.document import router as document_router
from routes.clauses import router as clauses_router
from routes.simulate import router as simulate_router
from routes.plan import router as plan_router

# ---------------------------------------------------------------------------
# Logging — no PII
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting DHAAL API")
    init_db()
    yield
    logger.info("Shutting down DHAAL API")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DHAAL API",
    version="1.4.2",
    description="Financial shock compiler for insured Indian households.",
    lifespan=lifespan,
    # Hide schema endpoints in production
    docs_url="/docs" if os.getenv("APP_ENV") != "production" else None,
    redoc_url=None,
)

# CORS — allow Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global error handlers
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log without request body (may contain PII)
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "Something went wrong.", "code": 500},
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(session_router)
app.include_router(document_router)
app.include_router(clauses_router)
app.include_router(simulate_router)
app.include_router(plan_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.4.2"}
