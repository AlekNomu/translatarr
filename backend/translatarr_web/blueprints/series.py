"""
/api/series — browse TV series and trigger subtitle generation.
"""

from __future__ import annotations

import urllib.parse
import urllib.request

from flask import Blueprint, Response, current_app, jsonify, request

from translatarr_web.database import get_db
from translatarr_web.media import delete_subtitle_for_media
from translatarr_web.settings import load_settings

bp = Blueprint("series", __name__, url_prefix="/api/series")


@bp.route("/sonarr-image")
def sonarr_image():
    """Proxy a Sonarr media cover image (poster, fanart) through the backend."""
    path = request.args.get("path", "")
    if not path or not path.startswith("/"):
        return "", 400
    db = get_db()
    settings = load_settings(db)
    if settings.get("sonarr_enabled", "0") != "1":
        return "", 404
    host = settings.get("sonarr_host", "sonarr")
    port = settings.get("sonarr_port", "8989")
    api_key = settings.get("sonarr_api_key", "")
    try:
        timeout = int(settings.get("sonarr_http_timeout", "60"))
    except ValueError:
        timeout = 60
    url = f"http://{host}:{port}{path}"
    req = urllib.request.Request(url, headers={"X-Api-Key": api_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return Response(resp.read(), content_type=content_type)
    except Exception:
        return "", 404


def _proxy_poster(raw: str | None) -> str | None:
    if not raw:
        return None
    return f"/api/series/sonarr-image?path={urllib.parse.quote(raw)}"


@bp.route("", methods=["GET"])
def list_series():
    """Return distinct series with episode counts, subtitle coverage, and poster URL."""
    db = get_db()
    rows = db.execute("""
        SELECT
            m.series_name,
            COUNT(*)                              AS episode_count,
            SUM(m.has_target_srt)                 AS subtitled_count,
            MIN(m.season)                         AS first_season,
            MAX(m.season)                         AS last_season,
            sm.poster_url
        FROM media_items m
        LEFT JOIN series_metadata sm ON sm.series_name = m.series_name
        WHERE m.media_type = 'episode' AND m.series_name IS NOT NULL
        GROUP BY m.series_name
        ORDER BY m.series_name
    """).fetchall()

    return jsonify([
        {
            "series_name": r["series_name"],
            "episode_count": r["episode_count"],
            "subtitled_count": r["subtitled_count"],
            "first_season": r["first_season"],
            "last_season": r["last_season"],
            "poster_url": _proxy_poster(r["poster_url"]),
        }
        for r in rows
    ])


@bp.route("/<path:name>", methods=["GET"])
def series_detail(name: str):
    """Return all episodes and metadata for a given series."""
    db = get_db()
    rows = db.execute("""
        SELECT id, title, season, episode, file_path,
               has_source_srt, source_srt_label, has_target_srt, target_srt_path,
               file_size, duration
        FROM media_items
        WHERE media_type = 'episode' AND series_name = ?
        ORDER BY season, episode
    """, (name,)).fetchall()

    if not rows:
        return jsonify({"error": "Series not found"}), 404

    episodes = [
        {
            "id": r["id"],
            "title": r["title"],
            "season": r["season"],
            "episode": r["episode"],
            "file_path": r["file_path"],
            "has_source_srt": bool(r["has_source_srt"]),
            "source_srt_label": r["source_srt_label"],
            "has_target_srt": bool(r["has_target_srt"]),
            "target_srt_path": r["target_srt_path"],
            "file_size": r["file_size"],
            "duration": r["duration"],
        }
        for r in rows
    ]

    meta_row = db.execute(
        "SELECT poster_url, overview, status, last_aired, series_path FROM series_metadata WHERE series_name = ?",
        (name,),
    ).fetchone()

    metadata = (
        {
            "poster_url": _proxy_poster(meta_row["poster_url"]),
            "overview": meta_row["overview"],
            "status": meta_row["status"],
            "last_aired": meta_row["last_aired"],
            "series_path": meta_row["series_path"],
        }
        if meta_row else None
    )

    return jsonify({
        "series_name": name,
        "metadata": metadata,
        "episodes": episodes,
    })


@bp.route("/<path:name>/generate", methods=["POST"])
def generate_series(name: str):
    """Queue subtitle generation for all episodes missing target SRT."""
    db = get_db()
    rows = db.execute("""
        SELECT id FROM media_items
        WHERE media_type = 'episode' AND series_name = ? AND has_target_srt = 0
    """, (name,)).fetchall()

    if not rows:
        return jsonify({"message": "No episodes need subtitles"}), 200

    tm = current_app.extensions["task_manager"]
    task_ids = [tm.submit_subtitle(r["id"]) for r in rows]
    return jsonify({"task_ids": task_ids, "queued": len(task_ids)}), 202


@bp.route("/<path:name>/seasons/<int:season>/generate", methods=["POST"])
def generate_season(name: str, season: int):
    """Queue subtitle generation for all episodes in a season missing target SRT."""
    db = get_db()
    rows = db.execute("""
        SELECT id FROM media_items
        WHERE media_type = 'episode' AND series_name = ? AND season = ? AND has_target_srt = 0
    """, (name, season)).fetchall()

    if not rows:
        return jsonify({"message": "No episodes need subtitles"}), 200

    tm = current_app.extensions["task_manager"]
    task_ids = [tm.submit_subtitle(r["id"]) for r in rows]
    return jsonify({"task_ids": task_ids, "queued": len(task_ids)}), 202


@bp.route("/<path:name>/episodes/<int:media_id>/generate", methods=["POST"])
def generate_episode(name: str, media_id: int):
    """Queue subtitle generation for a single episode."""
    db = get_db()
    row = db.execute(
        "SELECT id FROM media_items WHERE id = ? AND series_name = ? AND media_type = 'episode'",
        (media_id, name),
    ).fetchone()
    if not row:
        return jsonify({"error": "Episode not found in this series"}), 404
    tm = current_app.extensions["task_manager"]
    task_id = tm.submit_subtitle(media_id)
    return jsonify({"task_id": task_id}), 202



# ── Delete subtitle endpoints ─────────────────────────────────────────────────

@bp.route("/<path:name>/episodes/<int:media_id>/subtitle", methods=["DELETE"])
def delete_episode_subtitle(name: str, media_id: int):
    """Delete the generated subtitle for a single episode."""
    db = get_db()
    row = db.execute(
        "SELECT id FROM media_items WHERE id = ? AND series_name = ? AND media_type = 'episode'",
        (media_id, name),
    ).fetchone()
    if not row:
        return jsonify({"error": "Episode not found in this series"}), 404
    deleted = delete_subtitle_for_media(db, media_id)
    if deleted is None:
        return jsonify({"error": "No generated subtitle found"}), 404
    db.commit()
    return jsonify({"deleted": deleted})


@bp.route("/<path:name>/seasons/<int:season>/subtitle", methods=["DELETE"])
def delete_season_subtitle(name: str, season: int):
    """Delete generated subtitles for all episodes in a season."""
    db = get_db()
    rows = db.execute(
        "SELECT id FROM media_items WHERE media_type = 'episode' AND series_name = ? AND season = ? AND has_target_srt = 1",
        (name, season),
    ).fetchall()
    if not rows:
        return jsonify({"error": "No generated subtitles found for this season"}), 404

    deleted = [delete_subtitle_for_media(db, r["id"]) for r in rows]
    db.commit()
    return jsonify({"deleted": [d for d in deleted if d], "count": len(deleted)})


@bp.route("/<path:name>/subtitle", methods=["DELETE"])
def delete_series_subtitle(name: str):
    """Delete generated subtitles for all episodes of a series."""
    db = get_db()
    rows = db.execute(
        "SELECT id FROM media_items WHERE media_type = 'episode' AND series_name = ? AND has_target_srt = 1",
        (name,),
    ).fetchall()
    if not rows:
        return jsonify({"error": "No generated subtitles found for this series"}), 404

    deleted = [delete_subtitle_for_media(db, r["id"]) for r in rows]
    db.commit()
    return jsonify({"deleted": [d for d in deleted if d], "count": len(deleted)})
