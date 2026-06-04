"""Verify the FK ON DELETE RESTRICT actually fires."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_cannot_delete_project_with_zones(test_project, db_engine, make_zone):
    """projects -> project_modules has ON DELETE RESTRICT."""
    make_zone()  # create at least one module bound to the project
    with pytest.raises(IntegrityError):
        with db_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM projects WHERE project_id=:pid"),
                {"pid": test_project},
            )


def test_zone_progress_requires_existing_module(clean_db, db_engine):
    """zone_progress.zone_name FK must reject unknown zones."""
    bogus = f"ghost-zone-{uuid.uuid4().hex[:8]}"
    with pytest.raises(IntegrityError):
        with db_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO zone_progress(zone_name, status, completion_pct, "
                    "reported_by) VALUES (:zn, 'in_progress', 0, 'tester')"
                ),
                {"zn": bogus},
            )
