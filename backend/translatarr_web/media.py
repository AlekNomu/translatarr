"""
translatarr_web.media
~~~~~~~~~~~~~~~~~~~~~
Shared helpers for media-item operations that touch both the filesystem and the DB.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from translatarr_web.settings import load_setting


def delete_subtitle_for_media(db: sqlite3.Connection, media_id: int) -> str | None:
    """Delete the SRT file and clear DB fields for *media_id*.

    Returns the deleted path string, or ``None`` if the item had no subtitle.
    Does **not** call ``db.commit()`` — the caller is responsible.
    """
    row = db.execute(
        "SELECT file_path, target_srt_path FROM media_items WHERE id = ? AND has_target_srt = 1",
        (media_id,),
    ).fetchone()
    if not row:
        return None

    srt_path = Path(row["target_srt_path"])
    if srt_path.exists():
        srt_path.unlink()

    target_lang = load_setting(db, "target_lang")
    db.execute(
        "UPDATE media_items SET has_target_srt = 0, target_srt_path = NULL, updated_at = datetime('now') WHERE id = ?",
        (media_id,),
    )
    db.execute(
        "INSERT INTO history (media_id, file_path, action, target_lang, detail) VALUES (?, ?, 'deleted', ?, ?)",
        (media_id, row["file_path"], target_lang, str(srt_path)),
    )
    return str(srt_path)
