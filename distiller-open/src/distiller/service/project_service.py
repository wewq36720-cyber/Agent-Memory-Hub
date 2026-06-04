"""ProjectService — orchestrates ProjectRepo + JSONL + audit_log.

Every write-side method follows the DIST-01 mandatory order:
    JSONL append (fsync) -> MySQL repo write -> audit_log entry.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session as OrmSession

from ..jsonl import JsonlWriter, get_writer
from ..repo import AuditRepo, ProjectRepo


class ProjectService:
    """Project-level orchestration."""

    def __init__(
        self,
        db: OrmSession,
        writer: Optional[JsonlWriter] = None,
    ) -> None:
        self.db = db
        self.writer = writer if writer is not None else get_writer()
        self.repo = ProjectRepo(db)
        self.audit = AuditRepo(db)

    def create_project(
        self,
        project_id: str,
        name: str,
        description: Optional[str] = None,
        agent_name: str = "system",
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        tid = trace_id or str(uuid.uuid4())
        # 1. JSONL first — truth log.
        offset = self.writer.append(
            {
                "event": "create_project",
                "project_id": project_id,
                "name": name,
                "description": description,
                "agent": agent_name,
                "trace_id": tid,
            }
        )
        # 2. MySQL via repo.
        proj = self.repo.create(project_id=project_id, name=name, description=description)
        # 3. audit_log.
        self.audit.log(
            table_name="projects",
            record_id=proj.project_id,
            operation="create",
            old_data=None,
            new_data={"project_id": proj.project_id, "name": name, "description": description},
            agent_name=agent_name,
            trace_id=tid,
        )
        return {
            "project_id": proj.project_id,
            "name": proj.name,
            "description": proj.description,
            "status": proj.status,
            "jsonl_offset": offset,
            "trace_id": tid,
        }

    def get_project(self, project_id: str) -> Optional[dict[str, Any]]:
        proj = self.repo.get(project_id)
        if proj is None:
            return None
        return {
            "project_id": proj.project_id,
            "name": proj.name,
            "description": proj.description,
            "status": proj.status,
        }

    def list_active(self, limit: int = 100) -> list[dict[str, Any]]:
        return [
            {
                "project_id": p.project_id,
                "name": p.name,
                "description": p.description,
                "status": p.status,
            }
            for p in self.repo.list_active(limit=limit)
        ]

    def archive_project(
        self,
        project_id: str,
        agent_name: str,
        trace_id: Optional[str] = None,
    ) -> bool:
        tid = trace_id or str(uuid.uuid4())
        # 1. JSONL.
        self.writer.append(
            {
                "event": "archive_project",
                "project_id": project_id,
                "agent": agent_name,
                "trace_id": tid,
            }
        )
        # 2. MySQL.
        ok = self.repo.archive(project_id)
        # 3. audit.
        self.audit.log(
            table_name="projects",
            record_id=project_id,
            operation="archive",
            old_data={"status": "active"},
            new_data={"status": "archived"},
            agent_name=agent_name,
            trace_id=tid,
        )
        return ok
