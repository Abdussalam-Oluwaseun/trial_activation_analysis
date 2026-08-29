"""
api/main.py
────────────
COGENT bi — Trial Activation Dashboard
FastAPI application entrypoint.

Run with:
    uvicorn api.main:app --reload

The dashboard HTML is served from /dashboard/index.html.
API routes are mounted under /api/*.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api import local_data
from api.routes import funnel, organisations, overview

# ─── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger("cogent_bi")

# ─── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="COGENT bi — Trial Activation Dashboard",
    description="Internal analytics API for tracking organisation trial journeys.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)


@app.on_event("startup")
def preload_data() -> None:
    """Load all JSON data files into memory at startup."""
    try:
        local_data.reload()
        logger.info("Local data loaded successfully.")
    except FileNotFoundError as exc:
        logger.warning(f"Could not pre-load data: {exc}")

# Allow the HTML dashboard to call the API when opened from file:// during dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ─── API routes ──────────────────────────────────────────────────────────────

app.include_router(overview.router)
app.include_router(funnel.router)
app.include_router(organisations.router)

# ─── Static frontend ─────────────────────────────────────────────────────────

DASHBOARD_DIR = Path(__file__).parent.parent / "dashboard"

if DASHBOARD_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(DASHBOARD_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def serve_dashboard() -> FileResponse:
        """Serve the dashboard SPA."""
        return FileResponse(str(DASHBOARD_DIR / "index.html"))

else:
    logger.warning("dashboard/ directory not found — frontend will not be served.")


# ─── Health check ─────────────────────────────────────────────────────────────

@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok", "app": "COGENT bi Trial Activation Dashboard"}
