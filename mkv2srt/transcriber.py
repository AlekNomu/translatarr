"""
mkv2srt.transcriber
~~~~~~~~~~~~~~~~~~~
Speech-to-text transcription using OpenAI Whisper.
"""

from __future__ import annotations

import sys
from pathlib import Path
from mkv2srt.models import SubtitleTrack


# ─────────────────────────────────────────────────────────────────────────────
# Whisper transcription
# ─────────────────────────────────────────────────────────────────────────────

#: Available Whisper model sizes ordered from fastest to most accurate.
WHISPER_MODELS = ("tiny", "base", "small", "medium", "large")


def transcribe(
    wav_path: Path,
    model_name: str = "medium",
    language: str | None = None,
) -> tuple[SubtitleTrack, str]:
    """Transcribe *wav_path* with Whisper.

    :returns: ``(track, detected_language)`` tuple.
    :raises SystemExit: If *openai-whisper* is not installed or transcription
                        yields no segments.
    """
    try:
        import whisper  # type: ignore
    except ImportError:
        sys.exit(
            "'openai-whisper' is not installed.\n"
            "    Run: pip install openai-whisper"
        )

    model = whisper.load_model(model_name)

    options: dict = {}
    if language:
        options["language"] = language

    result = model.transcribe(str(wav_path), **options)

    detected_lang = result.get("language", "unknown")
    segments = result.get("segments", [])
    if not segments:
        sys.exit("No segments produced. Check that the file contains audio.")

    track = SubtitleTrack.from_whisper_segments(segments)
    return track, detected_lang
