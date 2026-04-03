"""Tests for translatarr_web.sonarr — metadata fetch and sync."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from translatarr_web.database import _SCHEMA
from translatarr_web.sonarr import build_metadata_row, sync_series_metadata


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture()
def mem_db() -> sqlite3.Connection:
    """In-memory DB with the full schema."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _insert_episode(db: sqlite3.Connection, series_name: str, file_path: str) -> None:
    db.execute(
        """INSERT INTO media_items
               (media_type, file_path, title, series_name, season, episode)
           VALUES ('episode', ?, ?, ?, 1, 1)""",
        (file_path, "Pilot", series_name),
    )
    db.commit()


_SONARR_SERIES = [
    {
        "id": 1,
        "title": "Breaking Bad",
        "overview": "A chemistry teacher turns to crime.",
        "status": "ended",
        "previousAiring": "2013-09-29T00:00:00Z",
        "path": "/tv/Breaking Bad (2008)",
        "images": [
            {"coverType": "poster", "url": "/mediacover/1/poster-250.jpg"},
            {"coverType": "fanart", "url": "/mediacover/1/fanart.jpg"},
        ],
    },
    {
        "id": 2,
        "title": "Better Call Saul",
        "overview": "Prequel to Breaking Bad.",
        "status": "ended",
        "previousAiring": "2022-08-15T00:00:00Z",
        "path": "/tv/Better Call Saul (2015)",
        "images": [
            {"coverType": "poster", "url": "/mediacover/2/poster-250.jpg"},
        ],
    },
]

_SONARR_SETTINGS = {
    "sonarr_enabled": "1",
    "sonarr_host": "sonarr",
    "sonarr_port": "8989",
    "sonarr_api_key": "testkey",
    "sonarr_http_timeout": "10",
}


# ─────────────────────────────────────────────────────────────────────────────
# build_metadata_row
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildMetadataRow:
    def test_extracts_poster(self):
        row = build_metadata_row(_SONARR_SERIES[0])
        assert row["poster_url"] == "/mediacover/1/poster-250.jpg"

    def test_extracts_fanart(self):
        row = build_metadata_row(_SONARR_SERIES[0])
        assert row["fanart_url"] == "/mediacover/1/fanart.jpg"

    def test_extracts_overview(self):
        row = build_metadata_row(_SONARR_SERIES[0])
        assert row["overview"] == "A chemistry teacher turns to crime."

    def test_extracts_status(self):
        row = build_metadata_row(_SONARR_SERIES[0])
        assert row["status"] == "ended"

    def test_extracts_last_aired(self):
        row = build_metadata_row(_SONARR_SERIES[0])
        assert row["last_aired"] == "2013-09-29T00:00:00Z"

    def test_extracts_series_path(self):
        row = build_metadata_row(_SONARR_SERIES[0])
        assert row["series_path"] == "/tv/Breaking Bad (2008)"

    def test_handles_missing_images(self):
        series = {**_SONARR_SERIES[0], "images": []}
        row = build_metadata_row(series)
        assert row["poster_url"] is None
        assert row["fanart_url"] is None

    def test_handles_missing_fanart(self):
        row = build_metadata_row(_SONARR_SERIES[1])  # only has poster
        assert row["poster_url"] == "/mediacover/2/poster-250.jpg"
        assert row["fanart_url"] is None


# ─────────────────────────────────────────────────────────────────────────────
# sync_series_metadata
# ─────────────────────────────────────────────────────────────────────────────

