"""ZoneService — orchestrates ZoneRepo + JSONL + audit_log.

Covers: project_modules registration, zone progress reports, issues.
Order on every write: JSONL -> MySQL -> audit_log (DIST-01).
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session as OrmSession

from ..jsonl import JsonlWriter, get_writer
from ..repo import AuditRepo, ZoneRepo


def _module_to_dict(m: Any) -> dict[str, Any]:
    return {
        "id": m.id,
        "project_id": m.project_id,
        "module_name": m.module_name,
        "zone_name": m.zone_name,
        "assigned_agent": m.assigned_agent,
        "acceptance_criteria": m.acceptance_criteria,
        "acceptance_schema": m.acceptance_schema,
        "status": m.status,
    }


def _progress_to_dict(p: Any) -> dict[str, Any]:
    return {
        "id": p.id,
        "zone_name": p.zone_name,
        "status": p.status,
        "completion_pct": p.completion_pct,
        "current_task": p.current_task,
        "blockers": p.blockers,
        "next_plan": p.next_plan,
        "reported_by": p.reported_by,
        "trace_id": p.trace_id,
    }


def _issue_to_dict(i: Any) -> dict[str, Any]:
    return {
        "id": i.id,
        "zone_name": i.zone_name,
        "reported_by": i.reported_by,
        "severity": i.severity,
        "title": i.title,
        "description": i.description,
        "status": i.status,
        "human_notified": i.human_notified,
        "trace_id": i.trace_id,
    }


class ZoneService:
    """Zone (module) lifecycle + progress + issues."""

    def __init__(
        self,
        db: OrmSession,
        writer: Optional[JsonlWriter] = None,
    ) -> None:
        self.db = db
        self.writer = writer if writer is not None else get_writer()
        self.repo = ZoneRepo(db)
        self.audit = AuditRepo(db)

    def create_module(
        self,
        project_id: str,
        module_name: str,
        zone_name: str,
        assigned_agent: Optional[str],
        acceptance_criteria: Optional[list] = None,
        acceptance_schema: Optional[dict] = None,
        agent_name: str = "system",
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        tid = trace_id or str(uuid.uuid4())
        offset = self.writer.append(
            {
                "event": "create_module",
                "project_id": project_id,
                "module_name": module_name,
                "zone_name": zone_name,
                "assigned_agent": assigned_agent,
                "acceptance_criteria": acceptance_criteria,
                "acceptance_schema": acceptance_schema,
                "agent": agent_name,
                "trace_id": tid,
            }
        )
        mod = self.repo.create_module(
            project_id=project_id,
            module_name=module_name,
            zone_name=zone_name,
            assigned_agent=assigned_agent,
            acceptance_criteria=acceptance_criteria,
            acceptance_schema=acceptance_schema,
        )
        self.audit.log(
            table_name="project_modules",
            record_id=mod.id,
            operation="create",
            old_data=None,
            new_data=_module_to_dict(mod),
            agent_name=agent_name,
            zone_name=zone_name,
            trace_id=tid,
        )
        result = _module_to_dict(mod)
        result["jsonl_offset"] = offset
        result["trace_id"] = tid
        return result

    def report_progress(
        self,
        zone_name: str,
        status: str,
        completion_pct: int,
        current_task: Optional[str] = None,
        blockers: Optional[list] = None,
        next_plan: Optional[str] = None,
        reported_by: str = "agent",
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        tid = trace_id or str(uuid.uuid4())
        offset = self.writer.append(
            {
                "event": "report_progress",
                "zone_name": zone_name,
                "status": status,
                "completion_pct": completion_pct,
                "current_task": current_task,
                "blockers": blockers,
                "next_plan": next_plan,
                "reported_by": reported_by,
                "trace_id": tid,
            }
        )
        zp = self.repo.report_progress(
            zone_name=zone_name,
            status=status,
            completion_pct=completion_pct,
            current_task=current_task,
            blockers=blockers,
            next_plan=next_plan,
            reported_by=reported_by,
            trace_id=tid,
        )
        self.audit.log(
            table_name="zone_progress",
            record_id=zp.id,
            operation="report",
            old_data=None,
            new_data=_progress_to_dict(zp),
            agent_name=reported_by,
            zone_name=zone_name,
            trace_id=tid,
        )
        result = _progress_to_dict(zp)
        result["jsonl_offset"] = offset
        return result

    def report_issue(
        self,
        zone_name: str,
        severity: str,
        title: str,
        description: Optional[str] = None,
        reported_by: str = "agent",
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        tid = trace_id or str(uuid.uuid4())
        offset = self.writer.append(
            {
                "event": "report_issue",
                "zone_name": zone_name,
                "severity": severity,
                "title": title,
                "description": description,
                "reported_by": reported_by,
                "trace_id": tid,
            }
        )
        iss = self.repo.report_issue(
            zone_name=zone_name,
            severity=severity,
            title=title,
            description=description,
            reported_by=reported_by,
            trace_id=tid,
        )
        self.audit.log(
            table_name="issues",
            record_id=iss.id,
            operation="open",
            old_data=None,
            new_data=_issue_to_dict(iss),
            agent_name=reported_by,
            zone_name=zone_name,
            trace_id=tid,
        )
        result = _issue_to_dict(iss)
        result["jsonl_offset"] = offset
        return result

    def get_module(self, zone_name: str) -> Optional[dict[str, Any]]:
        mod = self.repo.get_module(zone_name)
        if mod is None:
            return None
        return _module_to_dict(mod)
