"""REST API routes — wires the service layer to HTTP.

Every write-side endpoint relies on the underlying service to honour the
DIST-01 ordering (JSONL append -> MySQL write -> audit_log). Routes only
translate HTTP <-> service args and shape responses with Pydantic DTOs.

DB session lifecycle is owned by FastAPI's ``Depends(get_db)`` generator;
write endpoints commit on success and roll back on any uncaught exception.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...service import (
    MemoryService,
    ProjectService,
    ReviewService,
    ZoneService,
)
from .dto import (
    ApiError,
    MemoryItem,
    PatrolResponse,
    ReportIssueRequest,
    ReportIssueResponse,
    ReportProgressRequest,
    ReportProgressResponse,
    RequestReviewRequest,
    RequestReviewResponse,
    SubmitReviewRequest,
    SubmitReviewResponse,
    WriteMemoryRequest,
    WriteMemoryResponse,
    ZoneSnapshot,
)

api_router = APIRouter(prefix="/api/v1")


# ---------- Memory ---------------------------------------------------------


@api_router.post(
    "/memories",
    response_model=WriteMemoryResponse,
    status_code=201,
    responses={400: {"model": ApiError}},
)
def write_memory(
    body: WriteMemoryRequest,
    db: Annotated[Session, Depends(get_db)],
) -> WriteMemoryResponse:
    """Write a new memory (decision/pattern/fix/...). DIST-01 ordered."""
    svc = MemoryService(db)
    try:
        result = svc.write_memory(
            project_id=body.project_id,
            memory_type=body.memory_type,
            title=body.title,
            summary=body.summary,
            content=body.content,
            tags=body.tags,
            importance=body.importance,
            session_id=body.session_id,
            zone_name=body.zone_name,
            agent_name=body.agent_name,
            trace_id=body.trace_id,
        )
        db.commit()
    except Exception as exc:  # pragma: no cover - shape only
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WriteMemoryResponse(**result)


@api_router.get(
    "/memories",
    response_model=list[MemoryItem],
    responses={400: {"model": ApiError}},
)
def search_memory(
    db: Annotated[Session, Depends(get_db)],
    project_id: Annotated[str, Query(..., max_length=64)],
    q: Annotated[str, Query(..., min_length=1)],
    top_k: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[MemoryItem]:
    """Full-text search over a project's active memories. Read-only path."""
    svc = MemoryService(db)
    try:
        rows = svc.search_memory(project_id=project_id, query=q, top_k=top_k)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return [MemoryItem(**row) for row in rows]


# ---------- Zone progress / issues -----------------------------------------


@api_router.post(
    "/zones/{zone_name}/progress",
    response_model=ReportProgressResponse,
    status_code=201,
    responses={400: {"model": ApiError}},
)
def report_progress(
    zone_name: str,
    body: ReportProgressRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ReportProgressResponse:
    """Report progress for a zone (module). DIST-01 ordered."""
    svc = ZoneService(db)
    try:
        result = svc.report_progress(
            zone_name=zone_name,
            status=body.status,
            completion_pct=body.completion_pct,
            current_task=body.current_task,
            blockers=body.blockers,
            next_plan=body.next_plan,
            reported_by=body.reported_by,
            trace_id=body.trace_id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReportProgressResponse(**result)


@api_router.post(
    "/zones/{zone_name}/issues",
    response_model=ReportIssueResponse,
    status_code=201,
    responses={400: {"model": ApiError}},
)
def report_issue(
    zone_name: str,
    body: ReportIssueRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ReportIssueResponse:
    """Open an issue against a zone. DIST-01 ordered."""
    svc = ZoneService(db)
    try:
        result = svc.report_issue(
            zone_name=zone_name,
            severity=body.severity,
            title=body.title,
            description=body.description,
            reported_by=body.reported_by,
            trace_id=body.trace_id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ReportIssueResponse(**result)


# ---------- Patrol ---------------------------------------------------------


@api_router.get(
    "/projects/{project_id}/patrol",
    response_model=PatrolResponse,
    responses={400: {"model": ApiError}, 404: {"model": ApiError}},
)
def patrol(
    project_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> PatrolResponse:
    """Aggregated module status for a project. Read-only path."""
    proj_svc = ProjectService(db)
    if proj_svc.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")
    zone_svc = ZoneService(db)
    try:
        modules = zone_svc.repo.list_modules(project_id=project_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    snapshots = [
        ZoneSnapshot(
            id=m.id,
            project_id=m.project_id,
            module_name=m.module_name,
            zone_name=m.zone_name,
            assigned_agent=m.assigned_agent,
            status=m.status,
            acceptance_criteria=m.acceptance_criteria,
            acceptance_schema=m.acceptance_schema,
        )
        for m in modules
    ]
    return PatrolResponse(
        project_id=project_id,
        zone_count=len(snapshots),
        zones=snapshots,
    )


# ---------- Reviews --------------------------------------------------------


@api_router.post(
    "/reviews",
    response_model=RequestReviewResponse,
    status_code=201,
    responses={400: {"model": ApiError}},
)
def request_review(
    body: RequestReviewRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RequestReviewResponse:
    """Open a review request against a zone. DIST-01 ordered."""
    svc = ReviewService(db)
    try:
        result = svc.request_review(
            zone_name=body.zone_name,
            requested_by=body.requested_by,
            notes=body.notes,
            trace_id=body.trace_id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RequestReviewResponse(**result)


@api_router.post(
    "/reviews/{request_id}/result",
    response_model=SubmitReviewResponse,
    status_code=201,
    responses={400: {"model": ApiError}, 404: {"model": ApiError}},
)
def submit_review(
    request_id: int,
    body: SubmitReviewRequest,
    db: Annotated[Session, Depends(get_db)],
) -> SubmitReviewResponse:
    """Submit a review result. Flips the parent request status."""
    svc = ReviewService(db)
    try:
        result = svc.submit_review(
            request_id=request_id,
            reviewed_by=body.reviewed_by,
            approved=body.approved,
            issues=body.issues,
            summary=body.summary,
            checklist_items=body.checklist_items,
            trace_id=body.trace_id,
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SubmitReviewResponse(**result)
