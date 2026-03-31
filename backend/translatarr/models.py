"""
translatarr.models
~~~~~~~~~~~~~~
Core data structures shared across the package.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SECONDS_PER_HOUR = 3600
SECONDS_PER_MINUTE = 60
MS_PER_SECOND = 1000
MIN_SRT_BLOCK_LINES = 3

# Accepts both comma and dot as ms separator (SRT uses comma, some tools use dot)
_SRT_TIME_PATTERN = re.compile(
    r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})"
)


def srt_time_to_seconds(timestamp: str) -> float:
    """Convert an SRT timestamp (``HH:MM:SS,mmm``) to seconds (float)."""
    timestamp = timestamp.strip().replace(",", ".")
    h, m, rest = timestamp.split(":")
    return int(h) * SECONDS_PER_HOUR + int(m) * SECONDS_PER_MINUTE + float(rest)


def seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds (float) to an SRT timestamp (``HH:MM:SS,mmm``)."""
    seconds = max(0.0, seconds)
    ms = int(round((seconds % 1) * MS_PER_SECOND))
    s  = int(seconds)
    h  = s // SECONDS_PER_HOUR
    m  = (s % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE
    s  = s % SECONDS_PER_MINUTE
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


@dataclass
class Subtitle:
    """Represents a single subtitle entry."""

    index: int
    start: float
    end:   float
    text:  str

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

    def to_srt_block(self) -> str:
        """Return the SRT-formatted block for this subtitle."""
        return (
            f"{self.index}\n"
            f"{self.start_timestamp} --> {self.end_timestamp}\n"
            f"{self.text}\n"
        )

    @classmethod
    def from_whisper_segment(cls, index: int, segment: dict) -> "Subtitle":
        return cls(
            index=index,
            start=float(segment["start"]),
            end=float(segment["end"]),
            text=segment["text"].strip(),
        )


@dataclass
class SubtitleTrack:
    """An ordered collection of :class:`Subtitle` entries."""

    subtitles: list[Subtitle] = field(default_factory=list)

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
            if len(lines) < MIN_SRT_BLOCK_LINES:
                continue
            try:
                idx = int(lines[0].strip())
            except ValueError:
                continue

            time_match = _SRT_TIME_PATTERN.match(lines[1])
            
            if not time_match:
                continue

            subs.append(Subtitle(
                index=idx,
                start=srt_time_to_seconds(time_match.group(1)),
                end=srt_time_to_seconds(time_match.group(2)),
                text="\n".join(lines[2:]).strip(),
            ))

        return cls(subtitles=subs)

    def to_srt(self) -> str:
        """Render the full SRT file content."""
        return "\n".join(sub.to_srt_block() for sub in self.subtitles)

    def has_same_timestamps(self, other: "SubtitleTrack", tolerance: float = 0.05) -> bool:
        """Check if two tracks have identical timestamps (within tolerance)."""
        if len(self) != len(other):
            return False
        return all(
            abs(a.start - b.start) <= tolerance and abs(a.end - b.end) <= tolerance
            for a, b in zip(self.subtitles, other.subtitles)
        )

    def resync_from(self, reference: "SubtitleTrack") -> "SubtitleTrack":
        """Apply timestamps from *reference* onto this track's text.

        Only works when both tracks have the same number of entries.
        Returns a new SubtitleTrack with reference timestamps and this track's text.

        :raises ValueError: If the two tracks have different lengths.
        """
        if len(self) != len(reference):
            raise ValueError(
                f"Cannot resync: track has {len(self)} entries "
                f"but reference has {len(reference)}"
            )
        resynced = [
            Subtitle(
                index=ref.index,
                start=ref.start,
                end=ref.end,
                text=sub.text,
            )
            for sub, ref in zip(self.subtitles, reference.subtitles)
        ]
        return SubtitleTrack(subtitles=resynced)

    def __len__(self) -> int:
        return len(self.subtitles)

    def __iter__(self):
        return iter(self.subtitles)
