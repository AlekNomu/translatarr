"""
/api/movies — browse movies and trigger subtitle generation.
"""

from __future__ import annotations

import urllib.parse
import urllib.request

from flask import Blueprint, Response, current_app, jsonify, request

from translatarr_web.database import get_db
from translatarr_web.media import delete_subtitle_for_media
from translatarr_web.settings import load_settings

bp = Blueprint("movies", __name__, url_prefix="/api/movies")


@bp.route("/radarr-image")
def radarr_image():
    """Proxy a Radarr media cover image through the backend."""
    path = request.args.get("path", "")
    if not path or not path.startswith("/"):
        return "", 400
    db = get_db()
    settings = load_settings(db)
    if settings.get("radarr_enabled", "0") != "1":
        return "", 404
    host = settings.get("radarr_host", "radarr")
    port = settings.get("radarr_port", "7878")
    api_key = settings.get("radarr_api_key", "")
    try:
        timeout = int(settings.get("radarr_http_timeout", "60"))
    except ValueError:
        timeout = 60
    # Strip cache-busting query params; pass apikey as query param (required for /MediaCover/)
    image_path = path.split("?")[0]
    url = f"http://{host}:{port}{image_path}?apikey={urllib.parse.quote(api_key)}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return Response(resp.read(), content_type=content_type)
    except Exception:
        return "", 404


def _proxy_poster(raw: str | None) -> str | None:
    if not raw:
        return None
    return f"/api/movies/radarr-image?path={urllib.parse.quote(raw)}"


def _movie_row(r) -> dict:
    raw_poster = r["poster_url"] if "poster_url" in r.keys() else None
    return {
        "id": r["id"],
        "title": r["title"],
        "year": r["year"],
        "file_path": r["file_path"],
        "has_source_srt": bool(r["has_source_srt"]),
        "source_srt_label": r["source_srt_label"],
        "has_target_srt": bool(r["has_target_srt"]),
        "target_srt_path": r["target_srt_path"],
        "file_size": r["file_size"],
        "duration": r["duration"],
        "poster_url": _proxy_poster(raw_poster),
    }


@bp.route("", methods=["GET"])
def list_movies():
    db = get_db()
    rows = db.execute("""
        SELECT m.id, m.title, m.year, m.file_path,
               m.has_source_srt, m.source_srt_label, m.has_target_srt, m.target_srt_path,
               m.file_size, m.duration,
               mm.poster_url
        FROM media_items m
        LEFT JOIN movie_metadata mm ON mm.file_path = m.file_path
        WHERE m.media_type = 'movie'
        ORDER BY m.title
    """).fetchall()
    return jsonify([_movie_row(r) for r in rows])


@bp.route("/<int:movie_id>", methods=["GET"])
def movie_detail(movie_id: int):
    db = get_db()
    row = db.execute("""
        SELECT id, title, year, file_path,
               has_source_srt, source_srt_label, has_target_srt, target_srt_path,
               file_size, duration
        FROM media_items
        WHERE id = ? AND media_type = 'movie'
    """, (movie_id,)).fetchone()

    if not row:
        return jsonify({"error": "Movie not found"}), 404

    meta_row = db.execute(
        "SELECT poster_url, overview, movie_path FROM movie_metadata WHERE file_path = ?",
        (row["file_path"],),
    ).fetchone()

    metadata = (
        {
            "poster_url": _proxy_poster(meta_row["poster_url"]),
            "overview": meta_row["overview"],
            "movie_path": meta_row["movie_path"],
        }
        if meta_row else None
    )

    result = _movie_row(row)
    result["metadata"] = metadata
    return jsonify(result)


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
