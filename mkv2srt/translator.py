"""
mkv2srt.translator
~~~~~~~~~~~~~~~~~~
Subtitle translation via Google Translate (deep-translator, no API key needed).

Translation is performed in batches to reduce network round-trips while
staying within Google Translate's per-request size limits.
"""

from __future__ import annotations

import re
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

#: Matches HTML/SRT formatting tags like <i>, </b>, <font color="#fff">
_TAG_PATTERN = re.compile(r"</?[a-zA-Z][^>]*>")

#: Matches SDH/CC annotations: [music], (laughing), ♪ lyrics ♪
_SDH_PATTERN = re.compile(r"\[.*?\]|\(.*?\)|♪.*?♪", re.DOTALL)


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

    Multi-line subtitle texts are joined into a single line before batching
    so that Google Translate treats each entry as one coherent phrase.
    After translation, results are re-wrapped to the original line count.

    Falls back to one-by-one translation if the separator is not preserved
    correctly in the response (can happen with very short texts or special
    characters).
    """
    # Dialogues, multi-line texts, SDH annotations and HTML tags need
    # special handling — route through one-by-one for correctness.
    needs_special = any(
        "\n" in sub.text
        or _is_sdh(sub.text)
        or _TAG_PATTERN.search(sub.text)
        for sub in batch
    )
    if needs_special:
        return _translate_one_by_one(translator, batch)

    combined = _SEP.join(sub.text for sub in batch)
    try:
        result = translator.translate(combined)
        parts  = result.split("|||SEP|||")
        if len(parts) == len(batch):
            return [part.strip() for part in parts]
        # Mismatch: separator was mangled — fall through to per-sub mode
    except Exception:
        pass

    return _translate_one_by_one(translator, batch)


def _translate_one_by_one(translator, batch: list[Subtitle]) -> list[str]:
    """Translate each subtitle individually, preserving the original on error."""
    parts: list[str] = []
    for sub in batch:
        try:
            parts.append(_translate_single(translator, sub.text))
        except Exception:
            # Keep original rather than losing the line
            parts.append(sub.text)
        time.sleep(_FALLBACK_DELAY)
    return parts


def _translate_single(translator, text: str) -> str:
    """Translate a single subtitle text, handling SDH annotations and HTML tags."""
    # SDH/CC annotations (e.g. [music], ♪ lyrics ♪) — keep as-is
    if _is_sdh(text):
        return text

    # Strip HTML tags, translate clean text, restore tags
    clean, prefix, suffix = _strip_tags(text)
    if not clean.strip():
        return text

    translated = _translate_multiline(translator, clean)
    return _restore_tags(translated, prefix, suffix)


def _strip_tags(text: str) -> tuple[str, str, str]:
    """Remove HTML tags from *text*.

    Returns (clean_text, prefix_tags, suffix_tags) where prefix/suffix
    contain the opening/closing tags that wrapped the text.

    For example ``<i>Hello world</i>`` → ``("Hello world", "<i>", "</i>")``.
    """
    # Collect leading tags (opening)
    prefix = ""
    tmp = text
    while True:
        m = _TAG_PATTERN.match(tmp)
        if not m:
            break
        prefix += m.group()
        tmp = tmp[m.end():]

    # Collect trailing tags (closing) from the end
    suffix = ""
    while True:
        m = re.search(r"</?[a-zA-Z][^>]*>\s*$", tmp)
        if not m:
            break
        suffix = m.group().strip() + suffix
        tmp = tmp[:m.start()]

    # Remove any remaining inline tags
    clean = _TAG_PATTERN.sub("", tmp)
    return clean, prefix, suffix


def _restore_tags(text: str, prefix: str, suffix: str) -> str:
    """Re-wrap translated text with its original HTML tags."""
    return prefix + text + suffix


def _is_sdh(text: str) -> bool:
    """Return True if the text is purely an SDH/CC annotation with no
    actual dialogue (e.g. ``[music playing]``, ``♪ theme song ♪``)."""
    stripped = _SDH_PATTERN.sub("", text).strip()
    return len(stripped) == 0 and len(text.strip()) > 0


def _is_dialogue(lines: list[str]) -> bool:
    """Detect dialogue lines: all non-empty lines start with ``-``."""
    return all(line.strip().startswith("-") for line in lines if line.strip())


def _translate_multiline(translator, text: str) -> str:
    """Translate multi-line subtitle text, handling both dialogues and
    wrapped sentences correctly.

    **Dialogue** (each line starts with ``-``)::

        -Yeah.
        -Come on, buddy.

    Each speaker's line is translated independently, preserving the ``-``
    prefix and the line structure.

    **Wrapped sentence** (no ``-`` prefix)::

        Can we just
        leave, please?

    Lines are joined into a single phrase, translated as one unit, then
    re-wrapped to the original number of lines.
    """
    lines = text.split("\n")
    if len(lines) <= 1:
        return translator.translate(text)

    # Dialogue: translate each speaker's line independently
    if _is_dialogue(lines):
        translated_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Remove the leading dash, translate, then re-add it
            speech = stripped.lstrip("-").strip()
            if speech:
                translated_lines.append("-" + translator.translate(speech))
            else:
                translated_lines.append(stripped)
        return "\n".join(translated_lines)

    # Wrapped sentence: join, translate as one, re-wrap
    joined = " ".join(line.strip() for line in lines)
    translated = translator.translate(joined)
    return _rewrap(translated, len(lines))


def _rewrap(text: str, num_lines: int) -> str:
    """Split *text* into *num_lines* lines of roughly equal word count."""
    if num_lines <= 1:
        return text
    words = text.split()
    if len(words) <= num_lines:
        return "\n".join(words)
    base, extra = divmod(len(words), num_lines)
    lines: list[str] = []
    idx = 0
    for i in range(num_lines):
        count = base + (1 if i < extra else 0)
        lines.append(" ".join(words[idx : idx + count]))
        idx += count
    return "\n".join(lines)
