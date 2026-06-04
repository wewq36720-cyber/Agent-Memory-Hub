"""Service layer — orchestrates repo + JSONL + audit_log per DIST-01.

Every write-side service method follows the strict order:
    1. JSONL append (fsync) — capture jsonl_offset
    2. MySQL write via repo (referencing jsonl_offset where applicable)
    3. audit_log entry (trace_id correlated)

JSONL is the source of truth and is never rolled back; MySQL is rebuildable
from JSONL replay.
"""
from .memory_service import MemoryService
from .project_service import ProjectService
from .review_service import ReviewService
from .zone_service import ZoneService

__all__ = [
    "MemoryService",
    "ZoneService",
    "ReviewService",
    "ProjectService",
]
