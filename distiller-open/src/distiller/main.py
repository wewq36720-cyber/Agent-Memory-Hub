"""FastAPI application entry point."""
from fastapi import FastAPI
from sqlalchemy import text

from . import __version__
from .api.rest import api_router
from .db import engine

app = FastAPI(
    title="Distiller — Agent Memory Hub",
    version=__version__,
    description="上下文蒸馏 MCP 数据库",
)

app.include_router(api_router)


@app.get("/health")
def health():
    """Liveness probe — does not check DB."""
    return {"status": "ok", "version": __version__}


@app.get("/health/db")
def health_db():
    """Readiness probe — checks DB connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as exc:  # pragma: no cover - shape only
        return {"status": "error", "db": str(exc)[:200]}
