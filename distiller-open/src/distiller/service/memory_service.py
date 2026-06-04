"""MemoryService — orchestrates MemoryRepo + JSONL + audit_log.

Strict DIST-01 ordering on every write:
    1. JSONL append (fsync)  -> jsonl_offset
    2. MemoryRepo.create / supersede with episode_id=jsonl_offset
    3. AuditRepo.log with trace_id correlation
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.orm import Session as OrmSession

from ..jsonl import JsonlWriter, get_writer
from ..repo import AuditRepo, MemoryRepo


def _memory_to_dict(mem: Any) -> dict[str, Any]:
    """Serialize a Memory ORM row to a plain dict (ORM-detached safe)."""
    return {
        "memory_id": mem.memory_id,
        "project_id": mem.project_id,
        "memory_type": mem.memory_type,
        "title": mem.title,
        "content": mem.content,
        "tags": mem.tags,
        "importance": mem.importance,
        "active": mem.active,
        "trace_id": mem.trace_id,
        "episode_id": mem.episode_id,
        "superseded_by": mem.superseded_by,
    }


class MemoryService:
    """Memory write/read orchestration with truth-log first ordering."""

    def __init__(
        self,
        db: OrmSession,
        writer: Optional[JsonlWriter] = None,
    ) -> None:
        self.db = db
        self.writer = writer if writer is not None else get_writer()
        self.repo = MemoryRepo(db)
        self.audit = AuditRepo(db)

    def write_memory(
        self,
        project_id: str,
        memory_type: str,
        title: str,
        summary: str,
        content: Optional[str] = None,
        tags: Optional[list] = None,
        importance: int = 3,
        session_id: Optional[str] = None,
        zone_name: Optional[str] = None,
        agent_name: str = "system",
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Write a memory. Order: JSONL -> MySQL -> audit_log."""
        tid = trace_id or str(uuid.uuid4())

        # 1. JSONL first — full payload so replay can rebuild MySQL.
        offset = self.writer.append(
            {
                "event": "write_memory",
                "project_id": project_id,
                "memory_type": memory_type,
                "title": title,
                "summary": summary,
                "content": content,
                "tags": tags,
                "importance": importance,
                "session_id": session_id,
                "zone_name": zone_name,
                "agent": agent_name,
                "trace_id": tid,
            }
        )

        # 2. MySQL write — episode_id points back at the JSONL offset.
        mem = self.repo.create(
            project_id=project_id,
            memory_type=memory_type,
            title=title,
            summary=summary,
            content=content,
            tags=tags,
            importance=importance,
            trace_id=tid,
            episode_id=offset,
        )

        # 3. audit_log.
        self.audit.log(
            table_name="memories",
            record_id=mem.memory_id,
            operation="write_memory",
            old_data=None,
            new_data=_memory_to_dict(mem),
            agent_name=agent_name,
            zone_name=zone_name,
            trace_id=tid,
        )

        return {
            "memory_id": mem.memory_id,
            "jsonl_offset": offset,
            "trace_id": tid,
        }

    def search_memory(
        self,
        project_id: str,
        query: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Read-only path — does NOT write JSONL or audit_log."""
        rows = self.repo.search_fulltext(
            project_id=project_id,
            query=query,
            top_k=top_k,
        )
        return [_memory_to_dict(m) for m in rows]

    def supersede_memory(
        self,
        old_memory_id: int,
        new_memory_data: dict[str, Any],
        agent_name: str = "system",
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Supersede an old memory with a new revision. JSONL -> MySQL -> audit."""
        tid = trace_id or str(uuid.uuid4())

        old_before = self.repo.get(old_memory_id)
        old_snapshot = _memory_to_dict(old_before) if old_before is not None else None

        # 1. JSONL.
        offset = self.writer.append(
            {
                "event": "supersede_memory",
                "old_memory_id": old_memory_id,
                "new": new_memory_data,
                "agent": agent_name,
                "trace_id": tid,
            }
        )

        # 2. MySQL — inject episode_id + trace_id into the new row.
        new_data = dict(new_memory_data)
        new_data.setdefault("trace_id", tid)
        new_data.setdefault("episode_id", offset)
        new_mem = self.repo.supersede(old_memory_id, new_data)

        # 3. audit_log.
        self.audit.log(
            table_name="memories",
            record_id=new_mem.memory_id,
            operation="supersede",
            old_data=old_snapshot,
            new_data=_memory_to_dict(new_mem),
            agent_name=agent_name,
            trace_id=tid,
        )

        return {
            "new_memory_id": new_mem.memory_id,
            "old_memory_id": old_memory_id,
            "jsonl_offset": offset,
            "trace_id": tid,
        }

    def list_memories(
        self,
        project_id: str,
        memory_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read-only path — does NOT write JSONL or audit_log."""
        rows = self.repo.list_active(
            project_id=project_id,
            memory_type=memory_type,
            limit=limit,
        )
        return [_memory_to_dict(m) for m in rows]
