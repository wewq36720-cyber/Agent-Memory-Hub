"""ProjectRepo — projects table CRUD."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session as OrmSession

from ..models import Project


class ProjectRepo:
    """Encapsulates access to the `projects` table."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def create(
        self,
        project_id: str,
        name: str,
        description: Optional[str] = None,
    ) -> Project:
        """Insert a new project (status defaults to 'active')."""
        proj = Project(
            project_id=project_id,
            name=name,
            description=description,
            status="active",
        )
        self.db.add(proj)
        self.db.flush()
        return proj

    def get(self, project_id: str) -> Optional[Project]:
        """Fetch by primary key, or None if missing."""
        stmt = select(Project).where(Project.project_id == project_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active(self, limit: int = 100) -> list[Project]:
        """List active projects, newest first."""
        stmt = (
            select(Project)
            .where(Project.status == "active")
            .order_by(Project.updated_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())

    def archive(self, project_id: str) -> bool:
        """Mark a project archived. Returns True if a row was updated."""
        stmt = (
            update(Project)
            .where(Project.project_id == project_id)
            .values(status="archived")
        )
        result = self.db.execute(stmt)
        return result.rowcount > 0
