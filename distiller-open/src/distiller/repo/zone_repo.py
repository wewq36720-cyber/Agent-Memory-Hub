"""ZoneRepo — covers project_modules + zone_progress + issues.

Single repo per spec; service layer (B3) decides when to call which method.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import Issue, ProjectModule, ZoneProgress


class ZoneRepo:
    """Encapsulates access to project_modules / zone_progress / issues."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    # -- project_modules --------------------------------------------------

    def create_module(
        self,
        project_id: str,
        module_name: str,
        zone_name: str,
        assigned_agent: Optional[str],
        acceptance_criteria: Optional[list] = None,
        acceptance_schema: Optional[dict] = None,
    ) -> ProjectModule:
        """Register a module + zone. Module id is a fresh UUID4."""
        mod = ProjectModule(
            id=str(uuid.uuid4()),
            project_id=project_id,
            module_name=module_name,
            zone_name=zone_name,
            assigned_agent=assigned_agent,
            acceptance_criteria=acceptance_criteria,
            acceptance_schema=acceptance_schema,
            status="active",
        )
        self.db.add(mod)
        self.db.flush()
        return mod

    def get_module(self, zone_name: str) -> Optional[ProjectModule]:
        """Fetch module by unique zone_name."""
        stmt = select(ProjectModule).where(ProjectModule.zone_name == zone_name)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_modules(self, project_id: str) -> list[ProjectModule]:
        """All modules for a project, newest first."""
        stmt = (
            select(ProjectModule)
            .where(ProjectModule.project_id == project_id)
            .order_by(ProjectModule.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    # -- zone_progress ----------------------------------------------------

    def report_progress(
        self,
        zone_name: str,
        status: str,
        completion_pct: int,
        current_task: Optional[str],
        blockers: Optional[list],
        next_plan: Optional[str],
        reported_by: str,
        trace_id: Optional[str] = None,
    ) -> ZoneProgress:
        """Append a progress row (zones report continuously, no upsert)."""
        pct = max(0, min(100, int(completion_pct)))
        zp = ZoneProgress(
            zone_name=zone_name,
            status=status,
            completion_pct=pct,
            current_task=current_task,
            blockers=blockers,
            next_plan=next_plan,
            reported_by=reported_by,
            trace_id=trace_id,
        )
        self.db.add(zp)
        self.db.flush()
        return zp

    # -- issues -----------------------------------------------------------

    def report_issue(
        self,
        zone_name: str,
        severity: str,
        title: str,
        description: Optional[str],
        reported_by: str,
        trace_id: Optional[str] = None,
    ) -> Issue:
        """Open a new issue (status='open')."""
        iss = Issue(
            zone_name=zone_name,
            reported_by=reported_by,
            severity=severity,
            title=title,
            description=description,
            status="open",
            human_notified=False,
            trace_id=trace_id,
        )
        self.db.add(iss)
        self.db.flush()
        return iss
