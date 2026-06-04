"""MemoryRepo — memories table CRUD + FULLTEXT search + supersede chain.

Notes:
- importance column is TINYINT (1-5) per schema; method signature uses int.
- Ngram FULLTEXT index covers (title, content); we match against both via
  MATCH(title, content) AGAINST(:q IN NATURAL LANGUAGE MODE).
- Supersede pattern: insert new row, then mark old.active=False and
  old.superseded_by=new.memory_id; old.valid_to=now.
"""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import bindparam, func, select, text, update
from sqlalchemy.orm import Session as OrmSession

from ..models import Memory


class MemoryRepo:
    """Encapsulates access to the `memories` table."""

    def __init__(self, db: OrmSession) -> None:
        self.db = db

    def create(
        self,
        project_id: str,
        memory_type: str,
        title: str,
        summary: str,
        content: Optional[str] = None,
        tags: Optional[list] = None,
        importance: int = 3,
        trace_id: Optional[str] = None,
        episode_id: Optional[int] = None,
    ) -> Memory:
        """Insert a memory.

        `summary` maps to title-row free text; full body goes to `content`.
        If `content` is None, `summary` is also stored as content (column is NOT NULL).
        """
        body = content if content is not None else summary
        # Clamp importance into TINYINT 1-5 range per schema comment.
        imp = max(1, min(5, int(importance)))
        mem = Memory(
            project_id=project_id,
            memory_type=memory_type,
            title=title,
            content=body,
            tags=tags,
            importance=imp,
            active=True,
            trace_id=trace_id,
            episode_id=episode_id,
        )
        self.db.add(mem)
        self.db.flush()
        return mem

    def get(self, memory_id: int) -> Optional[Memory]:
        """Fetch memory by id."""
        stmt = select(Memory).where(Memory.memory_id == memory_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def search_fulltext(
        self,
        project_id: str,
        query: str,
        top_k: int = 10,
    ) -> list[Memory]:
        """MySQL ngram FULLTEXT search scoped to a project, active rows only.

        Uses NATURAL LANGUAGE MODE; relevance score sorts results.
        """
        stmt = (
            select(Memory)
            .where(
                Memory.project_id == project_id,
                Memory.active.is_(True),
                text(
                    "MATCH(title, content) AGAINST(:q IN NATURAL LANGUAGE MODE)"
                ),
            )
            .order_by(
                text(
                    "MATCH(title, content) AGAINST(:q IN NATURAL LANGUAGE MODE) DESC"
                )
            )
            .limit(top_k)
        )
        return list(
            self.db.execute(stmt, {"q": query}).scalars().all()
        )

    def supersede(self, old_id: int, new_memory_data: dict) -> Memory:
        """Create a replacement memory and mark the old one superseded.

        new_memory_data must include: project_id, memory_type, title, summary
        (or content). Optional: tags, importance, trace_id, episode_id.
        Inherits project_id from old if missing.
        """
        old = self.get(old_id)
        if old is None:
            raise ValueError(f"memory {old_id} not found")

        data = dict(new_memory_data)
        data.setdefault("project_id", old.project_id)
        data.setdefault("memory_type", old.memory_type)
        data.setdefault("title", old.title or "(untitled)")
        if "content" not in data and "summary" not in data:
            data["summary"] = old.content
        new_mem = self.create(
            project_id=data["project_id"],
            memory_type=data["memory_type"],
            title=data["title"],
            summary=data.get("summary", data.get("content", "")),
            content=data.get("content"),
            tags=data.get("tags"),
            importance=int(data.get("importance", old.importance)),
            trace_id=data.get("trace_id"),
            episode_id=data.get("episode_id"),
        )

        # Mark old row as superseded.
        upd = (
            update(Memory)
            .where(Memory.memory_id == old_id)
            .values(
                active=False,
                superseded_by=new_mem.memory_id,
                valid_to=func.current_timestamp(),
            )
        )
        self.db.execute(upd)
        self.db.flush()
        return new_mem

    def list_active(
        self,
        project_id: str,
        memory_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Memory]:
        """List active memories for a project, optionally filtered by type."""
        stmt = select(Memory).where(
            Memory.project_id == project_id,
            Memory.active.is_(True),
        )
        if memory_type is not None:
            stmt = stmt.where(Memory.memory_type == memory_type)
        stmt = stmt.order_by(
            Memory.importance.desc(), Memory.updated_at.desc()
        ).limit(limit)
        return list(self.db.execute(stmt).scalars().all())
