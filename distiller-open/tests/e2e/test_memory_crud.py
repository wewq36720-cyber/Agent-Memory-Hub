"""Memory CRUD via REST: /api/v1/memories POST + GET."""
from __future__ import annotations

import uuid


MEMORY_TYPES = [
    "preference",
    "fact",
    "decision",
    "context",
    "reference",
    "acceptance_criteria",
    "verification_result",
]


def _write_payload(project_id: str, mtype: str, title: str, summary: str) -> dict:
    return {
        "project_id": project_id,
        "memory_type": mtype,
        "title": title,
        "summary": summary,
        "content": summary,
        "importance": 3,
        "agent_name": "e2e-test",
    }


def test_write_all_memory_types(api_client, test_project):
    """All 7 canonical memory_type values must accept and return distinct IDs."""
    seen_ids: set[int] = set()
    for mtype in MEMORY_TYPES:
        payload = _write_payload(
            test_project, mtype, f"title-{mtype}", f"summary for {mtype}"
        )
        r = api_client.post("/api/v1/memories", json=payload)
        assert r.status_code == 201, f"{mtype}: {r.status_code} {r.text}"
        body = r.json()
        assert "memory_id" in body
        assert body["memory_id"] not in seen_ids
        seen_ids.add(body["memory_id"])
    assert len(seen_ids) == 7


def test_write_memory_returns_trace_id(api_client, test_project):
    payload = _write_payload(test_project, "fact", "trace-id-test", "checking trace_id")
    r = api_client.post("/api/v1/memories", json=payload)
    assert r.status_code == 201
    body = r.json()
    tid = body["trace_id"]
    # Must be a valid UUID string.
    parsed = uuid.UUID(tid)
    assert str(parsed) == tid


def test_search_memory_chinese(api_client, test_project):
    """ngram FULLTEXT must recall a Chinese-content memory."""
    payload = _write_payload(
        test_project,
        "preference",
        "中文偏好",
        "用户偏好中文回复，请使用简体中文沟通。",
    )
    r = api_client.post("/api/v1/memories", json=payload)
    assert r.status_code == 201

    r2 = api_client.get(
        "/api/v1/memories",
        params={"project_id": test_project, "q": "中文", "top_k": 5},
    )
    assert r2.status_code == 200
    rows = r2.json()
    assert len(rows) >= 1
    assert any("中文" in (row.get("title") or "") + (row.get("content") or "")
               for row in rows)


def test_search_memory_top_k_limit(api_client, test_project):
    """Writing 10 memories then searching with top_k=3 must return <=3."""
    for i in range(10):
        payload = _write_payload(
            test_project, "fact", f"topk-fact-{i}", f"topkneedle marker {i}"
        )
        r = api_client.post("/api/v1/memories", json=payload)
        assert r.status_code == 201

    r = api_client.get(
        "/api/v1/memories",
        params={"project_id": test_project, "q": "topkneedle", "top_k": 3},
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) <= 3


def test_write_invalid_memory_type_400(api_client, test_project):
    """Pydantic Literal validation must reject unknown memory_type with 422."""
    payload = _write_payload(test_project, "fact", "bad", "bad")
    payload["memory_type"] = "not_a_real_type"
    r = api_client.post("/api/v1/memories", json=payload)
    assert r.status_code == 422
