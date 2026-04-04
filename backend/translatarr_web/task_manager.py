"""
translatarr_web.task_manager
~~~~~~~~~~~~~~~~~~~~~~~~
Background task queue for subtitle generation and library scanning.

Uses a :class:`~concurrent.futures.ThreadPoolExecutor` to run pipeline jobs
without blocking the Flask request thread.  Each task is tracked in the
``tasks`` SQLite table and can be polled or streamed via SSE.
"""

from __future__ import annotations

import logging
import sqlite3
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from flask import Flask

from translatarr.pipeline import run_from_mkv
from translatarr_web.database import get_db
from translatarr_web.scanner import scan_library
from translatarr_web.settings import load_settings
from translatarr_web.jellyfin import refresh_library
from translatarr_web.radarr import sync_movie_metadata
from translatarr_web.sonarr import sync_series_metadata

logger = logging.getLogger("translatarr")

# ─────────────────────────────────���───────────────────────────────────────────
# Task manager
# ───���─────────────────────��─────────────────────────────��─────────────────────


class TaskManager:
    """Singleton that owns the worker pool and the in-flight task registry."""

    def __init__(self, app: Flask, max_workers: int = 4) -> None:
        self._app = app
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    # ── Public API ────────────────────────────────────────────────────────

    def submit_scan(self) -> str:
        """Queue a library scan.  Returns the task id.

        If a scan is already queued or running, returns its existing task id
        instead of creating a duplicate.
        """
        with self._app.app_context():
            db = get_db()
            existing = db.execute(
                "SELECT id FROM tasks WHERE task_type = 'scan' AND status IN ('queued', 'running') LIMIT 1"
            ).fetchone()
            if existing:
                return existing["id"]
        task_id = self._create_task("scan")
        self._executor.submit(self._run_scan, task_id)
        return task_id

    def submit_subtitle(self, media_id: int) -> str:
        """Queue subtitle generation for a single media item.  Returns the task id."""
        task_id = self._create_task("generate_subtitle", media_id=media_id)
        self._executor.submit(self._run_subtitle, task_id, media_id)
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """Mark a queued task as cancelled. Returns True if it was queued, False otherwise."""
        with self._app.app_context():
            db = get_db()
            cur = db.execute(
                "UPDATE tasks SET status = 'cancelled', finished_at = datetime('now') WHERE id = ? AND status = 'queued'",
                (task_id,),
            )
            db.commit()
            return cur.rowcount > 0

    def list_tasks(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._app.app_context():
            db = get_db()
            rows = db.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._app.app_context():
            db = get_db()
            row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            return dict(row) if row else None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)

    # ── Workers ───────────���───────────────────────────────────────────────

    def _run_scan(self, task_id: str) -> None:
        with self._app.app_context():
            db = get_db()
            row = db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row and row["status"] == "cancelled":
                return
            self._update_task(db, task_id, status="running")
            try:
                settings = load_settings(db)
                result = scan_library(
                    db,
                    series_path=settings.get("series_path", "/tv"),
                    movies_path=settings.get("movies_path", "/movies"),
                    target_lang=settings.get("target_lang", "fr"),
                )
                detail = f"added={result.added}, updated={result.updated}, removed={result.removed}"
                self._update_task(db, task_id, status="completed", progress=100, detail=detail)

                # ── Sonarr metadata sync (new or updated series)
                synced = sync_series_metadata(db, settings)
                if synced:
                    detail += f", sonarr: {synced} series synced"

                # ── Radarr metadata sync (new or updated movies)
                synced_movies = sync_movie_metadata(db, settings)
                if synced_movies:
                    detail += f", radarr: {synced_movies} movies synced"

                if synced or synced_movies:
                    db.execute("UPDATE tasks SET detail = ? WHERE id = ?", (detail, task_id))
                    db.commit()

                if settings.get("generate_after_scan", "0") == "1":
                    pending = db.execute(
                        """SELECT id FROM media_items
                        WHERE has_target_srt = 0
                        AND id NOT IN (
                            SELECT media_id FROM tasks
                            WHERE task_type = 'generate_subtitle'
                            AND status IN ('queued', 'running')
                            AND media_id IS NOT NULL
                        )"""
                    ).fetchall()
                    for row in pending:
                        self.submit_subtitle(row["id"])
                    detail += f", queued {len(pending)} subtitle job(s)"
                    db.execute("UPDATE tasks SET detail = ? WHERE id = ?", (detail, task_id))
                    db.commit()
            except Exception as exc:
                logger.error("Scan failed: %s", exc)
                self._update_task(db, task_id, status="failed", detail=str(exc))

    def _run_subtitle(self, task_id: str, media_id: int) -> None:
        with self._app.app_context():
            db = get_db()
            row = db.execute("SELECT status FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row and row["status"] == "cancelled":
                return
            self._update_task(db, task_id, status="running")

            row = db.execute(
                "SELECT * FROM media_items WHERE id = ?", (media_id,)
            ).fetchone()
            if not row:
                self._update_task(db, task_id, status="failed", detail="Media not found")
                return

            media_title = row["title"] or Path(row["file_path"]).name
            self._update_task(db, task_id, detail=media_title)

            settings = load_settings(db)
            mkv_path = Path(row["file_path"])
            target_lang = settings.get("target_lang", "fr")

            output_path = _resolve_output(mkv_path, target_lang)

            def on_progress(done: int, total: int) -> None:
                pct = int(done / total * 100) if total else 0
                with self._app.app_context():
                    d = get_db()
                    self._update_task(d, task_id, progress=pct)

            try:
                result = run_from_mkv(
                    mkv_path, output_path,
                    target_lang=target_lang,
                    model=settings.get("whisper_model", "medium"),
                    language=settings.get("source_language") or None,
                    sync_check=settings.get("sync_check", "1") == "1",
                    on_progress=on_progress,
                )

                action = result or "skipped"
                self._update_task(db, task_id, status="completed", progress=100)

                # Record in history
                db.execute(
                    """INSERT INTO history (media_id, file_path, action, target_lang, detail)
                    VALUES (?, ?, ?, ?, ?)""",
                    (media_id, str(mkv_path), action, target_lang, str(output_path)),
                )
                # Update media_items subtitle status
                if result:
                    db.execute(
                        """UPDATE media_items
                        SET has_target_srt = 1, target_srt_path = ?, updated_at = datetime('now')
                        WHERE id = ?""",
                        (str(output_path), media_id),
                    )
                db.commit()

                # ── Jellyfin refresh when the subtitle queue drains
                if result:
                    remaining = db.execute(
                        """SELECT COUNT(*) FROM tasks
                           WHERE task_type = 'generate_subtitle'
                           AND status IN ('queued', 'running')"""
                    ).fetchone()[0]
                    if remaining == 0 and refresh_library(settings):
                        logger.info("Jellyfin library refresh triggered")

            except Exception as exc:
                logger.error("Subtitle generation failed for %s: %s", mkv_path.name, exc)
                self._update_task(db, task_id, status="failed", detail=str(exc))
                db.execute(
                    """INSERT INTO history (media_id, file_path, action, target_lang, detail)
                    VALUES (?, ?, 'failed', ?, ?)""",
                    (media_id, str(mkv_path), target_lang, str(exc)),
                )
                db.commit()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _create_task(self, task_type: str, media_id: int | None = None) -> str:
        task_id = str(uuid.uuid4())
        with self._app.app_context():
            db = get_db()
            db.execute(
                """INSERT INTO tasks (id, task_type, media_id, status, progress, created_at)
                VALUES (?, ?, ?, 'queued', 0, datetime('now'))""",
                (task_id, task_type, media_id),
            )
            db.commit()
        return task_id

    def _update_task(
        self, db: sqlite3.Connection, task_id: str, **fields: Any
    ) -> None:
        sets: list[str] = []
        values: list[Any] = []
        for key, val in fields.items():
            sets.append(f"{key} = ?")
            values.append(val)
        if "status" in fields and fields["status"] == "running":
            sets.append("started_at = datetime('now')")
        if "status" in fields and fields["status"] in ("completed", "failed"):
            sets.append("finished_at = datetime('now')")
        values.append(task_id)
        db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", values)
        db.commit()


# ──��───────────────────────────��──────────────────────────────────────────────
# Output path resolution (mirrors cli._resolve_output)
# ───────────────────────────────────���─────────────────────────────────────────

_OUTPUT_SUFFIXES = (".srt", ".cc.srt", ".sdh.srt")


def _resolve_output(mkv_path: Path, target_lang: str) -> Path:
    stem = mkv_path.stem
    parent = mkv_path.parent
    for suffix in _OUTPUT_SUFFIXES:
        candidate = parent / f"{stem}.{target_lang}{suffix}"
        if not candidate.exists():
            return candidate
    i = 2
    while True:
        candidate = parent / f"{stem}.{target_lang}.{i}.srt"
        if not candidate.exists():
            return candidate
        i += 1
