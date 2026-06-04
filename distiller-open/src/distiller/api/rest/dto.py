"""Pydantic DTOs for the REST API.

Field types strictly match the service-layer method signatures defined in
``distiller.service``. Anything that needs to round-trip into JSONL/audit_log
is kept as primitive JSON-compatible shapes (str / int / list / dict).
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# 7 canonical memory_type values (kept in sync with the DDL CHECK constraint).
MemoryType = Literal[
    "preference",
    "fact",
    "decision",
    "context",
    "reference",
    "acceptance_criteria",
    "verification_result",
]


# ---------- Common ---------------------------------------------------------


class ApiError(BaseModel):
    """Uniform error envelope returned via HTTPException."""

    detail: str
    trace_id: Optional[str] = None


# ---------- write_memory ---------------------------------------------------


class WriteMemoryRequest(BaseModel):
    project_id: str = Field(..., max_length=64)
    memory_type: MemoryType
    title: str = Field(..., max_length=512)
    summary: str
    content: Optional[str] = None
    tags: Optional[list[str]] = None
    importance: int = Field(3, ge=1, le=5)
    session_id: Optional[str] = Field(None, max_length=64)
    zone_name: Optional[str] = Field(None, max_length=64)
    agent_name: str = Field("system", max_length=64)
    trace_id: Optional[str] = Field(None, max_length=36)


class WriteMemoryResponse(BaseModel):
    memory_id: int
    jsonl_offset: int
    trace_id: str


# ---------- search_memory --------------------------------------------------


class SearchMemoryQuery(BaseModel):
    """Query-string params for GET /memories. Used for documentation only."""

    project_id: str
    q: str
    top_k: int = 10


class MemoryItem(BaseModel):
    memory_id: int
    project_id: str
    memory_type: str
    title: str
    content: Optional[str] = None
    tags: Optional[list[Any]] = None
    importance: int
    active: bool
    trace_id: Optional[str] = None
    episode_id: Optional[int] = None
    superseded_by: Optional[int] = None


# ---------- report_progress ------------------------------------------------


ZoneStatus = Literal["in_progress", "blocked", "completed", "idle"]


class ReportProgressRequest(BaseModel):
    status: ZoneStatus
    completion_pct: int = Field(..., ge=0, le=100)
    current_task: Optional[str] = None
    blockers: Optional[list[str]] = None
    next_plan: Optional[str] = None
    reported_by: str = Field("agent", max_length=64)
    trace_id: Optional[str] = None


class ReportProgressResponse(BaseModel):
    id: int
    zone_name: str
    status: str
    completion_pct: int
    current_task: Optional[str] = None
    blockers: Optional[list[Any]] = None
    next_plan: Optional[str] = None
    reported_by: str
    trace_id: Optional[str] = None
    jsonl_offset: int


# ---------- report_issue ---------------------------------------------------


IssueSeverity = Literal["blocker", "major", "minor", "question"]


class ReportIssueRequest(BaseModel):
    severity: IssueSeverity
    title: str = Field(..., max_length=512)
    description: Optional[str] = None
    reported_by: str = Field("agent", max_length=64)
    trace_id: Optional[str] = None


class ReportIssueResponse(BaseModel):
    id: int
    zone_name: str
    reported_by: str
    severity: str
    title: str
    description: Optional[str] = None
    status: str
    human_notified: bool
    trace_id: Optional[str] = None
    jsonl_offset: int


# ---------- patrol ---------------------------------------------------------


class ZoneSnapshot(BaseModel):
    """One module's snapshot inside a project's patrol report."""

    id: str
    project_id: str
    module_name: str
    zone_name: str
    assigned_agent: Optional[str] = None
    status: str
    acceptance_criteria: Optional[list[Any]] = None
    acceptance_schema: Optional[dict[str, Any]] = None


class PatrolResponse(BaseModel):
    project_id: str
    zone_count: int
    zones: list[ZoneSnapshot]


# ---------- request_review / submit_review ---------------------------------


class RequestReviewRequest(BaseModel):
    zone_name: str = Field(..., max_length=64)
    requested_by: str = Field(..., max_length=64)
    notes: Optional[str] = None
    trace_id: Optional[str] = None


class RequestReviewResponse(BaseModel):
    request_id: int
    status: str
    jsonl_offset: int
    trace_id: str


class SubmitReviewRequest(BaseModel):
    reviewed_by: str = Field(..., max_length=64)
    approved: bool
    issues: Optional[list[dict[str, Any]]] = None
    summary: Optional[str] = None
    checklist_items: Optional[list[dict[str, Any]]] = None
    trace_id: Optional[str] = None


class SubmitReviewResponse(BaseModel):
    result_id: int
    request_id: int
    approved: bool
    jsonl_offset: int
    trace_id: str
