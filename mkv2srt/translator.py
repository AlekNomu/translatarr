"""
mkv2srt.translator
~~~~~~~~~~~~~~~~~~
Subtitle translation via Google Translate (deep-translator, no API key needed).

Translation is performed in batches to reduce network round-trips while
staying within Google Translate's per-request size limits.
"""

from __future__ import annotations

import sys
import time
from dataclasses import replace

from mkv2srt.models import Subtitle, SubtitleTrack


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

#: Internal separator used to join/split batch texts.
#: Unlikely to appear in real subtitle text.
_SEP = " |||SEP||| "

#: Default number of subtitles sent per translation request.
_DEFAULT_BATCH_SIZE = 20

#: Delay (seconds) between individual fallback requests.
_FALLBACK_DELAY = 0.1


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def translate_track(
    track:       SubtitleTrack,
    source_lang: str = "auto",
    target_lang: str = "fr",
    batch_size:  int = _DEFAULT_BATCH_SIZE,
) -> SubtitleTrack:
    """
    Return a new :class:`~mkv2srt.models.SubtitleTrack` with all subtitle
    texts translated to *target_lang*.

    Timings are preserved exactly — only the ``text`` field is modified.

    :param track:       Source subtitle track.
    :param source_lang: BCP-47 source language, or ``"auto"`` for detection.
    :param target_lang: BCP-47 target language (default ``"fr"``).
    :param batch_size:  Number of subtitles per translation request.
    :raises SystemExit: If *deep-translator* is not installed.
    """
    _require_deep_translator()
    from deep_translator import GoogleTranslator  # type: ignore

    translator = GoogleTranslator(source=source_lang, target=target_lang)
    subtitles  = list(track)
    total      = len(subtitles)

    print(f"Translating {total} subtitles to '{target_lang}' ...")

    translated: list[Subtitle] = []
    for start in range(0, total, batch_size):
        batch = subtitles[start : start + batch_size]
        parts = _translate_batch(translator, batch)
        for sub, new_text in zip(batch, parts):
            translated.append(replace(sub, text=new_text.strip()))

        done = min(start + batch_size, total)
        print(f"    {done}/{total}", end="\r")

    print()
    print(f"Translation complete — {total} subtitles.")
    return SubtitleTrack(subtitles=translated)


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers
# ─────────────────────────────────────────────────────────────────────────────

def _require_deep_translator() -> None:
    try:
        import deep_translator  # noqa: F401
    except ImportError:
        sys.exit(
            "'deep-translator' is not installed.\n"
            "    Run: pip install deep-translator"
        )


def _translate_batch(translator, batch: list[Subtitle]) -> list[str]:
    """
    Translate a batch of subtitles in a single request.

    Falls back to one-by-one translation if the separator is not preserved
    correctly in the response (can happen with very short texts or special
    characters).
    """
    combined = _SEP.join(sub.text for sub in batch)
    try:
        result = translator.translate(combined)
        parts  = result.split("|||SEP|||")
        if len(parts) == len(batch):
            return parts
        # Mismatch: separator was mangled — fall through to per-sub mode
    except Exception:
        pass

    return _translate_one_by_one(translator, batch)


def _translate_one_by_one(translator, batch: list[Subtitle]) -> list[str]:
    """Translate each subtitle individually, preserving the original on error."""
    parts: list[str] = []
    for sub in batch:
        try:
            parts.append(translator.translate(sub.text))
        except Exception:
            parts.append(sub.text)   # keep original rather than losing the line
        time.sleep(_FALLBACK_DELAY)
    return parts
