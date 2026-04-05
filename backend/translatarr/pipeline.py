"""
translatarr.pipeline
~~~~~~~~~~~~~~~~
Core subtitle pipeline: lookup existing SRTs, decide strategy (resync / translate /
transcribe), and produce a translated SubtitleTrack.
"""

from __future__ import annotations

import logging
import tempfile
import threading
from collections.abc import Callable
from pathlib import Path

from translatarr.audio import (
    extract_audio,
    extract_subtitle,
    find_embedded_sub_index,
    get_duration,
    require_ffmpeg,
)
from translatarr.models import SubtitleTrack
from translatarr.srt_io import read_srt, write_srt
from translatarr.sync_checker import check_sync
from translatarr.transcriber import transcribe
from translatarr.translator import translate_track

__all__ = [
    "find_srt_by_lang", "find_source_srt_with_label",
    "target_srt_tags", "get_english_srt",
    "run_from_srt", "run_from_mkv",
]

logger = logging.getLogger("translatarr")

# Serializes Whisper transcriptions — GPU can only handle one model at a time
whisper_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────────────────────
# Subtitle lookup
# ─────────────────────────────────────────────────────────────────────────────

_EN_SRT_TAGS = ("en", "eng", "english", "")
_HI_MARKERS = ("hi", "sdh", "cc")

# ISO 639 short → common variants for finding existing SRT files
LANG_TAG_ALIASES: dict[str, tuple[str, ...]] = {
    "fr": ("fr", "fre", "french"),
    "en": ("en", "eng", "english"),
    "es": ("es", "spa", "spanish"),
    "de": ("de", "deu", "ger", "german"),
    "it": ("it", "ita", "italian"),
    "pt": ("pt", "por", "portuguese"),
}


def target_srt_tags(lang: str) -> tuple[str, ...]:
    return LANG_TAG_ALIASES.get(lang, (lang,))


def find_srt_by_lang(mkv_path: Path, lang_tags: tuple[str, ...]) -> Path | None:
    """Look for an existing .srt next to the MKV file matching one of the language tags.

    Checks plain (.fr.srt) first, then HI/SDH/CC variants (.fr.hi.srt, .fr.sdh.srt, …).
    """
    stem = mkv_path.stem
    parent = mkv_path.parent
    for tag in lang_tags:
        candidate = parent / f"{stem}.{tag}.srt"
        if candidate.exists():
            return candidate
        for hi in _HI_MARKERS:
            candidate = parent / f"{stem}.{tag}.{hi}.srt"
            if candidate.exists():
                return candidate
    return None


def find_source_srt_with_label(mkv_path: Path) -> str | None:
    """Return a label describing the available English subtitle source, or None.

    Checks in order:
    1. External SRT with HI markers (hi/sdh/cc) → "EN:HI"
    2. Regular external English SRT             → "EN"
    3. Embedded subtitle track via ffprobe       → "EN:EMB"
    """
    stem = mkv_path.stem
    parent = mkv_path.parent

    for tag in ("en", "eng", "english"):
        for hi in _HI_MARKERS:
            if (parent / f"{stem}.{tag}.{hi}.srt").exists():
                return "EN:HI"
        if (parent / f"{stem}.{tag}.srt").exists():
            return "EN"

    if (parent / f"{stem}.srt").exists():
        return "EN"

    # Only call ffprobe when no external SRT found
    sub_index = find_embedded_sub_index(mkv_path)
    if sub_index is not None:
        return "EN:EMB"

    return None


def get_english_srt(mkv_path: Path) -> tuple[Path | None, Path | None]:
    """Find an English .srt (external file or embedded in MKV).

    Returns (english_srt_path, embedded_srt_path).
    embedded_srt_path is set only when extraction was needed (for cleanup).
    """
    existing_srt = find_srt_by_lang(mkv_path, _EN_SRT_TAGS)
    embedded_srt_path: Path | None = None

    if not existing_srt:
        sub_index = find_embedded_sub_index(mkv_path)
        if sub_index is not None:
            tmp = tempfile.NamedTemporaryFile(suffix=".srt", delete=False)
            embedded_srt_path = Path(tmp.name)
            tmp.close()
            extract_subtitle(mkv_path, sub_index, embedded_srt_path)
            existing_srt = embedded_srt_path

    return existing_srt, embedded_srt_path


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline modes
# ─────────────────────────────────────────────────────────────────────────────

