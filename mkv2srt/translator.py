"""
mkv2srt.translator
~~~~~~~~~~~~~~~~~~
Subtitle translation via Google Translate (deep-translator, no API key needed).

All subtitles are pre-processed (SDH skipped, tags stripped, multi-line joined,
dialogues split) into flat single-line "translation units", then batch-translated
in as few HTTP requests as possible, then reassembled with their original
formatting.
"""

from __future__ import annotations

import re
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol

from mkv2srt.models import Subtitle, SubtitleTrack

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

_SEP = " |||SEP||| "
_DEFAULT_BATCH_SIZE = 40
_FALLBACK_DELAY = 0.1

# Matches any HTML/SRT tag (<i>, </b>, <font color="…">) — used to strip formatting before translation
_TAG_PATTERN = re.compile(r"</?[a-zA-Z][^>]*>")
# Same but anchored at end-of-string — lets _strip_tags peel trailing tags without touching mid-text ones
_TRAILING_TAG_PATTERN = re.compile(r"</?[a-zA-Z][^>]*>\s*$")
# Matches SDH/CC annotations ([music], (laughing), ♪…♪) — these are skipped, never sent to translation
_SDH_PATTERN = re.compile(r"\[.*?\]|\(.*?\)|♪.*?♪", re.DOTALL)


# ─────────────────────────────────────────────────────────────────────────────
# Translator protocol
# ─────────────────────────────────────────────────────────────────────────────

class _Translator(Protocol):
    def translate(self, text: str) -> str: ...


# ─────────────────────────────────────────────────────────────────────────────
# Pre-processing: subtitle → translation units
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class _PreparedSub:
    """A subtitle broken down into translatable units with reconstruction info."""
    original: Subtitle
    unit_texts: list[str]       # texts to send to Google Translate (empty = skip)
    num_lines: int              # original line count (for re-wrapping)
    is_dialogue: bool           # True → reassemble with "-" prefixes
    tag_prefix: str             # HTML tags to restore before text
    tag_suffix: str             # HTML tags to restore after text


def _prepare(sub: Subtitle) -> _PreparedSub:
    """Break a subtitle into flat, single-line translation units."""
    text = sub.text

    if _is_sdh(text):
        return _PreparedSub(sub, [], 1, False, "", "")

    clean, prefix, suffix = _strip_tags(text)
    if not clean.strip():
        return _PreparedSub(sub, [], 1, False, "", "")

    lines = clean.split("\n")

    if len(lines) > 1 and _is_dialogue(lines):
        speeches = [
            line.strip().lstrip("-").strip()
            for line in lines
            if line.strip().lstrip("-").strip()
        ]
        return _PreparedSub(sub, speeches, len(lines), True, prefix, suffix)

    joined = " ".join(line.strip() for line in lines)
    return _PreparedSub(sub, [joined], len(lines), False, prefix, suffix)


def _reassemble(prep: _PreparedSub, translated: list[str]) -> str:
    """Reconstruct the final subtitle text from translated units."""
    if not prep.unit_texts:
        return prep.original.text

    if prep.is_dialogue:
        text = "\n".join("-" + t for t in translated)
    elif prep.num_lines > 1:
        text = _rewrap(translated[0], prep.num_lines)
    else:
        text = translated[0]

    return prep.tag_prefix + text + prep.tag_suffix


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def translate_track(
    track: SubtitleTrack,
    source_lang: str = "auto",
    target_lang: str = "fr",
    batch_size: int = _DEFAULT_BATCH_SIZE,
    on_progress: Callable[[int, int], None] | None = None,
) -> SubtitleTrack:
    """Return a new :class:`SubtitleTrack` with every text translated.

    Timings are preserved exactly — only the ``text`` field changes.
    *on_progress(done, total)* is called after each batch if provided.
    """
    _require_deep_translator()
    from deep_translator import GoogleTranslator  # type: ignore

    translator = GoogleTranslator(source=source_lang, target=target_lang)
    subtitles = list(track)
    total = len(subtitles)

    # ── Phase 1: pre-process ───────────────────────────────────────────
    prepared = [_prepare(sub) for sub in subtitles]

    # Flat index mapping: each unit → (prep_index, unit_index_within_prep)
    all_units: list[str] = []
    unit_map: list[tuple[int, int]] = []
    for prep_idx, prep in enumerate(prepared):
        for unit_idx, text in enumerate(prep.unit_texts):
            all_units.append(text)
            unit_map.append((prep_idx, unit_idx))

    # ── Phase 2: batch translate ──────────────────────────────────────────
    translated_units = _batch_translate_all(
        translator, all_units, batch_size, total, on_progress,
    )

    # ── Phase 3: reassemble ──────────────────────────────────────────────
    results_per_prep: list[list[str]] = [[] for _ in prepared]
    for (prep_idx, _), translated_text in zip(unit_map, translated_units):
        results_per_prep[prep_idx].append(translated_text)

    translated_subs: list[Subtitle] = []
    for prep, result_texts in zip(prepared, results_per_prep):
        new_text = _reassemble(prep, result_texts)
        translated_subs.append(replace(prep.original, text=new_text.strip()))

    return SubtitleTrack(subtitles=translated_subs)


