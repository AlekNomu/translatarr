"""Tests for mkv2srt.models."""

import pytest
from mkv2srt.models import (
    Subtitle,
    SubtitleTrack,
    seconds_to_srt_time,
    srt_time_to_seconds,
)


# ─────────────────────────────────────────────────────────────────────────────
# Time conversion helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestTimeConversions:
    def test_seconds_to_srt_zero(self):
        assert seconds_to_srt_time(0.0) == "00:00:00,000"

    def test_seconds_to_srt_typical(self):
        assert seconds_to_srt_time(3661.5) == "01:01:01,500"

    def test_seconds_to_srt_negative_clamped(self):
        assert seconds_to_srt_time(-1.0) == "00:00:00,000"

    def test_srt_to_seconds_comma(self):
        assert srt_time_to_seconds("00:01:30,000") == pytest.approx(90.0)

    def test_srt_to_seconds_dot(self):
        assert srt_time_to_seconds("00:01:30.500") == pytest.approx(90.5)

    def test_roundtrip(self):
        original = 12345.678
        assert srt_time_to_seconds(seconds_to_srt_time(original)) == pytest.approx(
            original, abs=0.001
        )


# ─────────────────────────────────────────────────────────────────────────────
# Subtitle
# ─────────────────────────────────────────────────────────────────────────────

class TestSubtitle:
    def test_duration(self):
        sub = Subtitle(index=1, start=1.0, end=3.5, text="Hello")
        assert sub.duration == pytest.approx(2.5)

    def test_duration_negative_clamped(self):
        sub = Subtitle(index=1, start=5.0, end=3.0, text="Oops")
        assert sub.duration == 0.0

    def test_to_srt_block(self):
        sub = Subtitle(index=2, start=0.0, end=2.0, text="Hi there")
        block = sub.to_srt_block()
        assert "2\n" in block
        assert "00:00:00,000 --> 00:00:02,000" in block
        assert "Hi there" in block

    def test_from_whisper_segment(self):
        segment = {"start": 1.0, "end": 4.0, "text": "  Hello world  "}
        sub = Subtitle.from_whisper_segment(index=1, segment=segment)
        assert sub.text == "Hello world"
        assert sub.start == 1.0
        assert sub.end == 4.0


# ─────────────────────────────────────────────────────────────────────────────
# SubtitleTrack
# ─────────────────────────────────────────────────────────────────────────────

SRT_SAMPLE = """\
1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,500 --> 00:00:06,000
Goodbye world

"""


class TestSubtitleTrack:
    def test_parse_srt(self):
        track = SubtitleTrack.from_srt_text(SRT_SAMPLE)
        assert len(track) == 2
        assert track.subtitles[0].text == "Hello world"
        assert track.subtitles[1].start == pytest.approx(4.5)

    def test_to_srt_roundtrip(self):
        track  = SubtitleTrack.from_srt_text(SRT_SAMPLE)
        output = track.to_srt()
        track2 = SubtitleTrack.from_srt_text(output)
        assert len(track2) == len(track)
        for a, b in zip(track, track2):
            assert a.text  == b.text
            assert a.start == pytest.approx(b.start)
            assert a.end   == pytest.approx(b.end)

    def test_from_whisper_segments(self):
        segments = [
            {"start": 0.0, "end": 2.0, "text": "Bonjour"},
            {"start": 3.0, "end": 5.0, "text": "Au revoir"},
        ]
        track = SubtitleTrack.from_whisper_segments(segments)
        assert len(track) == 2
        assert track.subtitles[0].index == 1
        assert track.subtitles[1].index == 2

    def test_iter(self):
        track = SubtitleTrack.from_srt_text(SRT_SAMPLE)
        texts = [sub.text for sub in track]
        assert texts == ["Hello world", "Goodbye world"]