def run_from_srt(
    srt_path: Path,
    output_path: Path,
    target_lang: str = "fr",
    mkv_path: Path | None = None,
    sync_check: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
) -> None:
    """Translate an existing SRT file."""
    track = read_srt(srt_path)
    logger.info("Source: %s (%d entries)", srt_path.name, len(track))
    track = translate_track(track, target_lang=target_lang, on_progress=on_progress)

    if sync_check:
        duration = get_duration(mkv_path) if mkv_path else None
        issues = check_sync(track, duration)
        _log_sync(issues)

    write_srt(track, output_path)


def run_from_mkv(
    mkv_path: Path,
    output_path: Path,
    target_lang: str = "fr",
    model: str = "medium",
    language: str | None = None,
    sync_check: bool = True,
    on_progress: Callable[[int, int], None] | None = None,
) -> str | None:
    """Full pipeline from an MKV file.

    Returns the action performed ('translated', 'resynced', 'transcribed'),
    or None if no work was needed (already aligned).
    """
    require_ffmpeg()

    video_duration = get_duration(mkv_path) if sync_check else None

    english_srt, embedded_srt_path = get_english_srt(mkv_path)
    target_srt = find_srt_by_lang(mkv_path, target_srt_tags(target_lang))

    try:
        track, action = _resolve_track(
            mkv_path, english_srt, target_srt, embedded_srt_path,
            target_lang=target_lang, model=model, language=language,
            on_progress=on_progress,
        )
    finally:
        if embedded_srt_path and embedded_srt_path.exists():
            embedded_srt_path.unlink()

    if track is None:
        return None

    if sync_check:
        issues = check_sync(track, video_duration)
        _log_sync(issues)

    write_srt(track, output_path)
    return action


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline strategy
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_track(
    mkv_path: Path,
    english_srt: Path | None,
    target_srt: Path | None,
    embedded_srt_path: Path | None = None,
    *,
    target_lang: str = "fr",
    model: str = "medium",
    language: str | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> tuple[SubtitleTrack | None, str]:
    """Decide which pipeline branch to run and return (track, action).

    Returns (None, 'skipped') when the target and English SRTs are already aligned.
    Action is one of: 'skipped', 'resynced', 'translated', 'transcribed'.
    """
    if target_srt and english_srt:
        en_track = read_srt(english_srt)
        tgt_track = read_srt(target_srt)
        logger.info("Target SRT: %s (%d entries)", target_srt.name, len(tgt_track))
        logger.info("English SRT: %s (%d entries)", english_srt.name, len(en_track))

        if len(en_track) == len(tgt_track):
            if tgt_track.has_same_timestamps(en_track):
                logger.info("Already aligned — nothing to do.")
                return None, "skipped"

            logger.info("Resyncing target timestamps from English…")
            return tgt_track.resync_from(en_track), "resynced"

        logger.info(
            "Entry count mismatch (EN=%d, TGT=%d) — translating EN",
            len(en_track), len(tgt_track),
        )
        return translate_track(
            en_track, source_lang="en", target_lang=target_lang, on_progress=on_progress,
        ), "translated"

    if english_srt:
        track = read_srt(english_srt)
        source = "embedded" if embedded_srt_path else english_srt.name
        logger.info("English SRT: %s (%d entries)", source, len(track))
        return translate_track(
            track, source_lang="en", target_lang=target_lang, on_progress=on_progress,
        ), "translated"

    logger.info("No subtitles found — transcribing with Whisper (%s)", model)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    try:
        logger.info("Extracting audio…")
        extract_audio(mkv_path, wav_path)
        with whisper_lock:
            logger.info("Transcribing…")
            track, detected_lang = transcribe(
                wav_path, model_name=model, language=language,
            )
            logger.info("Detected language: %s — %d segments", detected_lang, len(track))
    finally:
        if wav_path.exists():
            wav_path.unlink()

    return translate_track(
        track, source_lang=language or "auto", target_lang=target_lang,
        on_progress=on_progress,
    ), "transcribed"


# ─────────────────────────────────────────────────────────────────────────────
# Logging helpers
# ─────────────────────────────────────────────────────────────────────────────

def _log_sync(issues: list) -> None:
    if not issues:
        logger.info("Sync check: OK")
    else:
        logger.warning("Sync check: %d issue(s)", len(issues))
        for issue in issues:
            logger.warning("  %s", issue)
