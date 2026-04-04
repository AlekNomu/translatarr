"""
translatarr_web.radarr
~~~~~~~~~~~~~~~~~~
Radarr API integration: fetch and sync movie metadata into movie_metadata.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import urllib.request

logger = logging.getLogger("translatarr")


# ─────────────────────────────────────────────────────────────────────────────
# Radarr API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_movie_list(host: str, port: str, api_key: str, timeout: int) -> list[dict]:
    """Fetch all movies from Radarr API v3.

    :raises urllib.error.URLError: On network failure.
    :raises urllib.error.HTTPError: On HTTP error.
    """
    url = f"http://{host}:{port}/api/v3/movie"
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def build_metadata_row(radarr_movie: dict, base_url: str = "") -> dict:
    """Extract storable metadata fields from a Radarr movie object."""
    images = {img["coverType"]: img["url"] for img in radarr_movie.get("images", [])}

    def _abs(url: str | None) -> str | None:
        if url and url.startswith("/"):
            return base_url + url
        return url

    return {
        "radarr_id":  radarr_movie.get("id"),
        "overview":   radarr_movie.get("overview") or "",
        "poster_url": _abs(images.get("poster")),
        "movie_path": radarr_movie.get("path"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Sync
# ─────────────────────────────────────────────────────────────────────────────

def sync_movie_metadata(db: sqlite3.Connection, settings: dict) -> int:
    """Sync movie_metadata for all movies present in media_items.

    Triggered only from the scan pipeline. Each call makes exactly one request
    to the Radarr API to retrieve all movies at once.

    Matching strategy (in priority order):
    1. File-based: Radarr's movieFile.path matches media_items.file_path exactly.
    2. Folder-based: media_items.file_path starts with Radarr's movie path.
    3. Title+year: title and year match (case-insensitive fallback).

    :returns: Number of movies inserted or updated.
    """
    if settings.get("radarr_enabled", "0") != "1":
        return 0

    host = settings.get("radarr_host", "radarr")
    port = settings.get("radarr_port", "7878")
    api_key = settings.get("radarr_api_key", "")
    try:
        timeout = int(settings.get("radarr_http_timeout", "60"))
    except ValueError:
        timeout = 60

    try:
        radarr_list = fetch_movie_list(host, port, api_key, timeout)
    except Exception as exc:
        logger.warning("Radarr metadata sync failed: %s", exc)
        return 0

    # Build lookup maps
    by_file: dict[str, dict] = {}    # movieFile.path → movie
    by_folder: dict[str, dict] = {}  # path (folder) → movie
    by_title_year: dict[tuple, dict] = {}  # (title.lower(), year) → movie

    for m in radarr_list:
        movie_file = m.get("movieFile") or {}
        file_path = movie_file.get("path", "")
        if file_path:
            by_file[file_path] = m
        folder = (m.get("path") or "").rstrip("/")
        if folder:
            by_folder[folder] = m
        by_title_year[(m.get("title", "").lower(), m.get("year"))] = m

    rows = db.execute(
        "SELECT file_path, title, year FROM media_items WHERE media_type = 'movie'"
    ).fetchall()

    updated = 0
    for row in rows:
        file_path: str = row["file_path"]
        title: str = row["title"] or ""
        year = row["year"]

        # ── Phase 1: exact file match
        match = by_file.get(file_path)

        # ── Phase 2: folder prefix match
        if match is None:
            for folder, m in by_folder.items():
                if file_path.startswith(folder):
                    match = m
                    break

        # ── Phase 3: title + year fallback
        if match is None:
            match = by_title_year.get((title.lower(), year))

        if match is None:
            continue

        meta = build_metadata_row(match, base_url=f"http://{host}:{port}")
        db.execute(
            """INSERT INTO movie_metadata
                   (file_path, radarr_id, overview, poster_url, movie_path, fetched_at)
               VALUES
                   (:file_path, :radarr_id, :overview, :poster_url, :movie_path, datetime('now'))
               ON CONFLICT(file_path) DO UPDATE SET
                   radarr_id  = excluded.radarr_id,
                   overview   = excluded.overview,
                   poster_url = excluded.poster_url,
                   movie_path = excluded.movie_path,
                   fetched_at = excluded.fetched_at""",
            {"file_path": file_path, **meta},
        )
        updated += 1

    db.commit()
    return updated
