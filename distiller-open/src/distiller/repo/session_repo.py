"""SessionRepo — sessions table CRUD."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session as OrmSession

from ..models import Session as SessionModel


class SessionRepo:
    """Encapsulates access to the `sessions` table."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def create(
        self,
        session_id: str,
        project_id: str,
        agent_name: str,
        zone_name: Optional[str] = None,
    ) -> SessionModel:
        """Open a new session (status='open')."""
        sess = SessionModel(
            session_id=session_id,
            project_id=project_id,
            agent_name=agent_name,
            zone_name=zone_name,
            status="open",
        )
        self.db.add(sess)
        self.db.flush()
        return sess

    def get(self, session_id: str) -> Optional[SessionModel]:
        """Fetch session by id."""
        stmt = select(SessionModel).where(SessionModel.session_id == session_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def end(
        self,
        session_id: str,
        compact_snapshot: Optional[str] = None,
    ) -> bool:
        """Close a session, stamping ended_at and optional compact snapshot in metadata."""
        sess = self.get(session_id)
        if sess is None:
            return False
        sess.status = "closed"
        sess.ended_at = self.db.execute(select(func.current_timestamp())).scalar()
        if compact_snapshot is not None:
            existing = sess.metadata_ or {}
            if not isinstance(existing, dict):
                existing = {}
            existing["compact_snapshot"] = compact_snapshot
            sess.metadata_ = existing
        self.db.flush()
        return True

    def list_by_project(
        self,
        project_id: str,
        limit: int = 50,
    ) -> list[SessionModel]:
        """List sessions for a project, newest first."""
        stmt = (
            select(SessionModel)
            .where(SessionModel.project_id == project_id)
            .order_by(SessionModel.started_at.desc())
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
