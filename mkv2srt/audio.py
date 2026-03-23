"""
mkv2srt.audio
~~~~~~~~~~~~~
Audio and subtitle extraction from MKV (and other video) files via ffmpeg.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


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
        sys.exit(
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


# ─────────────────────────────────────────────────────────────────────────────
# Extraction
# ─────────────────────────────────────────────────────────────────────────────

def extract_audio(video_path: Path, wav_path: Path) -> None:
    """
    Extract the first audio track from *video_path* and write it as a
    16 kHz mono PCM WAV to *wav_path*.

    The WAV format (16 kHz / mono / 16-bit) is the optimal input for Whisper.

    :param video_path: Source video file (MKV, MP4, AVI, …).
    :param wav_path:   Destination WAV file.
    :raises SystemExit: If ffmpeg exits with a non-zero return code.
    """
    print(f"Extracting audio  {video_path.name} → {wav_path.name}")

    cmd = [
        "ffmpeg", "-y",
        "-i",      str(video_path),
        "-vn",                       # drop video stream
        "-acodec", "pcm_s16le",      # 16-bit PCM
        "-ar",     "16000",          # 16 kHz sample rate
        "-ac",     "1",              # mono
        str(wav_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ffmpeg failed:\n{result.stderr}")

    print("Audio extracted successfully.")


# ─────────────────────────────────────────────────────────────────────────────
# Embedded subtitle extraction
# ─────────────────────────────────────────────────────────────────────────────

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

    TEXT_CODECS = {"subrip", "srt", "ass", "ssa", "webvtt", "mov_text"}

    # Filter to text-based subtitle streams only
    text_streams = [s for s in streams if s.get("codec_name", "") in TEXT_CODECS]
    if not text_streams:
        return None

    # Try to find an English track
    for s in text_streams:
        lang = s.get("tags", {}).get("language", "").lower()
        if lang in ("en", "eng", "english"):
            return s["index"]

    # Fallback: first text subtitle track
    return text_streams[0]["index"]


def extract_subtitle(video_path: Path, stream_index: int, srt_path: Path) -> None:
    """Extract a subtitle stream from *video_path* to an SRT file."""
    print(f"Extracting embedded subtitle (stream #{stream_index}) → {srt_path.name}")

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-map", f"0:{stream_index}",
        "-c:s", "srt",
        str(srt_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ffmpeg subtitle extraction failed:\n{result.stderr}")

    print("Subtitle extracted successfully.")
