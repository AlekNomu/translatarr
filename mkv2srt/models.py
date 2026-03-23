"""
mkv2srt.models
~~~~~~~~~~~~~~
Core data structures shared across the package.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ─────────────────────────────────────────────────────────────────────────────
# Time helpers
# ─────────────────────────────────────────────────────────────────────────────

def srt_time_to_seconds(timestamp: str) -> float:
    """Convert an SRT timestamp (``HH:MM:SS,mmm``) to seconds (float)."""
    timestamp = timestamp.strip().replace(",", ".")
    h, m, rest = timestamp.split(":")
    return int(h) * 3600 + int(m) * 60 + float(rest)


def seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds (float) to an SRT timestamp (``HH:MM:SS,mmm``)."""
    seconds = max(0.0, seconds)
    ms = int(round((seconds % 1) * 1000))
    s  = int(seconds)
    h  = s // 3600
    m  = (s % 3600) // 60
    s  = s % 60
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ─────────────────────────────────────────────────────────────────────────────
# Subtitle
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Subtitle:
    """Represents a single subtitle entry."""

    index: int
    start: float          # seconds
    end:   float          # seconds
    text:  str

    # ── Derived properties ──────────────────────────────────────────────────

    @property
    def duration(self) -> float:
        """Display duration in seconds."""
        return max(0.0, self.end - self.start)

    @property
    def start_timestamp(self) -> str:
        return seconds_to_srt_time(self.start)

    @property
    def end_timestamp(self) -> str:
        return seconds_to_srt_time(self.end)

    # ── Serialisation ───────────────────────────────────────────────────────

    def to_srt_block(self) -> str:
        """Return the SRT-formatted block for this subtitle."""
        return (
            f"{self.index}\n"
            f"{self.start_timestamp} --> {self.end_timestamp}\n"
            f"{self.text}\n"
        )

    # ── Factory helpers ─────────────────────────────────────────────────────

    @classmethod
    def from_whisper_segment(cls, index: int, segment: dict) -> "Subtitle":
        return cls(
            index=index,
            start=float(segment["start"]),
            end=float(segment["end"]),
            text=segment["text"].strip(),
        )


# ─────────────────────────────────────────────────────────────────────────────
# SubtitleTrack
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SubtitleTrack:
    """An ordered collection of :class:`Subtitle` entries."""

    subtitles: list[Subtitle] = field(default_factory=list)

    # ── Constructors ────────────────────────────────────────────────────────

    @classmethod
    def from_whisper_segments(cls, segments: list[dict]) -> "SubtitleTrack":
        subs = [
            Subtitle.from_whisper_segment(i + 1, seg)
            for i, seg in enumerate(segments)
        ]
        return cls(subtitles=subs)

    @classmethod
    def from_srt_text(cls, text: str) -> "SubtitleTrack":
        """Parse raw SRT content into a :class:`SubtitleTrack`."""
        blocks = re.split(r"\n{2,}", text.strip())
        subs: list[Subtitle] = []

        for block in blocks:
            lines = block.strip().splitlines()
            if len(lines) < 3:
                continue
            try:
                idx = int(lines[0].strip())
            except ValueError:
                continue

            time_pattern = re.compile(
                r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})"
            )
            m = time_pattern.match(lines[1])
            if not m:
                continue

            subs.append(Subtitle(
                index=idx,
                start=srt_time_to_seconds(m.group(1)),
                end=srt_time_to_seconds(m.group(2)),
                text="\n".join(lines[2:]).strip(),
            ))

        return cls(subtitles=subs)

    # ── Serialisation ───────────────────────────────────────────────────────

    def to_srt(self) -> str:
        """Render the full SRT file content."""
        return "\n".join(sub.to_srt_block() for sub in self.subtitles)

    # ── Helpers ─────────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self.subtitles)

    def __iter__(self):
        return iter(self.subtitles)