class TestSyncSeriesMetadata:
    def test_skips_when_sonarr_disabled(self, mem_db):
        settings = {**_SONARR_SETTINGS, "sonarr_enabled": "0"}
        _insert_episode(mem_db, "Breaking Bad", "/tv/Breaking Bad (2008)/S01E01.mkv")
        count = sync_series_metadata(mem_db, settings)
        assert count == 0
        assert mem_db.execute("SELECT COUNT(*) FROM series_metadata").fetchone()[0] == 0

    @patch("translatarr_web.sonarr.fetch_series_list", return_value=_SONARR_SERIES)
    def test_matches_by_path(self, _mock, mem_db):
        _insert_episode(mem_db, "Breaking Bad", "/tv/Breaking Bad (2008)/Season 1/S01E01.mkv")
        count = sync_series_metadata(mem_db, _SONARR_SETTINGS)
        assert count == 1
        row = mem_db.execute(
            "SELECT * FROM series_metadata WHERE series_name = 'Breaking Bad'"
        ).fetchone()
        assert row is not None
        assert row["sonarr_id"] == 1

    @patch("translatarr_web.sonarr.fetch_series_list", return_value=_SONARR_SERIES)
    def test_matches_by_title_fallback(self, _mock, mem_db):
        # Path doesn't match Sonarr path — must fall back to title matching
        _insert_episode(mem_db, "Breaking Bad", "/mnt/nas/series/Breaking Bad/S01E01.mkv")
        count = sync_series_metadata(mem_db, _SONARR_SETTINGS)
        assert count == 1
        row = mem_db.execute(
            "SELECT series_name FROM series_metadata"
        ).fetchone()
        assert row["series_name"] == "Breaking Bad"

    @patch("translatarr_web.sonarr.fetch_series_list", return_value=_SONARR_SERIES)
    def test_inserts_metadata_fields(self, _mock, mem_db):
        _insert_episode(mem_db, "Breaking Bad", "/tv/Breaking Bad (2008)/S01E01.mkv")
        sync_series_metadata(mem_db, _SONARR_SETTINGS)
        row = mem_db.execute(
            "SELECT * FROM series_metadata WHERE series_name = 'Breaking Bad'"
        ).fetchone()
        assert row["overview"] == "A chemistry teacher turns to crime."
        assert row["poster_url"] == "/mediacover/1/poster-250.jpg"
        assert row["fanart_url"] == "/mediacover/1/fanart.jpg"
        assert row["status"] == "ended"
        assert row["last_aired"] == "2013-09-29T00:00:00Z"
        assert row["series_path"] == "/tv/Breaking Bad (2008)"

    @patch("translatarr_web.sonarr.fetch_series_list", return_value=_SONARR_SERIES)
    def test_updates_existing_series(self, _mock, mem_db):
        _insert_episode(mem_db, "Breaking Bad", "/tv/Breaking Bad (2008)/S01E01.mkv")
        # Pre-seed with stale data
        mem_db.execute(
            """INSERT INTO series_metadata (series_name, status, last_aired)
               VALUES ('Breaking Bad', 'continuing', '2008-01-01')"""
        )
        mem_db.commit()
        sync_series_metadata(mem_db, _SONARR_SETTINGS)
        row = mem_db.execute(
            "SELECT status, last_aired FROM series_metadata WHERE series_name = 'Breaking Bad'"
        ).fetchone()
        assert row["status"] == "ended"
        assert row["last_aired"] == "2013-09-29T00:00:00Z"

    @patch("translatarr_web.sonarr.fetch_series_list", side_effect=Exception("unreachable"))
    def test_returns_zero_on_api_failure(self, _mock, mem_db):
        _insert_episode(mem_db, "Breaking Bad", "/tv/Breaking Bad (2008)/S01E01.mkv")
        count = sync_series_metadata(mem_db, _SONARR_SETTINGS)
        assert count == 0
        assert mem_db.execute("SELECT COUNT(*) FROM series_metadata").fetchone()[0] == 0

    @patch("translatarr_web.sonarr.fetch_series_list", return_value=_SONARR_SERIES)
    def test_skips_unmatched_series(self, _mock, mem_db):
        _insert_episode(mem_db, "Unknown Show", "/tv/Unknown Show/S01E01.mkv")
        count = sync_series_metadata(mem_db, _SONARR_SETTINGS)
        assert count == 0
