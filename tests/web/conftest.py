"""Shared fixtures for translatarr_web tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from translatarr_web.translatarr import create_app


@pytest.fixture()
def config_dir(tmp_path: Path) -> Path:
    return tmp_path / "config"


@pytest.fixture()
def app(config_dir: Path):
    """Flask app with an isolated SQLite database and a mock task manager."""
    application = create_app(config_dir=config_dir, _testing=True)
    application.config["TESTING"] = True

    real_tm = application.extensions["task_manager"]

    mock_tm = MagicMock()
    mock_tm.submit_scan.return_value = "scan-task-id"
    mock_tm.submit_subtitle.return_value = "subtitle-task-id"
    mock_tm.list_tasks.return_value = []
    mock_tm.get_task.return_value = None
    application.extensions["task_manager"] = mock_tm

    yield application

    application.extensions["scheduler"].shutdown(wait=False)
    real_tm.shutdown()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    """Direct SQLite connection for test setup/assertions."""
    db_path = Path(app.config["DB_PATH"])
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


# ─── Media helpers ────────────────────────────────────────────────────────────

def insert_movie(db: sqlite3.Connection, **kwargs) -> int:
    defaults = dict(
        media_type="movie",
        file_path="/movies/Inception (2010).mkv",
        title="Inception",
        year=2010,
        series_name=None,
        season=None,
        episode=None,
        has_source_srt=0,
        has_target_srt=0,
        target_srt_path=None,
        file_size=1000,
        duration=9180.0,
    )
    defaults.update(kwargs)
    cur = db.execute(
        """INSERT INTO media_items (media_type, file_path, title, year, series_name,
           season, episode, has_source_srt, has_target_srt, target_srt_path,
           file_size, duration)
           VALUES (:media_type, :file_path, :title, :year, :series_name,
           :season, :episode, :has_source_srt, :has_target_srt, :target_srt_path,
           :file_size, :duration)""",
        defaults,
    )
    db.commit()
    return cur.lastrowid


def insert_episode(db: sqlite3.Connection, **kwargs) -> int:
    defaults = dict(
        media_type="episode",
        file_path="/tv/Show/Season 1/Show S01E01.mkv",
        title="Pilot",
        year=None,
        series_name="Show",
        season=1,
        episode=1,
        has_source_srt=0,
        has_target_srt=0,
        target_srt_path=None,
        file_size=800,
        duration=2700.0,
    )
    defaults.update(kwargs)
    cur = db.execute(
        """INSERT INTO media_items (media_type, file_path, title, year, series_name,
           season, episode, has_source_srt, has_target_srt, target_srt_path,
           file_size, duration)
           VALUES (:media_type, :file_path, :title, :year, :series_name,
           :season, :episode, :has_source_srt, :has_target_srt, :target_srt_path,
           :file_size, :duration)""",
        defaults,
    )
    db.commit()
    return cur.lastrowid


def insert_history(db: sqlite3.Connection, **kwargs) -> int:
    defaults = dict(
        media_id=None,
        file_path="/movies/Inception (2010).mkv",
        action="translated",
        target_lang="fr",
        detail=None,
    )
    defaults.update(kwargs)
    cur = db.execute(
        """INSERT INTO history (media_id, file_path, action, target_lang, detail)
           VALUES (:media_id, :file_path, :action, :target_lang, :detail)""",
        defaults,
    )
    db.commit()
    return cur.lastrowid
