"""
translatarr.transcriber
~~~~~~~~~~~~~~~~~~~
Speech-to-text transcription using faster-whisper.
"""

from __future__ import annotations

from pathlib import Path

from translatarr.models import SubtitleTrack

try:
    from faster_whisper import WhisperModel  # type: ignore
except ImportError:
    WhisperModel = None  # type: ignore


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
    """Transcribe *wav_path* with Whisper via faster-whisper.

    :returns: ``(track, detected_language)`` tuple.
    :raises RuntimeError: If *faster-whisper* is not installed or transcription
                          yields no segments.
    """
    if WhisperModel is None:
        raise RuntimeError(
            "'faster-whisper' is not installed.\n"
            "    Run: pip install faster-whisper"
        )

    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    options: dict = {}
    if language:
        options["language"] = language

    segments_gen, info = model.transcribe(str(wav_path), **options)

    # faster-whisper returns a lazy generator — consume it once
    segments = list(segments_gen)
    if not segments:
        raise RuntimeError("No segments produced. Check that the file contains audio.")

    track = SubtitleTrack.from_whisper_segments(segments)
    return track, info.language