# ─────────────────────────────────────────────────────────────────────────────
# Batch translation engine
# ─────────────────────────────────────────────────────────────────────────────

def _batch_translate_all(
    translator: _Translator,
    units: list[str],
    batch_size: int,
    subtitle_count: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[str]:
    """Translate all units via batched requests, with fallback to one-by-one."""
    if not units:
        return []

    results: list[str] = []
    for start in range(0, len(units), batch_size):
        batch = units[start : start + batch_size]
        results.extend(_translate_batch(translator, batch))

        if on_progress:
            # Progress based on subtitle count (not unit count) for user clarity
            progress = min(len(results) * subtitle_count // max(len(units), 1), subtitle_count)
            on_progress(progress, subtitle_count)

    return results


def _translate_batch(translator: _Translator, batch: list[str]) -> list[str]:
    """Translate a batch of pre-processed texts in one request."""
    combined = _SEP.join(batch)
    try:
        result = translator.translate(combined)
        parts = result.split("|||SEP|||")
        if len(parts) == len(batch):
            return [part.strip() for part in parts]
    except Exception:
        pass

    return _translate_one_by_one(translator, batch)


def _translate_one_by_one(translator: _Translator, batch: list[str]) -> list[str]:
    """Fallback: translate each text individually."""
    parts: list[str] = []
    for text in batch:
        try:
            result = translator.translate(text)
            parts.append(result if result is not None else text)
        except Exception:
            parts.append(text)
        time.sleep(_FALLBACK_DELAY)
    return parts


# ─────────────────────────────────────────────────────────────────────────────
# Text pre-processing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_sdh(text: str) -> bool:
    """Return True if *text* is purely an SDH/CC annotation."""
    stripped = _SDH_PATTERN.sub("", text).strip()
    return len(stripped) == 0 and len(text.strip()) > 0


def _is_dialogue(lines: list[str]) -> bool:
    """Return True if every non-empty line starts with ``-`` (dialogue)."""
    return all(line.strip().startswith("-") for line in lines if line.strip())


def _strip_tags(text: str) -> tuple[str, str, str]:
    """Strip leading/trailing HTML tags from *text*.

    Returns ``(clean_text, prefix_tags, suffix_tags)``.
    """
    prefix = ""
    tmp = text
    while (tag_match := _TAG_PATTERN.match(tmp)):
        prefix += tag_match.group()
        tmp = tmp[tag_match.end():]

    suffix = ""
    while (tag_match := _TRAILING_TAG_PATTERN.search(tmp)):
        suffix = tag_match.group().strip() + suffix
        tmp = tmp[:tag_match.start()]

    clean = _TAG_PATTERN.sub("", tmp)
    return clean, prefix, suffix


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


# ─────────────────────────────────────────────────────────────────────────────
# Dependency check
# ─────────────────────────────────────────────────────────────────────────────

def _require_deep_translator() -> None:
    try:
        import deep_translator  # noqa: F401
    except ImportError:
        sys.exit(
            "'deep-translator' is not installed.\n"
            "    Run: pip install deep-translator"
        )
