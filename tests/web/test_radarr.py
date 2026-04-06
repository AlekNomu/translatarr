"""Tests for translatarr_web.radarr — metadata fetch and sync."""

from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest

from translatarr_web.database import _SCHEMA
from translatarr_web.radarr import build_metadata_row, sync_movie_metadata


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


def _insert_movie(
    db: sqlite3.Connection,
    title: str,
    file_path: str,
    year: int = 2010,
) -> None:
    db.execute(
        """INSERT INTO media_items (media_type, file_path, title, year)
           VALUES ('movie', ?, ?, ?)""",
        (file_path, title, year),
    )
    db.commit()


_RADARR_MOVIES = [
    {
        "id": 1,
        "title": "Inception",
        "year": 2010,
        "overview": "A thief who steals corporate secrets.",
        "images": [
            {"coverType": "poster", "url": "/mediacover/1/poster.jpg"},
            {"coverType": "fanart", "url": "/mediacover/1/fanart.jpg"},
        ],
        "path": "/movies/Inception (2010)",
        "movieFile": {
            "id": 10,
            "path": "/movies/Inception (2010)/Inception.2010.mkv",
        },
    },
    {
        "id": 2,
        "title": "Interstellar",
        "year": 2014,
        "overview": "A team of explorers travel through a wormhole.",
        "images": [
            {"coverType": "poster", "url": "/mediacover/2/poster.jpg"},
        ],
        "path": "/movies/Interstellar (2014)",
        "movieFile": None,
    },
]

_RADARR_SETTINGS = {
    "radarr_enabled": "1",
    "radarr_host": "radarr",
    "radarr_port": "7878",
    "radarr_api_key": "testkey",
    "radarr_http_timeout": "10",
}


# ─────────────────────────────────────────────────────────────────────────────
# build_metadata_row
# ─────────────────────────────────────────────────────────────────────────────

class TestBuildMetadataRow:
    def test_extracts_poster(self):
        row = build_metadata_row(_RADARR_MOVIES[0])
        assert row["poster_url"] == "/mediacover/1/poster.jpg"

    def test_extracts_overview(self):
        row = build_metadata_row(_RADARR_MOVIES[0])
        assert row["overview"] == "A thief who steals corporate secrets."

    def test_extracts_movie_path(self):
        row = build_metadata_row(_RADARR_MOVIES[0])
        assert row["movie_path"] == "/movies/Inception (2010)"

    def test_handles_missing_images(self):
        movie = {**_RADARR_MOVIES[0], "images": []}
        row = build_metadata_row(movie)
        assert row["poster_url"] is None

    def test_handles_no_movie_file(self):
        row = build_metadata_row(_RADARR_MOVIES[1])  # movieFile is None
        assert row["radarr_id"] == 2


# ─────────────────────────────────────────────────────────────────────────────
# sync_movie_metadata
# ─────────────────────────────────────────────────────────────────────────────

