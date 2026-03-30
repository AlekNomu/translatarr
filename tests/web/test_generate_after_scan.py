"""Tests for the generate_after_scan setting."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from translatarr_web.scanner import ScanResult
from translatarr_web.settings import save_settings
from translatarr_web.translatarr import create_app
from tests.web.conftest import insert_movie

_FAKE_SCAN = ScanResult(added=0, updated=0, removed=0, unchanged=0)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def gen_app(config_dir):
    """App with a real TaskManager (task_manager is NOT mocked)."""
    application = create_app(config_dir=config_dir, _testing=True)
    application.config["TESTING"] = True
    yield application
    application.extensions["scheduler"].shutdown(wait=False)
    application.extensions["task_manager"].shutdown()


@pytest.fixture()
def gen_db(gen_app):
    """Direct SQLite connection to the test app's database."""
    db_path = Path(gen_app.config["DB_PATH"])
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ── Helper ────────────────────────────────────────────────────────────────────

def _wait_scan(tm, task_id: str, timeout: float = 5.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        task = tm.get_task(task_id)
        if task and task["status"] in ("completed", "failed"):
            return task
        time.sleep(0.05)
    return tm.get_task(task_id)


# ── Tests ─────────────────────────────────────────────────────────────────────

@patch("translatarr_web.task_manager.run_from_mkv", return_value="translated")
@patch("translatarr_web.task_manager.scan_library", return_value=_FAKE_SCAN)
def test_enabled_queues_subtitle_tasks(mock_scan, mock_run, gen_app, gen_db):
    """When generate_after_scan=1, one subtitle task is queued per pending media item."""
    insert_movie(gen_db, has_target_srt=0)
    insert_movie(gen_db, file_path="/movies/Other (2020).mkv", title="Other", has_target_srt=0)
    save_settings(gen_db, {"generate_after_scan": "1"})

    tm = gen_app.extensions["task_manager"]
    task_id = tm.submit_scan()
    task = _wait_scan(tm, task_id)

    assert task["status"] == "completed"
    assert "queued 2 subtitle job(s)" in task["detail"]

    tasks = tm.list_tasks(limit=100)
    subtitle_tasks = [t for t in tasks if t["task_type"] == "generate_subtitle"]
    assert len(subtitle_tasks) == 2


@patch("translatarr_web.task_manager.scan_library", return_value=_FAKE_SCAN)
def test_disabled_queues_nothing(mock_scan, gen_app, gen_db):
    """When generate_after_scan=0 (default), no subtitle tasks are queued after scan."""
    insert_movie(gen_db, has_target_srt=0)
    # generate_after_scan defaults to "0" — no explicit set needed

    tm = gen_app.extensions["task_manager"]
    task_id = tm.submit_scan()
    task = _wait_scan(tm, task_id)

    assert task["status"] == "completed"
    assert "subtitle" not in (task["detail"] or "")

    tasks = tm.list_tasks(limit=100)
    subtitle_tasks = [t for t in tasks if t["task_type"] == "generate_subtitle"]
    assert len(subtitle_tasks) == 0


@patch("translatarr_web.task_manager.scan_library", return_value=_FAKE_SCAN)
def test_concurrent_scan_deduplicates(mock_scan, gen_app, gen_db):
    """submit_scan() returns the existing task id when a scan is already queued or running."""
    with gen_app.app_context():
        from translatarr_web.database import get_db
        db = get_db()
        db.execute(
            "INSERT INTO tasks (id, task_type, status, progress, created_at)"
            " VALUES ('existing-scan-id', 'scan', 'queued', 0, datetime('now'))"
        )
        db.commit()

    tm = gen_app.extensions["task_manager"]
    returned_id = tm.submit_scan()
    assert returned_id == "existing-scan-id"


@patch("translatarr_web.task_manager.scan_library", return_value=_FAKE_SCAN)
def test_concurrent_scan_running_deduplicates(mock_scan, gen_app, gen_db):
    """submit_scan() also deduplicates when a scan is already running."""
    with gen_app.app_context():
        from translatarr_web.database import get_db
        db = get_db()
        db.execute(
            "INSERT INTO tasks (id, task_type, status, progress, created_at)"
            " VALUES ('running-scan-id', 'scan', 'running', 50, datetime('now'))"
        )
        db.commit()

    tm = gen_app.extensions["task_manager"]
    returned_id = tm.submit_scan()
    assert returned_id == "running-scan-id"


@patch("translatarr_web.task_manager.scan_library", return_value=_FAKE_SCAN)
def test_generate_after_scan_skips_already_active_subtitle_jobs(mock_scan, gen_app, gen_db):
    """Media with an already queued/running subtitle job is not re-queued."""
    media_id = insert_movie(gen_db, has_target_srt=0)
    save_settings(gen_db, {"generate_after_scan": "1"})

    with gen_app.app_context():
        from translatarr_web.database import get_db
        db = get_db()
        db.execute(
            "INSERT INTO tasks (id, task_type, media_id, status, progress, created_at)"
            " VALUES ('existing-subtitle-id', 'generate_subtitle', ?, 'queued', 0, datetime('now'))",
            (media_id,),
        )
        db.commit()

    tm = gen_app.extensions["task_manager"]
    task_id = tm.submit_scan()
    task = _wait_scan(tm, task_id)

    assert task["status"] == "completed"
    assert "queued 0 subtitle job(s)" in task["detail"]

    tasks = tm.list_tasks(limit=100)
    subtitle_tasks = [t for t in tasks if t["task_type"] == "generate_subtitle"]
    assert len(subtitle_tasks) == 1  # only the pre-existing one, no duplicate


@patch("translatarr_web.task_manager.run_from_mkv", return_value="translated")
@patch("translatarr_web.task_manager.scan_library", return_value=_FAKE_SCAN)
def test_enabled_no_pending_media(mock_scan, mock_run, gen_app, gen_db):
    """When generate_after_scan=1 but all media already have subtitles, 0 tasks are queued."""
    insert_movie(gen_db, has_target_srt=1)
    save_settings(gen_db, {"generate_after_scan": "1"})

    tm = gen_app.extensions["task_manager"]
    task_id = tm.submit_scan()
    task = _wait_scan(tm, task_id)

    assert task["status"] == "completed"
    assert "queued 0 subtitle job(s)" in task["detail"]

    tasks = tm.list_tasks(limit=100)
    subtitle_tasks = [t for t in tasks if t["task_type"] == "generate_subtitle"]
    assert len(subtitle_tasks) == 0
