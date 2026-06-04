"""SQLAlchemy ORM models — 17 tables aligned with docker/mysql/*.sql.

Schema reference:
- F:/claudexiangmu/docker/mysql/01-hub-init.sql (9 tables)
- F:/claudexiangmu/docker/mysql/02-app-distiller-init.sql (8 tables)

All tables live in `distiller_hub` (single schema) with utf8mb4_0900_ai_ci.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.mysql import MEDIUMTEXT, TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


# ============================================================================
# Hub Layer (9 tables)
# ============================================================================


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("active", "archived", "suspended", name="project_status"),
        nullable=False,
        default="active",
        server_default="active",
    )
    owner: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class SchemaVersion(Base):
    __tablename__ = "schema_versions"

    version: Mapped[str] = mapped_column(String(20), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    migration_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class Session(Base):
    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    zone_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    agent_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("open", "closed", "aborted", name="session_status"),
        nullable=False,
        default="open",
        server_default="open",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)


class Memory(Base):
    __tablename__ = "memories"

    memory_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    memory_type: Mapped[str] = mapped_column(
        Enum(
            "preference",
            "fact",
            "decision",
            "context",
            "reference",
            "acceptance_criteria",
            "verification_result",
            name="memory_type",
        ),
        nullable=False,
    )
    title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(MEDIUMTEXT, nullable=False)
    tags: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    importance: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=3, server_default="3"
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    superseded_by: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    valid_from: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    valid_to: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    episode_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class InterfaceRegistry(Base):
    __tablename__ = "interface_registry"

    interface_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0.0", server_default="1.0.0"
    )
    status: Mapped[str] = mapped_column(
        Enum("draft", "active", "deprecated", "removed", name="interface_status"),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    audit_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    actor: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    checkpoint_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    state: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class SyncWatermark(Base):
    __tablename__ = "sync_watermarks"

    source: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    watermark: Mapped[str] = mapped_column(String(128), nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON, nullable=True)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


# ============================================================================
# App Layer (8 tables) — distiller business
# ============================================================================


class ProjectModule(Base):
    __tablename__ = "project_modules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_id"), nullable=False, index=True
    )
    module_name: Mapped[str] = mapped_column(String(255), nullable=False)
    zone_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    assigned_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    acceptance_criteria: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    acceptance_schema: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    milestone_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "active",
            "under_review",
            "approved",
            "rejected",
            "merged",
            name="project_module_status",
        ),
        nullable=False,
        default="active",
        server_default="active",
    )
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class ZoneProgress(Base):
    __tablename__ = "zone_progress"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zone_name: Mapped[str] = mapped_column(
        String(255), ForeignKey("project_modules.zone_name"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        Enum(
            "in_progress",
            "blocked",
            "completed",
            "idle",
            name="zone_progress_status",
        ),
        nullable=False,
        default="in_progress",
        server_default="in_progress",
    )
    current_task: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    completion_pct: Mapped[int] = mapped_column(
        TINYINT, nullable=False, default=0, server_default="0"
    )
    blockers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    next_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reported_by: Mapped[str] = mapped_column(String(255), nullable=False)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    report_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zone_name: Mapped[str] = mapped_column(
        String(255), ForeignKey("project_modules.zone_name"), nullable=False, index=True
    )
    reported_by: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(
        Enum("blocker", "major", "minor", "question", name="issue_severity"),
        nullable=False,
        default="question",
        server_default="question",
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("open", "discussing", "resolved", "closed", name="issue_status"),
        nullable=False,
        default="open",
        server_default="open",
    )
    supervisor_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    human_notified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0"
    )
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class PatrolLog(Base):
    __tablename__ = "patrol_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_id"), nullable=False, index=True
    )
    summary: Mapped[dict] = mapped_column(JSON, nullable=False)
    findings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    prodded_zones: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    patrol_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class ReviewRequest(Base):
    __tablename__ = "review_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    zone_name: Mapped[str] = mapped_column(
        String(255), ForeignKey("project_modules.zone_name"), nullable=False, index=True
    )
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending",
            "in_review",
            "approved",
            "rejected",
            name="review_request_status",
        ),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class ReviewResult(Base):
    __tablename__ = "review_results"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    request_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("review_requests.id"), nullable=False, index=True
    )
    reviewed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False)
    issues: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    checklist_items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class ApprovalGate(Base):
    __tablename__ = "approval_gates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_id"), nullable=False, index=True
    )
    gate_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="project_approval", server_default="project_approval"
    )
    status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected", name="approval_gate_status"),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    report_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    human_decision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )


class VerificationEvidence(Base):
    __tablename__ = "verification_evidence"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    zone_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    claim_type: Mapped[str] = mapped_column(String(50), nullable=False)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    covered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    not_covered: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    residual_risk: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence: Mapped[str] = mapped_column(
        Enum("A", "B", "C", name="evidence_confidence"), nullable=False
    )
    trace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, server_default=func.current_timestamp()
    )


__all__ = [
    # hub
    "Project",
    "SchemaVersion",
    "Session",
    "Memory",
    "InterfaceRegistry",
    "AuditLog",
    "Checkpoint",
    "SyncWatermark",
    "Tenant",
    # app
    "ProjectModule",
    "ZoneProgress",
    "Issue",
    "PatrolLog",
    "ReviewRequest",
    "ReviewResult",
    "ApprovalGate",
    "VerificationEvidence",
]
