"""Tests for mkv2srt.translator."""

from mkv2srt.models import Subtitle
from mkv2srt.translator import (
    _PreparedSub,
    _is_dialogue,
    _is_sdh,
    _prepare,
    _reassemble,
    _rewrap,
    _strip_tags,
)


def _sub(text: str) -> Subtitle:
    """Helper to create a Subtitle with only the text field set."""
    return Subtitle(index=1, start=0.0, end=1.0, text=text)


# ─────────────────────────────────────────────────────────────────────────────
# _rewrap
# ─────────────────────────────────────────────────────────────────────────────

class TestRewrap:
    def test_single_line_unchanged(self):
        assert _rewrap("Bonjour le monde", 1) == "Bonjour le monde"

    def test_two_lines_even(self):
        assert _rewrap("un deux trois quatre", 2) == "un deux\ntrois quatre"

    def test_two_lines_odd(self):
        assert _rewrap("un deux trois", 2) == "un deux\ntrois"

    def test_three_lines(self):
        assert _rewrap("a b c d e f", 3) == "a b\nc d\ne f"

    def test_fewer_words_than_lines(self):
        assert _rewrap("oui", 3) == "oui"

    def test_exact_words_as_lines(self):
        assert _rewrap("un deux", 2) == "un\ndeux"


# ─────────────────────────────────────────────────────────────────────────────
# _is_dialogue
# ─────────────────────────────────────────────────────────────────────────────

class TestIsDialogue:
    def test_dialogue_with_dashes(self):
        assert _is_dialogue(["-Yeah.", "-Come on, buddy."])

    def test_not_dialogue_without_dashes(self):
        assert not _is_dialogue(["Can we just", "leave, please?"])

    def test_not_dialogue_mixed(self):
        assert not _is_dialogue(["-Yeah.", "Come on, buddy."])

    def test_single_dash_line(self):
        assert _is_dialogue(["-Hello"])


# ─────────────────────────────────────────────────────────────────────────────
# HTML tags
# ─────────────────────────────────────────────────────────────────────────────

class TestStripTags:
    def test_no_tags(self):
        clean, prefix, suffix = _strip_tags("Hello world")
        assert clean == "Hello world"
        assert prefix == ""
        assert suffix == ""

    def test_italic_tags(self):
        clean, prefix, suffix = _strip_tags("<i>Hello world</i>")
        assert clean == "Hello world"
        assert prefix == "<i>"
        assert suffix == "</i>"

    def test_nested_tags(self):
        clean, prefix, suffix = _strip_tags("<b><i>Bold italic</i></b>")
        assert clean == "Bold italic"
        assert prefix == "<b><i>"
        assert suffix == "</i></b>"

    def test_font_tag(self):
        clean, prefix, suffix = _strip_tags('<font color="#ffffff">Text</font>')
        assert clean == "Text"
        assert prefix == '<font color="#ffffff">'
        assert suffix == "</font>"


# ─────────────────────────────────────────────────────────────────────────────
# SDH / CC annotations
# ─────────────────────────────────────────────────────────────────────────────

class TestIsSDH:
    def test_brackets(self):
        assert _is_sdh("[music playing]")

    def test_parentheses(self):
        assert _is_sdh("(laughing)")

    def test_music_notes(self):
        assert _is_sdh("♪ theme song ♪")

    def test_not_sdh_with_dialogue(self):
        assert not _is_sdh("Hello world")

    def test_not_sdh_mixed(self):
        assert not _is_sdh("[laughing] That's funny")

    def test_empty_string(self):
        assert not _is_sdh("")


# ─────────────────────────────────────────────────────────────────────────────
# _prepare / _reassemble (pre-process → translate → reconstruct)
# ─────────────────────────────────────────────────────────────────────────────

class TestPrepare:
    def test_plain_text(self):
        prep = _prepare(_sub("Hello world"))
        assert prep.unit_texts == ["Hello world"]
        assert not prep.is_dialogue
        assert prep.num_lines == 1

    def test_sdh_skipped(self):
        prep = _prepare(_sub("[music playing]"))
        assert prep.unit_texts == []

    def test_multiline_joined(self):
        prep = _prepare(_sub("Can we just\nleave, please?"))
        assert prep.unit_texts == ["Can we just leave, please?"]
        assert prep.num_lines == 2
        assert not prep.is_dialogue

    def test_dialogue_split(self):
        prep = _prepare(_sub("-Yeah.\n-Come on, buddy."))
        assert prep.unit_texts == ["Yeah.", "Come on, buddy."]
        assert prep.is_dialogue
        assert prep.num_lines == 2

    def test_html_tags_stripped(self):
        prep = _prepare(_sub("<i>Hello world</i>"))
        assert prep.unit_texts == ["Hello world"]
        assert prep.tag_prefix == "<i>"
        assert prep.tag_suffix == "</i>"

    def test_empty_after_tag_strip(self):
        prep = _prepare(_sub("<i></i>"))
        assert prep.unit_texts == []


class TestReassemble:
    def test_plain_text(self):
        prep = _PreparedSub(_sub("Hello"), ["Hello"], 1, False, "", "")
        assert _reassemble(prep, ["Bonjour"]) == "Bonjour"

    def test_sdh_kept(self):
        sub = _sub("[music playing]")
        prep = _PreparedSub(sub, [], 1, False, "", "")
        assert _reassemble(prep, []) == "[music playing]"

    def test_multiline_rewrapped(self):
        prep = _PreparedSub(
            _sub("Can we just\nleave, please?"),
            ["Can we just leave, please?"],
            2, False, "", "",
        )
        result = _reassemble(prep, ["Pouvons-nous juste partir"])
        assert len(result.split("\n")) == 2

    def test_dialogue_reassembled(self):
        prep = _PreparedSub(
            _sub("-Yeah.\n-Come on."),
            ["Yeah.", "Come on."],
            2, True, "", "",
        )
        assert _reassemble(prep, ["Ouais.", "Allez."]) == "-Ouais.\n-Allez."

    def test_html_tags_restored(self):
        prep = _PreparedSub(
            _sub("<i>Hello</i>"),
            ["Hello"],
            1, False, "<i>", "</i>",
        )
        assert _reassemble(prep, ["Bonjour"]) == "<i>Bonjour</i>"
