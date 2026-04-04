"""
translatarr.audio
~~~~~~~~~~~~~
Audio and subtitle extraction from MKV (and other video) files via ffmpeg.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

WHISPER_SAMPLE_RATE = "16000"
TEXT_CODECS = {"subrip", "srt", "ass", "ssa", "webvtt", "mov_text"}


# ─────────────────────────────────────────────────────────────────────────────
# Dependency check
# ─────────────────────────────────────────────────────────────────────────────

def require_ffmpeg() -> None:
    """Raise a clear error if ffmpeg is not available on PATH."""
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            check=True,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg not found. Please install it:\n"
            "    macOS   → brew install ffmpeg\n"
            "    Ubuntu  → sudo apt install ffmpeg\n"
            "    Windows → https://ffmpeg.org/download.html"
        )


def get_duration(video_path: Path) -> float | None:
    """
    Return the duration of a video file in seconds, or ``None`` on failure.

    Uses ``ffprobe`` which ships with ffmpeg.
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None

def extract_audio(video_path: Path, wav_path: Path) -> None:
    """
    Extract the first audio track from *video_path* and write it as a
    16 kHz mono PCM WAV to *wav_path*.

    The WAV format (16 kHz / mono / 16-bit) is the optimal input for Whisper.

    :param video_path: Source video file (MKV, MP4, AVI, …).
    :param wav_path:   Destination WAV file.
    :raises SystemExit: If ffmpeg exits with a non-zero return code.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-vn",                       # drop video stream
        "-acodec", "pcm_s16le",      # 16-bit PCM
        "-ar", WHISPER_SAMPLE_RATE,
        "-ac", "1",                  # mono
        str(wav_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{result.stderr}")

def find_embedded_sub_index(video_path: Path) -> int | None:
    """Return the stream index of the best English subtitle track, or *None*.

    Preference order:
    1. English text-based subtitle (subrip, ass, ssa — not bitmap formats)
    2. Any text-based subtitle track (first one)
    """
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "s",
                "-show_entries", "stream=index,codec_name:stream_tags=language,title",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        return None

    text_streams = [s for s in streams if s.get("codec_name", "") in TEXT_CODECS]
    if not text_streams:
        return None

    for s in text_streams:
        lang = s.get("tags", {}).get("language", "").lower()
        if lang in ("en", "eng", "english"):
            return s["index"]

    return text_streams[0]["index"]


def find_embedded_sub_by_lang(video_path: Path, lang_tags: tuple[str, ...]) -> int | None:
    """Return the stream index of the first embedded text subtitle matching any of the given
    language tags, or *None* if no match is found."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-select_streams", "s",
                "-show_entries", "stream=index,codec_name:stream_tags=language",
                "-of", "json",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except Exception:
        return None

    data = json.loads(result.stdout)
    for s in data.get("streams", []):
        if s.get("codec_name", "") not in TEXT_CODECS:
            continue
        lang = s.get("tags", {}).get("language", "").lower()
        if lang in lang_tags:
            return s["index"]
    return None


def extract_subtitle(video_path: Path, stream_index: int, srt_path: Path) -> None:
    """Extract a subtitle stream from *video_path* to an SRT file."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-map", f"0:{stream_index}",
        "-c:s", "srt",
        str(srt_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg subtitle extraction failed:\n{result.stderr}")
