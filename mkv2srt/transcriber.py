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
    wav_path:   Path,
    model_name: str = "medium",
    language:   str | None = None,
) -> SubtitleTrack:
    """
    Transcribe *wav_path* with Whisper and return a :class:`~mkv2srt.models.SubtitleTrack`.

    :param wav_path:    Path to a 16 kHz mono WAV file.
    :param model_name:  Whisper model size (``tiny`` → ``large``).
    :param language:    BCP-47 language code of the audio (e.g. ``"en"``).
                        Whisper auto-detects when ``None``.
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

    print(f"Loading Whisper model '{model_name}' …")
    model = whisper.load_model(model_name)

    options: dict = {}
    if language:
        options["language"] = language

    print("Transcribing … (this may take a few minutes)")
    result = model.transcribe(str(wav_path), **options)

    detected_lang = result.get("language", "unknown")
    print(f"Detected language: {detected_lang}")

    segments = result.get("segments", [])
    if not segments:
        sys.exit("No segments produced. Check that the file contains audio.")

    track = SubtitleTrack.from_whisper_segments(segments)
    print(f"Transcription complete — {len(track)} segments.")
    return track
