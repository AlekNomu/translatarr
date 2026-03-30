"""
/api/movies — browse movies and trigger subtitle generation.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify

from translatarr_web.database import get_db
from translatarr_web.media import delete_subtitle_for_media

bp = Blueprint("movies", __name__, url_prefix="/api/movies")


def _movie_row(r) -> dict:
    return {
        "id": r["id"],
        "title": r["title"],
        "year": r["year"],
        "file_path": r["file_path"],
        "has_source_srt": bool(r["has_source_srt"]),
        "has_target_srt": bool(r["has_target_srt"]),
        "target_srt_path": r["target_srt_path"],
        "file_size": r["file_size"],
        "duration": r["duration"],
    }


@bp.route("", methods=["GET"])
def list_movies():
    db = get_db()
    rows = db.execute("""
        SELECT id, title, year, file_path,
               has_source_srt, has_target_srt, target_srt_path,
               file_size, duration
        FROM media_items
        WHERE media_type = 'movie'
        ORDER BY title
    """).fetchall()
    return jsonify([_movie_row(r) for r in rows])


@bp.route("/<int:movie_id>", methods=["GET"])
def movie_detail(movie_id: int):
    db = get_db()
    row = db.execute("""
        SELECT id, title, year, file_path,
               has_source_srt, has_target_srt, target_srt_path,
               file_size, duration
        FROM media_items
        WHERE id = ? AND media_type = 'movie'
    """, (movie_id,)).fetchone()

    if not row:
        return jsonify({"error": "Movie not found"}), 404
    return jsonify(_movie_row(row))


@bp.route("/<int:movie_id>/generate", methods=["POST"])
def generate_movie(movie_id: int):
    """Queue subtitle generation for a movie."""
    tm = current_app.extensions["task_manager"]
    task_id = tm.submit_subtitle(movie_id)
    return jsonify({"task_id": task_id}), 202


@bp.route("/<int:movie_id>/subtitle", methods=["DELETE"])
def delete_movie_subtitle(movie_id: int):
    """Delete the generated subtitle file for a movie and update the DB."""
    db = get_db()
    deleted = delete_subtitle_for_media(db, movie_id)
    if deleted is None:
        return jsonify({"error": "No generated subtitle found"}), 404
    db.commit()
    return jsonify({"deleted": deleted})
