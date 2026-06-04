"""ReviewService — review_requests / review_results / approval_gates.

These tables have no dedicated repo per the spec; the service writes them
directly via SessionLocal-bound ORM. The DIST-01 ordering still holds:
JSONL append (fsync) -> MySQL write -> audit_log entry.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session as OrmSession

from ..jsonl import JsonlWriter, get_writer
from ..models import ApprovalGate, ReviewRequest, ReviewResult
from ..repo import AuditRepo


class ReviewService:
    """Review request/result + human approval gate orchestration."""

    def __init__(
        self,
        db: OrmSession,
        writer: Optional[JsonlWriter] = None,
    ) -> None:
        self.db = db
        self.writer = writer if writer is not None else get_writer()
        self.audit = AuditRepo(db)

    def request_review(
        self,
        zone_name: str,
        requested_by: str,
        notes: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        tid = trace_id or str(uuid.uuid4())
        offset = self.writer.append(
            {
                "event": "request_review",
                "zone_name": zone_name,
                "requested_by": requested_by,
                "notes": notes,
                "trace_id": tid,
            }
        )
        req = ReviewRequest(
            zone_name=zone_name,
            requested_by=requested_by,
            notes=notes,
            status="pending",
            trace_id=tid,
        )
        self.db.add(req)
        self.db.flush()
        self.audit.log(
            table_name="review_requests",
            record_id=req.id,
            operation="request",
            old_data=None,
            new_data={
                "id": req.id,
                "zone_name": zone_name,
                "requested_by": requested_by,
                "status": req.status,
                "notes": notes,
            },
            agent_name=requested_by,
            zone_name=zone_name,
            trace_id=tid,
        )
        return {
            "request_id": req.id,
            "status": req.status,
            "jsonl_offset": offset,
            "trace_id": tid,
        }

    def submit_review(
        self,
        request_id: int,
        reviewed_by: str,
        approved: bool,
        issues: Optional[list] = None,
        summary: Optional[str] = None,
        checklist_items: Optional[list] = None,
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        tid = trace_id or str(uuid.uuid4())
        offset = self.writer.append(
            {
                "event": "submit_review",
                "request_id": request_id,
                "reviewed_by": reviewed_by,
                "approved": approved,
                "issues": issues,
                "summary": summary,
                "checklist_items": checklist_items,
                "trace_id": tid,
            }
        )
        res = ReviewResult(
            request_id=request_id,
            reviewed_by=reviewed_by,
            approved=approved,
            issues=issues,
            summary=summary,
            checklist_items=checklist_items,
            trace_id=tid,
        )
        self.db.add(res)
        self.db.flush()
        # Flip the parent request status.
        req = self.db.get(ReviewRequest, request_id)
        if req is not None:
            req.status = "approved" if approved else "rejected"
            self.db.flush()
        self.audit.log(
            table_name="review_results",
            record_id=res.id,
            operation="submit",
            old_data=None,
            new_data={
                "id": res.id,
                "request_id": request_id,
                "reviewed_by": reviewed_by,
                "approved": approved,
                "summary": summary,
            },
            agent_name=reviewed_by,
            trace_id=tid,
        )
        return {
            "result_id": res.id,
            "request_id": request_id,
            "approved": approved,
            "jsonl_offset": offset,
            "trace_id": tid,
        }

    def create_approval_gate(
        self,
        project_id: str,
        gate_type: str,
        report_snapshot: Optional[dict] = None,
        agent_name: str = "system",
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        tid = trace_id or str(uuid.uuid4())
        offset = self.writer.append(
            {
                "event": "create_approval_gate",
                "project_id": project_id,
                "gate_type": gate_type,
                "report_snapshot": report_snapshot,
                "agent": agent_name,
                "trace_id": tid,
            }
        )
        gate = ApprovalGate(
            project_id=project_id,
            gate_type=gate_type,
            status="pending",
            report_snapshot=report_snapshot,
            trace_id=tid,
        )
        self.db.add(gate)
        self.db.flush()
        self.audit.log(
            table_name="approval_gates",
            record_id=gate.id,
            operation="create",
            old_data=None,
            new_data={
                "id": gate.id,
                "project_id": project_id,
                "gate_type": gate_type,
                "status": gate.status,
            },
            agent_name=agent_name,
            trace_id=tid,
        )
        return {
            "gate_id": gate.id,
            "status": gate.status,
            "jsonl_offset": offset,
            "trace_id": tid,
        }

    def human_decide(
        self,
        gate_id: int,
        approved: bool,
        decision_text: str,
        agent_name: str = "human",
        trace_id: Optional[str] = None,
    ) -> dict[str, Any]:
        tid = trace_id or str(uuid.uuid4())
        offset = self.writer.append(
            {
                "event": "human_decide",
                "gate_id": gate_id,
                "approved": approved,
                "decision_text": decision_text,
                "agent": agent_name,
                "trace_id": tid,
            }
        )
        gate = self.db.get(ApprovalGate, gate_id)
        if gate is None:
            raise ValueError(f"approval_gate {gate_id} not found")
        old_status = gate.status
        gate.status = "approved" if approved else "rejected"
        gate.human_decision = decision_text
        gate.decided_at = datetime.now(timezone.utc)
        self.db.flush()
        self.audit.log(
            table_name="approval_gates",
            record_id=gate.id,
            operation="human_decide",
            old_data={"status": old_status},
            new_data={"status": gate.status, "human_decision": decision_text},
            agent_name=agent_name,
            trace_id=tid,
        )
        return {
            "gate_id": gate.id,
            "status": gate.status,
            "approved": approved,
            "jsonl_offset": offset,
            "trace_id": tid,
        }