class TestSyncMovieMetadata:
    def test_skips_when_radarr_disabled(self, mem_db):
        settings = {**_RADARR_SETTINGS, "radarr_enabled": "0"}
        _insert_movie(mem_db, "Inception", "/movies/Inception (2010)/Inception.2010.mkv")
        count = sync_movie_metadata(mem_db, settings)
        assert count == 0
        assert mem_db.execute("SELECT COUNT(*) FROM movie_metadata").fetchone()[0] == 0

    @patch("translatarr_web.radarr.fetch_movie_list", return_value=_RADARR_MOVIES)
    def test_matches_by_file_path(self, _mock, mem_db):
        _insert_movie(mem_db, "Inception", "/movies/Inception (2010)/Inception.2010.mkv")
        count = sync_movie_metadata(mem_db, _RADARR_SETTINGS)
        assert count == 1
        row = mem_db.execute("SELECT * FROM movie_metadata").fetchone()
        assert row["radarr_id"] == 1

    @patch("translatarr_web.radarr.fetch_movie_list", return_value=_RADARR_MOVIES)
    def test_matches_by_folder_prefix(self, _mock, mem_db):
        # File path differs from Radarr's movieFile.path but folder matches
        _insert_movie(mem_db, "Inception", "/movies/Inception (2010)/Inception.BluRay.mkv")
        count = sync_movie_metadata(mem_db, _RADARR_SETTINGS)
        assert count == 1

    @patch("translatarr_web.radarr.fetch_movie_list", return_value=_RADARR_MOVIES)
    def test_matches_by_title_year_fallback(self, _mock, mem_db):
        # Neither file nor folder matches — fall back to title+year
        _insert_movie(mem_db, "Inception", "/mnt/nas/films/Inception.mkv", year=2010)
        count = sync_movie_metadata(mem_db, _RADARR_SETTINGS)
        assert count == 1

    @patch("translatarr_web.radarr.fetch_movie_list", return_value=_RADARR_MOVIES)
    def test_inserts_metadata_fields(self, _mock, mem_db):
        _insert_movie(mem_db, "Inception", "/movies/Inception (2010)/Inception.2010.mkv")
        sync_movie_metadata(mem_db, _RADARR_SETTINGS)
        row = mem_db.execute("SELECT * FROM movie_metadata").fetchone()
        assert row["overview"] == "A thief who steals corporate secrets."
        assert row["poster_url"] == "/mediacover/1/poster.jpg"
        assert row["movie_path"] == "/movies/Inception (2010)"

    @patch("translatarr_web.radarr.fetch_movie_list", return_value=_RADARR_MOVIES)
    def test_updates_existing_movie(self, _mock, mem_db):
        _insert_movie(mem_db, "Inception", "/movies/Inception (2010)/Inception.2010.mkv")
        mem_db.execute(
            """INSERT INTO movie_metadata (file_path, overview)
               VALUES ('/movies/Inception (2010)/Inception.2010.mkv', 'old overview')"""
        )
        mem_db.commit()
        sync_movie_metadata(mem_db, _RADARR_SETTINGS)
        row = mem_db.execute("SELECT overview FROM movie_metadata").fetchone()
        assert row["overview"] == "A thief who steals corporate secrets."

    @patch("translatarr_web.radarr.fetch_movie_list", side_effect=Exception("unreachable"))
    def test_returns_zero_on_api_failure(self, _mock, mem_db):
        _insert_movie(mem_db, "Inception", "/movies/Inception (2010)/Inception.2010.mkv")
        count = sync_movie_metadata(mem_db, _RADARR_SETTINGS)
        assert count == 0
        assert mem_db.execute("SELECT COUNT(*) FROM movie_metadata").fetchone()[0] == 0

    @patch("translatarr_web.radarr.fetch_movie_list", return_value=_RADARR_MOVIES)
    def test_skips_unmatched_movies(self, _mock, mem_db):
        _insert_movie(mem_db, "Unknown Film", "/movies/Unknown Film (1999)/film.mkv", year=1999)
        count = sync_movie_metadata(mem_db, _RADARR_SETTINGS)
        assert count == 0

    @patch("translatarr_web.radarr.fetch_movie_list", return_value=[
        {
            "id": 99,
            "title": "Avatar: Fire and Ash",
            "year": 2025,
            "overview": "The next chapter.",
            "images": [],
            "path": "/movies/Avatar - Fire and Ash (2025)",
            "movieFile": {"id": 99, "path": "/movies/Avatar - Fire and Ash (2025)/Avatar.mkv"},
        }
    ])
    def test_matches_colon_title_via_dash_folder_name(self, _mock, mem_db):
        """Radarr stores 'Avatar: Fire and Ash' but the folder (and our title) uses ' - '."""
        _insert_movie(
            mem_db,
            "Avatar - Fire and Ash",
            "/mnt/nas/Avatar - Fire and Ash (2025)/Avatar.mkv",
            year=2025,
        )
        count = sync_movie_metadata(mem_db, _RADARR_SETTINGS)
        assert count == 1
        row = mem_db.execute("SELECT title FROM media_items").fetchone()
        assert row["title"] == "Avatar: Fire and Ash"
