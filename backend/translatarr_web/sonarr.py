"""
translatarr_web.sonarr
~~~~~~~~~~~~~~~~~~
Sonarr API integration: fetch and sync series metadata into series_metadata.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import urllib.request

logger = logging.getLogger("translatarr")


# ─────────────────────────────────────────────────────────────────────────────
# Sonarr API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_series_list(host: str, port: str, api_key: str, timeout: int) -> list[dict]:
    """Fetch all series from Sonarr API v3.

    :raises urllib.error.URLError: On network failure.
    :raises urllib.error.HTTPError: On HTTP error.
    """
    url = f"http://{host}:{port}/api/v3/series"
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def build_metadata_row(sonarr_series: dict, base_url: str = "") -> dict:
    """Extract storable metadata fields from a Sonarr series object."""
    images = {img["coverType"]: img["url"] for img in sonarr_series.get("images", [])}

    def _abs(url: str | None) -> str | None:
        if url and url.startswith("/"):
            return base_url + url
        return url

    return {
        "sonarr_id":   sonarr_series.get("id"),
        "overview":    sonarr_series.get("overview") or "",
        "poster_url":  _abs(images.get("poster")),
        "fanart_url":  _abs(images.get("fanart")),
        "status":      sonarr_series.get("status"),
        "last_aired":  sonarr_series.get("previousAiring"),
        "series_path": sonarr_series.get("path"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Sync
# ─────────────────────────────────────────────────────────────────────────────

def sync_series_metadata(db: sqlite3.Connection, settings: dict) -> int:
    """Sync series_metadata for all series present in media_items.

    Triggered only from the scan pipeline. Each call makes exactly one request
    to the Sonarr API to retrieve all series at once.

    Matching strategy (in priority order):
    1. Path-based: an episode's file_path starts with a Sonarr series path.
    2. Title-based: series_name matches Sonarr title (case-insensitive).

    :returns: Number of series inserted or updated.
    """
    if settings.get("sonarr_enabled", "0") != "1":
        return 0

    host = settings.get("sonarr_host", "sonarr")
    port = settings.get("sonarr_port", "8989")
    api_key = settings.get("sonarr_api_key", "")
    try:
        timeout = int(settings.get("sonarr_http_timeout", "60"))
    except ValueError:
        timeout = 60

    try:
        sonarr_list = fetch_series_list(host, port, api_key, timeout)
    except Exception as exc:
        logger.warning("Sonarr metadata sync failed: %s", exc)
        return 0

    # Build lookup maps: by normalised path prefix and by lowercase title
    by_path: dict[str, dict] = {}
    by_title: dict[str, dict] = {}
    by_title_norm: dict[str, dict] = {}
    for s in sonarr_list:
        path = (s.get("path") or "").rstrip("/")
        if path:
            by_path[path] = s
        title = s.get("title", "")
        by_title[title.lower()] = s
        # Colon titles like "Foo: Bar" are stored on disk as "Foo - Bar"
        by_title_norm[title.lower().replace(": ", " - ")] = s

    # One sample episode path per series to enable path-based matching
    rows = db.execute(
        """SELECT series_name, MIN(file_path) AS sample_path
           FROM media_items
           WHERE media_type = 'episode' AND series_name IS NOT NULL
           GROUP BY series_name"""
    ).fetchall()

    updated = 0
    for row in rows:
        series_name: str = row["series_name"]
        sample_path: str = row["sample_path"]

        # ── Phase 1: path-based match
        match = None
        for sonarr_path, s in by_path.items():
            if sample_path.startswith(sonarr_path):
                match = s
                break

        # ── Phase 2: title-based fallback
        if match is None:
            match = by_title.get(series_name.lower())

        # ── Phase 3: normalised title (colon → dash)
        if match is None:
            match = by_title_norm.get(series_name.lower())

        if match is None:
            continue

        meta = build_metadata_row(match, base_url=f"http://{host}:{port}")
        db.execute(
            """INSERT INTO series_metadata
                   (series_name, sonarr_id, overview, poster_url, fanart_url,
                    status, last_aired, series_path, fetched_at)
               VALUES
                   (:series_name, :sonarr_id, :overview, :poster_url, :fanart_url,
                    :status, :last_aired, :series_path, datetime('now'))
               ON CONFLICT(series_name) DO UPDATE SET
                   sonarr_id   = excluded.sonarr_id,
                   overview    = excluded.overview,
                   poster_url  = excluded.poster_url,
                   fanart_url  = excluded.fanart_url,
                   status      = excluded.status,
                   last_aired  = excluded.last_aired,
                   series_path = excluded.series_path,
                   fetched_at  = excluded.fetched_at""",
            {"series_name": series_name, **meta},
        )
        updated += 1

    db.commit()
    return updated
