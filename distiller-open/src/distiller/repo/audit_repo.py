"""AuditRepo — audit_log writes + trace_id lookup."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session as OrmSession

from ..models import AuditLog


class AuditRepo:
    """Encapsulates access to the `audit_log` table."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def log(
        self,
        table_name: str,
        record_id: int,
        operation: str,
        old_data: Optional[dict],
        new_data: Optional[dict],
        agent_name: str,
        zone_name: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> AuditLog:
        """Append an audit row.

        The schema uses `target_type` for the table, `target_id` for the row id,
        `actor` for the agent, and `payload` JSON for diff; zone_name lives in
        payload since the table itself has no zone column.
        """
        payload: dict[str, Any] = {
            "old": old_data,
            "new": new_data,
        }
        if zone_name is not None:
            payload["zone_name"] = zone_name

        row = AuditLog(
            actor=agent_name,
            action=operation,
            target_type=table_name,
            target_id=str(record_id),
            payload=payload,
            trace_id=trace_id,
        )
        self.db.add(row)
        self.db.flush()
        return row

    def query_by_trace(self, trace_id: str) -> list[AuditLog]:
        """Return all audit rows sharing a trace_id, oldest first (causal order)."""
        stmt = (
            select(AuditLog)
            .where(AuditLog.trace_id == trace_id)
            .order_by(AuditLog.created_at.asc(), AuditLog.audit_id.asc())
        )
        return list(self.db.execute(stmt).scalars().all())
