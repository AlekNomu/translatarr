"""Tests for translatarr.pipeline — SRT lookup helpers and engine selection."""

from __future__ import annotations

import pytest

from translatarr import pipeline as pipeline_module
from translatarr.models import Subtitle, SubtitleTrack
from translatarr.pipeline import _resolve_track, find_srt_by_lang, target_srt_tags


# ─────────────────────────────────────────────────────────────────────────────
# find_srt_by_lang
# ─────────────────────────────────────────────────────────────────────────────

class TestFindSrtByLang:
    def test_finds_plain_lang_tag(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        (tmp_path / "Movie.2016.fr.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result == tmp_path / "Movie.2016.fr.srt"

    def test_finds_iso3_alias(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        (tmp_path / "Movie.2016.fre.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result == tmp_path / "Movie.2016.fre.srt"

    def test_finds_hi_variant(self, tmp_path):
        # Reproduces bug: .fr.hi.srt was not detected as a French subtitle
        mkv = tmp_path / "A.Silent.Voice.2016.1080p.BluRay.x264-HAiKU.mkv"
        mkv.touch()
        (tmp_path / "A.Silent.Voice.2016.1080p.BluRay.x264-HAiKU.fr.hi.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result is not None

    def test_finds_sdh_variant(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        (tmp_path / "Movie.2016.fr.sdh.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result is not None

    def test_plain_takes_priority_over_hi(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        plain = tmp_path / "Movie.2016.fr.srt"
        plain.touch()
        (tmp_path / "Movie.2016.fr.hi.srt").touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result == plain

    def test_returns_none_when_absent(self, tmp_path):
        mkv = tmp_path / "Movie.2016.mkv"
        mkv.touch()
        result = find_srt_by_lang(mkv, target_srt_tags("fr"))
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Translation engine selection
# ─────────────────────────────────────────────────────────────────────────────

SRT_ONE_LINE = "1\n00:00:01,000 --> 00:00:02,000\nHello\n"


@pytest.fixture
def spy_translate(monkeypatch):
    """Capture the provider arguments _resolve_track hands to the translator."""
    calls: list[dict] = []

    def fake_translate_track(track, **kwargs):
        calls.append(kwargs)
        return track

    monkeypatch.setattr(pipeline_module, "translate_track", fake_translate_track)
    return calls


class TestProviderSelection:
    """The engine chosen in Settings has to survive the trip to the translator.

    Nothing else asserts this wiring, and a provider silently dropped here would
    look exactly like a working translation, just always on the default engine.
    """

    def test_translating_a_source_srt_uses_the_selected_engine(self, tmp_path, spy_translate):
        mkv = tmp_path / "Movie.mkv"
        english = tmp_path / "Movie.en.srt"
        english.write_text(SRT_ONE_LINE, encoding="utf-8")

        _, action = _resolve_track(
            mkv, english, None,
            provider="deepl", provider_config={"deepl_api_key": "k"},
        )

        assert action == "translated"
        assert spy_translate[0]["provider"] == "deepl"
        assert spy_translate[0]["provider_config"] == {"deepl_api_key": "k"}

    def test_retranslating_a_mismatched_target_uses_the_selected_engine(
        self, tmp_path, spy_translate,
    ):
        mkv = tmp_path / "Movie.mkv"
        english = tmp_path / "Movie.en.srt"
        english.write_text(SRT_ONE_LINE + "\n2\n00:00:03,000 --> 00:00:04,000\nBye\n", encoding="utf-8")
        target = tmp_path / "Movie.fr.srt"
        target.write_text(SRT_ONE_LINE, encoding="utf-8")

        _, action = _resolve_track(
            mkv, english, target, provider="mymemory", provider_config={},
        )

        assert action == "translated"
        assert spy_translate[0]["provider"] == "mymemory"

    def test_unknown_provider_is_passed_through_for_the_translator_to_resolve(
        self, tmp_path, spy_translate,
    ):
        # Normalizing here too would mean resolving (and warning) twice per file
        mkv = tmp_path / "Movie.mkv"
        english = tmp_path / "Movie.en.srt"
        english.write_text(SRT_ONE_LINE, encoding="utf-8")

        _resolve_track(mkv, english, None, provider="nonsense")

        assert spy_translate[0]["provider"] == "nonsense"

    def test_skipping_an_aligned_pair_never_touches_the_translator(
        self, tmp_path, spy_translate,
    ):
        mkv = tmp_path / "Movie.mkv"
        for name in ("Movie.en.srt", "Movie.fr.srt"):
            (tmp_path / name).write_text(SRT_ONE_LINE, encoding="utf-8")

        track, action = _resolve_track(
            mkv, tmp_path / "Movie.en.srt", tmp_path / "Movie.fr.srt", provider="deepl",
        )

        assert (track, action) == (None, "skipped")
        assert spy_translate == []

    def test_resyncing_never_touches_the_translator(self, tmp_path, spy_translate):
        mkv = tmp_path / "Movie.mkv"
        english = tmp_path / "Movie.en.srt"
        english.write_text(SRT_ONE_LINE, encoding="utf-8")
        target = tmp_path / "Movie.fr.srt"
        target.write_text(
            "1\n00:00:09,000 --> 00:00:10,000\nBonjour\n", encoding="utf-8",
        )

        track, action = _resolve_track(mkv, english, target, provider="deepl")

        assert action == "resynced"
        assert spy_translate == []
        assert isinstance(track, SubtitleTrack)
        assert [s.start for s in track] == [1.0]

    def test_transcription_prefers_whispers_detected_language_over_auto(
        self, tmp_path, monkeypatch, spy_translate,
    ):
        """Engines without auto-detection would otherwise be told "auto" and guess English."""
        mkv = tmp_path / "Movie.mkv"
        track = SubtitleTrack(subtitles=[Subtitle(index=1, start=0.0, end=1.0, text="Hola")])
        monkeypatch.setattr(pipeline_module, "extract_audio", lambda *a, **k: None)
        monkeypatch.setattr(pipeline_module, "transcribe", lambda *a, **k: (track, "es"))

        _, action = _resolve_track(mkv, None, None, provider="deepl")

        assert action == "transcribed"
        assert spy_translate[0]["source_lang"] == "es"
        assert spy_translate[0]["provider"] == "deepl"

    def test_explicit_source_language_overrides_whispers_guess(
        self, tmp_path, monkeypatch, spy_translate,
    ):
        mkv = tmp_path / "Movie.mkv"
        track = SubtitleTrack(subtitles=[Subtitle(index=1, start=0.0, end=1.0, text="Hola")])
        monkeypatch.setattr(pipeline_module, "extract_audio", lambda *a, **k: None)
        monkeypatch.setattr(pipeline_module, "transcribe", lambda *a, **k: (track, "es"))

        _resolve_track(mkv, None, None, provider="google", language="de")

        assert spy_translate[0]["source_lang"] == "de"
