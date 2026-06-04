"""Zone (module) workflow: progress reports, issue reports, review cycle."""
from __future__ import annotations

from sqlalchemy import text


def test_create_module_and_progress(api_client, db_engine, make_zone):
    zone = make_zone()

    payload = {
        "status": "in_progress",
        "completion_pct": 42,
        "current_task": "wiring tests",
        "blockers": [],
        "next_plan": "finish wiring",
        "reported_by": "e2e-agent",
    }
    r = api_client.post(f"/api/v1/zones/{zone}/progress", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["zone_name"] == zone
    assert body["completion_pct"] == 42

    with db_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT zone_name, completion_pct, reported_by FROM zone_progress "
                "WHERE zone_name=:z ORDER BY id DESC LIMIT 1"
            ),
            {"z": zone},
        ).one()
    assert row.zone_name == zone
    assert row.completion_pct == 42
    assert row.reported_by == "e2e-agent"


def test_report_issue_blocker_severity(api_client, db_engine, make_zone):
    zone = make_zone()

    # severity must use schema ENUM values: blocker|major|minor|question.
    payload = {
        "severity": "blocker",
        "title": "build broken",
        "description": "tests cannot run",
        "reported_by": "e2e-agent",
    }
    r = api_client.post(f"/api/v1/zones/{zone}/issues", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["zone_name"] == zone
    assert body["title"] == "build broken"

    with db_engine.connect() as conn:
        sev, title, status = conn.execute(
            text(
                "SELECT severity, title, status FROM issues "
                "WHERE zone_name=:z ORDER BY id DESC LIMIT 1"
            ),
            {"z": zone},
        ).one()
    assert title == "build broken"
    assert sev == "blocker"
    assert status == "open"


def test_review_request_and_submit(api_client, db_engine, make_zone):
    zone = make_zone()

    req_payload = {
        "zone_name": zone,
        "requested_by": "child-agent",
        "notes": "ready for review",
    }
    r1 = api_client.post("/api/v1/reviews", json=req_payload)
    assert r1.status_code == 201, r1.text
    request_id = r1.json()["request_id"]

    submit_payload = {
        "reviewed_by": "supervisor",
        "approved": True,
        "issues": [],
        "summary": "lgtm",
        "checklist_items": [{"item": "tests pass", "ok": True}],
    }
    r2 = api_client.post(
        f"/api/v1/reviews/{request_id}/result", json=submit_payload
    )
    assert r2.status_code == 201, r2.text
    body = r2.json()
    assert body["request_id"] == request_id
    assert body["approved"] is True

    with db_engine.connect() as conn:
        rr_status = conn.execute(
            text("SELECT status FROM review_requests WHERE id=:rid"),
            {"rid": request_id},
        ).scalar_one()
        result_count = conn.execute(
            text("SELECT COUNT(*) FROM review_results WHERE request_id=:rid"),
            {"rid": request_id},
        ).scalar_one()

    assert result_count == 1
    assert rr_status in {"approved", "in_review", "pending"}
