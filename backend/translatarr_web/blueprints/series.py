"""
/api/series — browse TV series and trigger subtitle generation.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from translatarr_web.database import get_db
from translatarr_web.media import delete_subtitle_for_media

bp = Blueprint("series", __name__, url_prefix="/api/series")


@bp.route("", methods=["GET"])
def list_series():
    """Return distinct series with episode counts and subtitle coverage."""
    db = get_db()
    rows = db.execute("""
        SELECT
            series_name,
            COUNT(*)                              AS episode_count,
            SUM(has_target_srt)                   AS subtitled_count,
            MIN(season)                           AS first_season,
            MAX(season)                           AS last_season
        FROM media_items
        WHERE media_type = 'episode' AND series_name IS NOT NULL
        GROUP BY series_name
        ORDER BY series_name
    """).fetchall()

    return jsonify([
        {
            "series_name": r["series_name"],
            "episode_count": r["episode_count"],
            "subtitled_count": r["subtitled_count"],
            "first_season": r["first_season"],
            "last_season": r["last_season"],
        }
        for r in rows
    ])


@bp.route("/<path:name>", methods=["GET"])
def series_detail(name: str):
    """Return all episodes for a given series, grouped by season."""
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

    return jsonify({
        "series_name": name,
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
