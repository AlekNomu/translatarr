"""
mkv2srt.sync_checker
~~~~~~~~~~~~~~~~~~~~
Timing consistency validation for subtitle tracks.

Checks performed
----------------
* Negative or zero display duration
* Overlap with the following subtitle (tolerance: 50 ms)
* Unusually long display duration (> 7 s)
* Empty text
* Last subtitle ending after the video duration
"""

from __future__ import annotations

from dataclasses import dataclass

from mkv2srt.models import SubtitleTrack, seconds_to_srt_time


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

#: Maximum accepted display duration in seconds before flagging as suspicious.
MAX_DISPLAY_DURATION: float = 7.0

#: Overlap tolerance in seconds (50 ms).
OVERLAP_TOLERANCE: float = 0.05


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
        # ── Negative or zero duration ────────────────────────────────────────
        if sub.end <= sub.start:
            issues.append(SyncIssue(
                sub.index,
                f"end ({sub.end_timestamp}) ≤ start ({sub.start_timestamp})",
            ))

        # ── Overlap with next subtitle ───────────────────────────────────────
        if i + 1 < len(subtitles):
            nxt = subtitles[i + 1]
            if sub.end > nxt.start + OVERLAP_TOLERANCE:
                issues.append(SyncIssue(
                    sub.index,
                    f"overlaps #{nxt.index} "
                    f"({sub.end_timestamp} > {nxt.start_timestamp})",
                ))

        # ── Unusually long display time ──────────────────────────────────────
        if sub.duration > MAX_DISPLAY_DURATION:
            issues.append(SyncIssue(
                sub.index,
                f"unusually long display duration ({sub.duration:.1f}s)",
            ))

        # ── Empty text ───────────────────────────────────────────────────────
        if not sub.text.strip():
            issues.append(SyncIssue(sub.index, "empty text"))

    # ── Last subtitle beyond video end ───────────────────────────────────────
    if video_duration is not None and subtitles:
        last = subtitles[-1]
        if last.end > video_duration + 1.0:
            issues.append(SyncIssue(
                last.index,
                f"ends at {last.end_timestamp}, beyond video duration "
                f"({seconds_to_srt_time(video_duration)})",
            ))

    return issues


def print_sync_report(issues: list[SyncIssue]) -> None:
    """Print a human-readable sync report to stdout."""
    print("\nSynchronisation check")
    print("─" * 40)
    if not issues:
        print("  No issues found.")
    else:
        for issue in issues:
            print(issue)
        print(f"\n  {len(issues)} issue(s) detected — review the entries above.")
    print()
