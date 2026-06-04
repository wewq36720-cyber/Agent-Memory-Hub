"""Supersede chain — exercised at the service layer (no REST endpoint).

DIST-01 still applies (JSONL -> MySQL -> audit_log) but supersede_memory
is service-only. We use SessionLocal directly.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from distiller.db import SessionLocal
from distiller.service import MemoryService


def _write(svc: MemoryService, project_id: str, title: str) -> dict:
    return svc.write_memory(
        project_id=project_id,
        memory_type="decision",
        title=title,
        summary=f"summary for {title}",
        content=f"body of {title}",
        importance=3,
        agent_name="e2e-supersede",
    )


def test_supersede_marks_old_inactive(test_project, db_engine):
    """After supersede, old.active=False and old.superseded_by=new.memory_id."""
    db = SessionLocal()
    try:
        svc = MemoryService(db)
        old = _write(svc, test_project, "old-decision")
        db.commit()
        old_id = old["memory_id"]

        new_data = {
            "project_id": test_project,
            "memory_type": "decision",
            "title": "new-decision",
            "content": "revised body",
            "importance": 4,
        }
        result = svc.supersede_memory(old_memory_id=old_id, new_memory_data=new_data,
                                      agent_name="e2e-supersede")
        db.commit()
        new_id = result["new_memory_id"]
    finally:
        db.close()

    with db_engine.connect() as conn:
        old_row = conn.execute(
            text("SELECT active, superseded_by FROM memories WHERE memory_id=:mid"),
            {"mid": old_id},
        ).one()
        new_active = conn.execute(
            text("SELECT active FROM memories WHERE memory_id=:mid"),
            {"mid": new_id},
        ).scalar_one()

    assert bool(old_row.active) is False
    assert old_row.superseded_by == new_id
    assert bool(new_active) is True


def test_active_filter_excludes_superseded(test_project):
    """list_memories default must hide superseded rows."""
    db = SessionLocal()
    try:
        svc = MemoryService(db)
        old = _write(svc, test_project, "to-be-superseded")
        db.commit()
        old_id = old["memory_id"]

        svc.supersede_memory(
            old_memory_id=old_id,
            new_memory_data={
                "project_id": test_project,
                "memory_type": "decision",
                "title": "successor",
                "content": "successor body",
                "importance": 3,
            },
            agent_name="e2e-supersede",
        )
        db.commit()

        active_rows = svc.list_memories(project_id=test_project)
        ids = {row["memory_id"] for row in active_rows}
    finally:
        db.close()

    assert old_id not in ids, f"superseded id {old_id} leaked into list_memories"
