"""
/api/history — paginated history of subtitle operations.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from translatarr_web.database import get_db

bp = Blueprint("history", __name__, url_prefix="/api/history")


@bp.route("", methods=["GET"])
def list_history():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    action_filter = request.args.get("action")

    page = max(1, page)
    per_page = max(1, min(per_page, 200))
    offset = (page - 1) * per_page

    db = get_db()

    base_query = """
        SELECT h.id, h.media_id, h.file_path, h.action, h.target_lang,
               h.detail, h.created_at,
               m.title AS media_title, m.series_name
        FROM history h
        LEFT JOIN media_items m ON h.media_id = m.id
    """
    count_query = "SELECT COUNT(*) AS cnt FROM history h"
    params: list = []
    if action_filter:
        base_query += " WHERE h.action = ?"
        count_query += " WHERE h.action = ?"
        params.append(action_filter)

    rows = db.execute(
        base_query + " ORDER BY h.created_at DESC LIMIT ? OFFSET ?",
        (*params, per_page, offset),
    ).fetchall()

    total_row = db.execute(count_query, params).fetchone()
    total = total_row["cnt"]

    return jsonify({
        "items": [
            {
                "id": r["id"],
                "media_id": r["media_id"],
                "file_path": r["file_path"],
                "action": r["action"],
                "target_lang": r["target_lang"],
                "detail": r["detail"],
                "created_at": r["created_at"],
                "media_title": r["media_title"],
                "series_name": r["series_name"],
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    })
