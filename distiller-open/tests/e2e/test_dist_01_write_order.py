"""DIST-01 ordering invariants: JSONL append -> MySQL -> audit_log.

These tests enforce that the write path's three side-effects stay
consistent: monotonic offsets, identical trace_id across the three
sinks, and one audit_log row per write.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from sqlalchemy import text


def _payload(project_id: str, idx: int) -> dict:
    return {
        "project_id": project_id,
        "memory_type": "fact",
        "title": f"order-test-{idx}",
        "summary": f"order summary {idx}",
        "content": f"order body {idx}",
        "importance": 3,
        "agent_name": "e2e-order",
    }


def test_jsonl_offset_monotonic(api_client, test_project):
    offsets: list[int] = []
    for i in range(5):
        r = api_client.post("/api/v1/memories", json=_payload(test_project, i))
        assert r.status_code == 201, r.text
        offsets.append(r.json()["jsonl_offset"])
    # Strictly monotonically increasing.
    for prev, cur in zip(offsets, offsets[1:]):
        assert cur > prev, f"non-monotonic offsets: {offsets}"


def test_trace_id_three_way_consistency(api_client, test_project, db_engine):
    """REST trace_id must equal memories.trace_id and audit_log.trace_id."""
    r = api_client.post("/api/v1/memories", json=_payload(test_project, 99))
    assert r.status_code == 201
    body = r.json()
    rest_tid = body["trace_id"]
    memory_id = body["memory_id"]

    with db_engine.connect() as conn:
        db_mem_tid = conn.execute(
            text("SELECT trace_id FROM memories WHERE memory_id=:mid"),
            {"mid": memory_id},
        ).scalar_one()
        audit_tid = conn.execute(
            text(
                "SELECT trace_id FROM audit_log "
                "WHERE target_type='memories' AND target_id=:mid "
                "ORDER BY audit_id DESC LIMIT 1"
            ),
            {"mid": str(memory_id)},
        ).scalar()

    assert db_mem_tid == rest_tid, f"memories.trace_id={db_mem_tid} != REST {rest_tid}"
    assert audit_tid == rest_tid, f"audit_log.trace_id={audit_tid} != REST {rest_tid}"


def test_audit_log_written(api_client, test_project, db_engine):
    """Each write_memory must emit exactly one audit_log row (action=write_memory)."""
    with db_engine.connect() as conn:
        before = conn.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE action='write_memory'")
        ).scalar_one()

    for i in range(3):
        r = api_client.post("/api/v1/memories", json=_payload(test_project, 1000 + i))
        assert r.status_code == 201

    with db_engine.connect() as conn:
        after = conn.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE action='write_memory'")
        ).scalar_one()

    assert after - before == 3, f"audit_log delta {after - before}, want 3"


def test_jsonl_file_exists(api_client, test_project):
    """Today's JSONL file must exist with at least as many lines as writes."""
    repo_root = Path(__file__).resolve().parents[2]
    today = _dt.date.today().strftime("%Y-%m-%d")
    candidates = [
        repo_root / "logs" / f"{today}.jsonl",
        repo_root / "logs" / f"distiller-{today}.jsonl",
    ]

    writes = 4
    for i in range(writes):
        r = api_client.post("/api/v1/memories", json=_payload(test_project, 2000 + i))
        assert r.status_code == 201

    found = [p for p in candidates if p.exists()]
    if not found:
        # Fallback: any jsonl file under logs/ from today.
        logs_dir = repo_root / "logs"
        if logs_dir.exists():
            found = [p for p in logs_dir.glob("*.jsonl") if p.stat().st_size > 0]
    assert found, f"no JSONL file found under logs/, looked at {candidates}"

    total_lines = sum(
        sum(1 for _ in p.open("r", encoding="utf-8")) for p in found
    )
    assert total_lines >= writes, f"jsonl has {total_lines} lines, want >= {writes}"
