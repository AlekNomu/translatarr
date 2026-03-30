"""Tests for translatarr.sync_checker."""

from translatarr.models import Subtitle, SubtitleTrack
from translatarr.sync_checker import check_sync


def _make_track(*entries: tuple) -> SubtitleTrack:
    """Helper: build a SubtitleTrack from (start, end, text) tuples."""
    subs = [
        Subtitle(index=i + 1, start=s, end=e, text=t)
        for i, (s, e, t) in enumerate(entries)
    ]
    return SubtitleTrack(subtitles=subs)


class TestCheckSync:
    def test_no_issues(self):
        track = _make_track((0.0, 2.0, "Hello"), (3.0, 5.0, "World"))
        assert check_sync(track) == []

    def test_negative_duration(self):
        track = _make_track((5.0, 3.0, "Oops"))
        issues = check_sync(track)
        assert any("≤" in i.message or "<=" in i.message for i in issues)

    def test_overlap(self):
        track = _make_track((0.0, 4.0, "First"), (3.0, 6.0, "Second"))
        issues = check_sync(track)
        assert any("overlap" in i.message for i in issues)

    def test_long_duration(self):
        track = _make_track((0.0, 20.0, "Very long subtitle"))
        issues = check_sync(track)
        assert any("long" in i.message for i in issues)

    def test_normal_duration_not_flagged(self):
        track = _make_track((0.0, 10.0, "Normal-length subtitle"))
        issues = check_sync(track)
        assert not any("long" in i.message for i in issues)

    def test_empty_text(self):
        track = _make_track((0.0, 2.0, "   "))
        issues = check_sync(track)
        assert any("empty" in i.message for i in issues)

    def test_beyond_video_duration(self):
        track = _make_track((0.0, 2.0, "Hello"), (120.0, 125.0, "End"))
        issues = check_sync(track, video_duration=100.0)
        assert any("beyond" in i.message for i in issues)

    def test_within_video_duration(self):
        track = _make_track((0.0, 2.0, "Hello"), (5.0, 7.0, "End"))
        issues = check_sync(track, video_duration=100.0)
        assert issues == []
