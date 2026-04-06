"""
translatarr_web.scanner
~~~~~~~~~~~~~~~~~~~
Discover MKV files in the configured movies and series directories,
parse metadata from filenames, and synchronise the ``media_items`` table.
"""

from __future__ import annotations

import datetime
import logging
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from translatarr.audio import find_embedded_sub_by_lang
from translatarr.pipeline import find_source_srt_with_label, find_srt_by_lang, target_srt_tags

logger = logging.getLogger("translatarr")

# ─────────────────────────────────────────────────────────────────────────────
# Filename parsers
# ─────────────────────────────────────────────────────────────────────────────

_EPISODE_RE = re.compile(r"[Ss](\d+)[Ee](\d+)")
_YEAR_PAREN_RE = re.compile(r"\((\d{4})\)")
_YEAR_SEP_RE = re.compile(r"(?<=\s)(\d{4})(?=\s|$)")
# Sonarr-style: "Show Name (2022) - S01E03 - Episode Title (...).mkv"
_SONARR_RE = re.compile(
    r"^(?P<series>.+?)\s*\(\d{4}\)\s*-\s*S(?P<season>\d+)E(?P<episode>\d+)"
    r"\s*-\s*(?P<title>.+?)(?:\s*\(.*\))*\.(?:mkv|mp4)$",
    re.IGNORECASE,
)


def _parse_episode(path: Path) -> dict | None:
    """Try to parse series/season/episode from a filename."""
    name = path.name
    m = _SONARR_RE.match(name)
    if m:
        return {
            "series_name": m.group("series").strip(),
            "season": int(m.group("season")),
            "episode": int(m.group("episode")),
            "title": m.group("title").strip(),
        }

    m = _EPISODE_RE.search(name)
    if m:
        series_name = path.parent.parent.name if path.parent.name.lower().startswith("season") \
            else path.parent.name
        return {
            "series_name": series_name,
            "season": int(m.group(1)),
            "episode": int(m.group(2)),
            "title": name,
        }
    return None


def _parse_movie_title(path: Path) -> tuple[str, int | None]:
    """Extract title and optional year from a movie filename."""
    stem = path.stem
    m = _YEAR_PAREN_RE.search(stem)
    if m:
        return stem[: m.start()].strip(), int(m.group(1))
    clean = stem.replace(".", " ")
    m = _YEAR_SEP_RE.search(clean)
    if m:
        year_val = int(m.group(1))
        if 1900 <= year_val <= datetime.date.today().year + 1:
            return clean[: m.start()].strip(), year_val
    return clean, None


# ─────────────────────────────────────────────────────────────────────────────
# Scanner
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ScanResult:
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0


_VIDEO_GLOBS = ("*.mkv", "*.mp4")


def scan_library(
    db: sqlite3.Connection,
    series_path: str,
    movies_path: str,
    target_lang: str = "fr",
) -> ScanResult:
    """Walk *series_path* and *movies_path*, sync ``media_items`` table.

    Returns counts of added / updated / removed / unchanged items.
    """
    result = ScanResult()

    series_dir = Path(series_path)
    movies_dir = Path(movies_path)

    discovered: dict[str, dict] = {}

    if series_dir.is_dir():
        for glob in _VIDEO_GLOBS:
            for mkv in series_dir.rglob(glob):
                ep = _parse_episode(mkv)
                if ep:
                    discovered[str(mkv)] = {
                        "media_type": "episode",
                        "file_path": str(mkv),
                        "title": ep["title"],
                        "series_name": ep["series_name"],
                        "season": ep["season"],
                        "episode": ep["episode"],
                        "year": None,
                    }
                else:
                    logger.debug("Skipping unrecognised file in series directory: %s", mkv.name)

    if movies_dir.is_dir():
        for glob in _VIDEO_GLOBS:
            for mkv in movies_dir.rglob(glob):
                title, year = _parse_movie_title(mkv)
                discovered[str(mkv)] = {
                    "media_type": "movie",
                    "file_path": str(mkv),
                    "title": title,
                    "year": year,
                    "series_name": None,
                    "season": None,
                    "episode": None,
                }

    # ── Check subtitle presence for discovered files ──────────────────────
    lang_tags = target_srt_tags(target_lang)
    for file_path, meta in discovered.items():
        mkv = Path(file_path)
        source_label = find_source_srt_with_label(mkv)
        meta["has_source_srt"] = 1 if source_label else 0
        meta["source_srt_label"] = source_label
        target_srt = find_srt_by_lang(mkv, lang_tags)
        has_target = bool(target_srt) or find_embedded_sub_by_lang(mkv, lang_tags) is not None
        meta["has_target_srt"] = 1 if has_target else 0
        meta["target_srt_path"] = str(target_srt) if target_srt else None
        try:
            meta["file_size"] = mkv.stat().st_size
        except OSError:
            meta["file_size"] = None

    # ── Sync with database ────────────────────────────────────────────────
    existing_rows = db.execute("SELECT id, file_path FROM media_items").fetchall()
    existing_map = {row["file_path"]: row["id"] for row in existing_rows}

    for file_path, meta in discovered.items():
        if file_path in existing_map:
            existing_id = existing_map[file_path]
            current = db.execute(
                "SELECT has_source_srt, source_srt_label, has_target_srt, target_srt_path, file_size FROM media_items WHERE id = ?",
                (existing_id,),
            ).fetchone()
            if (
                current["has_source_srt"] != meta["has_source_srt"]
                or current["source_srt_label"] != meta["source_srt_label"]
                or current["has_target_srt"] != meta["has_target_srt"]
                or current["target_srt_path"] != meta["target_srt_path"]
                or current["file_size"] != meta["file_size"]
            ):
                db.execute(
                    """UPDATE media_items SET
                        has_source_srt = ?, source_srt_label = ?,
                        has_target_srt = ?, target_srt_path = ?,
                        file_size = ?, updated_at = datetime('now')
                    WHERE id = ?""",
                    (
                        meta["has_source_srt"], meta["source_srt_label"],
                        meta["has_target_srt"], meta["target_srt_path"],
                        meta["file_size"], existing_id,
                    ),
                )
                result.updated += 1
            else:
                result.unchanged += 1
        else:
            db.execute(
                """INSERT INTO media_items
                    (media_type, file_path, title, year, series_name, season, episode,
                     has_source_srt, source_srt_label, has_target_srt, target_srt_path, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    meta["media_type"], meta["file_path"], meta["title"],
                    meta["year"], meta["series_name"], meta["season"],
                    meta["episode"], meta["has_source_srt"], meta["source_srt_label"],
                    meta["has_target_srt"], meta["target_srt_path"],
                    meta["file_size"],
                ),
            )
            result.added += 1

    # Remove entries for files that no longer exist on disk
    discovered_paths = set(discovered.keys())
    for file_path, row_id in existing_map.items():
        if file_path not in discovered_paths:
            srt_row = db.execute(
                "SELECT target_srt_path FROM media_items WHERE id = ? AND has_target_srt = 1",
                (row_id,),
            ).fetchone()
            if srt_row and srt_row["target_srt_path"]:
                srt_path = Path(srt_row["target_srt_path"])
                if srt_path.exists():
                    srt_path.unlink()
            db.execute("DELETE FROM media_items WHERE id = ?", (row_id,))
            result.removed += 1

    db.commit()

    logger.info(
        "Scan complete: %d added, %d updated, %d removed",
        result.added, result.updated, result.removed,
    )
    return result
