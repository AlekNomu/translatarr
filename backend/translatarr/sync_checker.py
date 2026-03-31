"""
translatarr.sync_checker
~~~~~~~~~~~~~~~~~~~~
Timing consistency validation for subtitle tracks.

Checks performed
----------------
* Negative or zero display duration
* Overlap with the following subtitle (tolerance: 50 ms)
* Unusually long display duration (> 15 s)
* Empty text
* Last subtitle ending after the video duration
"""

from __future__ import annotations
from dataclasses import dataclass
from translatarr.models import SubtitleTrack, seconds_to_srt_time


# ─────────────────────────────────────────────────────────────────────────────
# Issue
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SyncIssue:
    subtitle_index: int
    message: str

    def __str__(self) -> str:
        return f"  [!] #{self.subtitle_index}: {self.message}"


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────
MAX_DISPLAY_DURATION: float = 15.0
OVERLAP_TOLERANCE: float = 0.05
END_OF_VIDEO_TOLERANCE: float = 1.0


def check_sync(
    track:          SubtitleTrack,
    video_duration: float | None = None,
) -> list[SyncIssue]:
    """
    Validate the timing of every subtitle in *track*.

    :param track:          Subtitle track to inspect.
    :param video_duration: Optional video duration in seconds used to detect
                           subtitles that extend beyond the end of the video.
    :returns: A list of :class:`SyncIssue` objects (empty → no issues found).
    """
    issues: list[SyncIssue] = []
    subtitles = list(track)

    for i, sub in enumerate(subtitles):
        if sub.end <= sub.start:
            issues.append(SyncIssue(
                sub.index,
                f"end ({sub.end_timestamp}) ≤ start ({sub.start_timestamp})",
            ))

        if i + 1 < len(subtitles):
            nxt = subtitles[i + 1]
            if sub.end > nxt.start + OVERLAP_TOLERANCE:
                issues.append(SyncIssue(
                    sub.index,
                    f"overlaps #{nxt.index} "
                    f"({sub.end_timestamp} > {nxt.start_timestamp})",
                ))

        if sub.duration > MAX_DISPLAY_DURATION:
            issues.append(SyncIssue(
                sub.index,
                f"unusually long display duration ({sub.duration:.1f}s)",
            ))

        if not sub.text.strip():
            issues.append(SyncIssue(sub.index, "empty text"))
    if video_duration is not None and subtitles:
        last = subtitles[-1]
        if last.end > video_duration + END_OF_VIDEO_TOLERANCE:
            issues.append(SyncIssue(
                last.index,
                f"ends at {last.end_timestamp}, beyond video duration "
                f"({seconds_to_srt_time(video_duration)})",
            ))

    return issues