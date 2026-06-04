"""distiller MCP server (stdio mode).

Exposes 7 tools that mirror the REST endpoints but speak Model Context
Protocol. Each tool dispatches to the corresponding service method, wrapping
the synchronous SQLAlchemy session work in ``asyncio.to_thread`` so the
event loop is not blocked.

Run via:
    python -m distiller.api.mcp.server
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from ...db import SessionLocal
from ...service import (
    MemoryService,
    ReviewService,
    ZoneService,
)

logger = logging.getLogger(__name__)

app: Server = Server("distiller-mcp")


# ---------------------------------------------------------------------------
# Tool schema definitions
# ---------------------------------------------------------------------------


# Each tool's schema lives in its own module-level constant for IDE
# navigation and localized future edits. ``_ALL_TOOLS`` aggregates them.

_TOOL_WRITE_MEMORY = Tool(
    name="write_memory",
    description="Persist a memory to the distiller hub (JSONL truth log + MySQL).",
    inputSchema={
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "memory_type": {"type": "string"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "content": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "importance": {"type": "integer", "minimum": 1, "maximum": 5},
            "session_id": {"type": "string"},
            "zone_name": {"type": "string"},
            "agent_name": {"type": "string"},
            "trace_id": {"type": "string"},
        },
        "required": ["project_id", "memory_type", "title", "summary"],
    },
)


_TOOL_SEARCH_MEMORY = Tool(
    name="search_memory",
    description="Full-text search active memories for a project.",
    inputSchema={
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
            "query": {"type": "string"},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 100},
        },
        "required": ["project_id", "query"],
    },
)


_TOOL_REPORT_PROGRESS = Tool(
    name="report_progress",
    description="Append a zone progress report.",
    inputSchema={
        "type": "object",
        "properties": {
            "zone_name": {"type": "string"},
            "status": {"type": "string"},
            "completion_pct": {"type": "integer", "minimum": 0, "maximum": 100},
            "current_task": {"type": "string"},
            "blockers": {"type": "array", "items": {"type": "string"}},
            "next_plan": {"type": "string"},
            "reported_by": {"type": "string"},
            "trace_id": {"type": "string"},
        },
        "required": ["zone_name", "status", "completion_pct"],
    },
)


_TOOL_REPORT_ISSUE = Tool(
    name="report_issue",
    description="Open a new issue against a zone.",
    inputSchema={
        "type": "object",
        "properties": {
            "zone_name": {"type": "string"},
            "severity": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "reported_by": {"type": "string"},
            "trace_id": {"type": "string"},
        },
        "required": ["zone_name", "severity", "title"],
    },
)


_TOOL_PATROL = Tool(
    name="patrol",
    description="List all modules for a project (zone-level patrol view).",
    inputSchema={
        "type": "object",
        "properties": {
            "project_id": {"type": "string"},
        },
        "required": ["project_id"],
    },
)


_TOOL_REQUEST_REVIEW = Tool(
    name="request_review",
    description="Request a review for a zone.",
    inputSchema={
        "type": "object",
        "properties": {
            "zone_name": {"type": "string"},
            "requested_by": {"type": "string"},
            "notes": {"type": "string"},
            "trace_id": {"type": "string"},
        },
        "required": ["zone_name", "requested_by"],
    },
)


_TOOL_SUBMIT_REVIEW = Tool(
    name="submit_review",
    description="Submit a review verdict for a previously requested review.",
    inputSchema={
        "type": "object",
        "properties": {
            "request_id": {"type": "integer"},
            "reviewed_by": {"type": "string"},
            "approved": {"type": "boolean"},
            "issues": {"type": "array"},
            "summary": {"type": "string"},
            "checklist_items": {"type": "array"},
            "trace_id": {"type": "string"},
        },
        "required": ["request_id", "reviewed_by", "approved"],
    },
)


_ALL_TOOLS: list[Tool] = [
    _TOOL_WRITE_MEMORY,
    _TOOL_SEARCH_MEMORY,
    _TOOL_REPORT_PROGRESS,
    _TOOL_REPORT_ISSUE,
    _TOOL_PATROL,
    _TOOL_REQUEST_REVIEW,
    _TOOL_SUBMIT_REVIEW,
]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return _ALL_TOOLS


# ---------------------------------------------------------------------------
# Sync dispatch helpers — each opens a SessionLocal, runs the service call,
# commits, and serializes the result. They are invoked under
# asyncio.to_thread so the event loop stays free.
# ---------------------------------------------------------------------------


def _ok(payload: Any) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, default=str, ensure_ascii=False))]


def _err(name: str, exc: BaseException) -> list[TextContent]:
    body = {"error": type(exc).__name__, "tool": name, "message": str(exc)}
    return [TextContent(type="text", text=json.dumps(body, ensure_ascii=False))]


def _run_write_memory(args: dict) -> Any:
    db = SessionLocal()
    try:
        result = MemoryService(db).write_memory(
            project_id=args["project_id"],
            memory_type=args["memory_type"],
            title=args["title"],
            summary=args["summary"],
            content=args.get("content"),
            tags=args.get("tags"),
            importance=int(args.get("importance", 3)),
            session_id=args.get("session_id"),
            zone_name=args.get("zone_name"),
            agent_name=args.get("agent_name", "system"),
            trace_id=args.get("trace_id"),
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_search_memory(args: dict) -> Any:
    db = SessionLocal()
    try:
        return MemoryService(db).search_memory(
            project_id=args["project_id"],
            query=args["query"],
            top_k=int(args.get("top_k", 10)),
        )
    finally:
        db.close()


def _run_report_progress(args: dict) -> Any:
    db = SessionLocal()
    try:
        result = ZoneService(db).report_progress(
            zone_name=args["zone_name"],
            status=args["status"],
            completion_pct=int(args["completion_pct"]),
            current_task=args.get("current_task"),
            blockers=args.get("blockers"),
            next_plan=args.get("next_plan"),
            reported_by=args.get("reported_by", "agent"),
            trace_id=args.get("trace_id"),
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_report_issue(args: dict) -> Any:
    db = SessionLocal()
    try:
        result = ZoneService(db).report_issue(
            zone_name=args["zone_name"],
            severity=args["severity"],
            title=args["title"],
            description=args.get("description"),
            reported_by=args.get("reported_by", "agent"),
            trace_id=args.get("trace_id"),
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_patrol(args: dict) -> Any:
    db = SessionLocal()
    try:
        zsvc = ZoneService(db)
        modules = zsvc.repo.list_modules(project_id=args["project_id"])
        return {
            "project_id": args["project_id"],
            "module_count": len(modules),
            "modules": [
                {
                    "id": m.id,
                    "module_name": m.module_name,
                    "zone_name": m.zone_name,
                    "assigned_agent": m.assigned_agent,
                    "status": m.status,
                }
                for m in modules
            ],
        }
    finally:
        db.close()


def _run_request_review(args: dict) -> Any:
    db = SessionLocal()
    try:
        result = ReviewService(db).request_review(
            zone_name=args["zone_name"],
            requested_by=args["requested_by"],
            notes=args.get("notes"),
            trace_id=args.get("trace_id"),
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_submit_review(args: dict) -> Any:
    db = SessionLocal()
    try:
        result = ReviewService(db).submit_review(
            request_id=int(args["request_id"]),
            reviewed_by=args["reviewed_by"],
            approved=bool(args["approved"]),
            issues=args.get("issues"),
            summary=args.get("summary"),
            checklist_items=args.get("checklist_items"),
            trace_id=args.get("trace_id"),
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


_DISPATCH = {
    "write_memory": _run_write_memory,
    "search_memory": _run_search_memory,
    "report_progress": _run_report_progress,
    "report_issue": _run_report_issue,
    "patrol": _run_patrol,
    "request_review": _run_request_review,
    "submit_review": _run_submit_review,
}


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    args = arguments or {}
    handler = _DISPATCH.get(name)
    if handler is None:
        return _err(name, ValueError(f"unknown tool: {name}"))
    try:
        if name == "write_memory":
            result = await asyncio.to_thread(_run_write_memory, args)
        elif name == "search_memory":
            result = await asyncio.to_thread(_run_search_memory, args)
        elif name == "report_progress":
            result = await asyncio.to_thread(_run_report_progress, args)
        elif name == "report_issue":
            result = await asyncio.to_thread(_run_report_issue, args)
        elif name == "patrol":
            result = await asyncio.to_thread(_run_patrol, args)
        elif name == "request_review":
            result = await asyncio.to_thread(_run_request_review, args)
        elif name == "submit_review":
            result = await asyncio.to_thread(_run_submit_review, args)
        else:
            return _err(name, ValueError(f"unrouted tool: {name}"))
        return _ok(result)
    except Exception as exc:  # noqa: BLE001 — never crash the MCP loop
        logger.exception("MCP tool %s failed", name)
        return _err(name, exc)


async def main() -> None:
    """Run the distiller MCP server over stdio."""
    logging.basicConfig(level=logging.INFO)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

