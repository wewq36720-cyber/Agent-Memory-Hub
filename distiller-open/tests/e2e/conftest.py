"""Common pytest fixtures for distiller e2e tests.

These tests hit the real Docker network: api container at localhost:8000
and MySQL at localhost:3306. No FastAPI TestClient is used.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


# Load .env from repo root so MYSQL_ROOT_PASSWORD is available.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env")


API_BASE_URL = os.getenv("DISTILLER_API_BASE_URL", "http://localhost:8000")

# Tables we wipe before every test (preserve schema_versions).
_BUSINESS_TABLES = [
    "verification_evidence",
    "approval_gates",
    "review_results",
    "review_requests",
    "patrol_logs",
    "issues",
    "zone_progress",
    "project_modules",
    "audit_log",
    "checkpoints",
    "sync_watermarks",
    "memories",
    "interface_registry",
    "sessions",
    "projects",
]


def _build_mysql_url() -> str:
    pwd = os.getenv("MYSQL_ROOT_PASSWORD", "distiller_dev_pass_2026")
    host = os.getenv("MYSQL_HOST", "localhost")
    port = os.getenv("MYSQL_PORT", "3306")
    db = os.getenv("MYSQL_DATABASE", "distiller_hub")
    return f"mysql+pymysql://root:{pwd}@{host}:{port}/{db}?charset=utf8mb4"


@pytest.fixture(scope="session")
def db_engine():
    eng = create_engine(_build_mysql_url(), pool_pre_ping=True, future=True)
    yield eng
    eng.dispose()


@pytest.fixture(scope="session")
def db_session_factory(db_engine):
    return sessionmaker(bind=db_engine, autocommit=False, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def api_client():
    with httpx.Client(base_url=API_BASE_URL, timeout=10.0) as client:
        yield client


@pytest.fixture()
def clean_db(db_engine):
    """Wipe e2e test data before each test, preserving:
    - schema_versions (DDL version tracking)
    - any row whose project_id starts with 'meta-' (long-term meta memory)
    """
    with db_engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for tbl in _BUSINESS_TABLES:
            # Tables that have a project_id column → preserve meta-* projects.
            # Other tables (audit_log, checkpoints, sync_watermarks, interface_registry):
            # full wipe is fine; they don't accumulate cross-session truth.
            if tbl == "projects":
                conn.execute(text("DELETE FROM projects WHERE project_id NOT LIKE 'meta-%'"))
            elif tbl in ("memories", "sessions", "project_modules", "patrol_logs",
                         "approval_gates", "verification_evidence"):
                conn.execute(text(f"DELETE FROM {tbl} WHERE project_id NOT LIKE 'meta-%'"))
            elif tbl == "audit_log":
                # audit_log keyed by project_id too, preserve meta lineage
                conn.execute(text("DELETE FROM audit_log WHERE project_id NOT LIKE 'meta-%' OR project_id IS NULL"))
            else:
                # zone_progress / issues / review_requests / review_results / checkpoints /
                # sync_watermarks / interface_registry — wipe fully, no cross-session value
                conn.execute(text(f"DELETE FROM {tbl}"))
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    yield


@pytest.fixture()
def test_project(clean_db, db_engine):
    """Create a fixture project, archive at teardown."""
    pid = "e2e-test-proj"
    with db_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO projects(project_id, name, description, status) "
                "VALUES (:pid, :name, :desc, 'active')"
            ),
            {"pid": pid, "name": "E2E Test Project", "desc": "auto"},
        )
    yield pid
    with db_engine.begin() as conn:
        conn.execute(
            text("UPDATE projects SET status='archived' WHERE project_id=:pid"),
            {"pid": pid},
        )


@pytest.fixture()
def make_zone(test_project, db_engine):
    """Helper to create a zone (project_module) under the test project."""
    created: list[str] = []

    def _make(zone_name: str | None = None, agent: str = "test-agent") -> str:
        z = zone_name or f"zone-{uuid.uuid4().hex[:8]}"
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO project_modules(id, project_id, module_name, zone_name, "
                    "assigned_agent, status) VALUES (:id, :pid, :mn, :zn, :ag, 'active')"
                ),
                {
                    "id": str(uuid.uuid4()),
                    "pid": test_project,
                    "mn": f"mod-{z}",
                    "zn": z,
                    "ag": agent,
                },
            )
        created.append(z)
        return z

    return _make
