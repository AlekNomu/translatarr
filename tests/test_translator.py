"""Tests for mkv2srt.translator (multi-line handling)."""

from mkv2srt.translator import (
    _is_dialogue,
    _is_sdh,
    _restore_tags,
    _rewrap,
    _strip_tags,
    _translate_multiline,
    _translate_single,
)


class TestRewrap:
    def test_single_line_unchanged(self):
        assert _rewrap("Bonjour le monde", 1) == "Bonjour le monde"

    def test_two_lines_even(self):
        result = _rewrap("un deux trois quatre", 2)
        assert result == "un deux\ntrois quatre"

    def test_two_lines_odd(self):
        result = _rewrap("un deux trois", 2)
        # 3 words / 2 lines → 2 + 1
        assert result == "un deux\ntrois"

    def test_three_lines(self):
        result = _rewrap("a b c d e f", 3)
        assert result == "a b\nc d\ne f"

    def test_fewer_words_than_lines(self):
        result = _rewrap("oui", 3)
        assert result == "oui"

    def test_exact_words_as_lines(self):
        result = _rewrap("un deux", 2)
        assert result == "un\ndeux"


class TestTranslateMultiline:
    def test_single_line_calls_translate(self):
        class FakeTranslator:
            def translate(self, text):
                return "Bonjour"

        result = _translate_multiline(FakeTranslator(), "Hello")
        assert result == "Bonjour"

    def test_multiline_joins_before_translate(self):
        """Multi-line text should be joined, translated as one, then re-wrapped."""
        received = []

        class FakeTranslator:
            def translate(self, text):
                received.append(text)
                return "Pouvons-nous juste partir s'il vous plait"

        result = _translate_multiline(
            FakeTranslator(), "Can we just\nleave, please?"
        )
        # Should have sent joined text
        assert received == ["Can we just leave, please?"]
        # Result should be re-wrapped to 2 lines
        assert "\n" in result
        lines = result.split("\n")
        assert len(lines) == 2


class TestIsDialogue:
    def test_dialogue_with_dashes(self):
        assert _is_dialogue(["-Yeah.", "-Come on, buddy."])

    def test_not_dialogue_without_dashes(self):
        assert not _is_dialogue(["Can we just", "leave, please?"])

    def test_not_dialogue_mixed(self):
        assert not _is_dialogue(["-Yeah.", "Come on, buddy."])

    def test_single_dash_line(self):
        assert _is_dialogue(["-Hello"])


class TestTranslateMultilineDialogue:
    def test_dialogue_translated_independently(self):
        """Each speaker line should be translated separately."""
        received = []

        class FakeTranslator:
            def translate(self, text):
                received.append(text)
                translations = {"Yeah.": "Ouais.", "Come on, buddy.": "Allez, mon pote."}
                return translations.get(text, text)

        result = _translate_multiline(
            FakeTranslator(), "-Yeah.\n-Come on, buddy."
        )
        # Each line translated independently (without the dash)
        assert received == ["Yeah.", "Come on, buddy."]
        # Result preserves dialogue structure
        assert result == "-Ouais.\n-Allez, mon pote."

    def test_wrapped_sentence_not_treated_as_dialogue(self):
        """Lines without dashes should be joined and translated as one."""
        received = []

        class FakeTranslator:
            def translate(self, text):
                received.append(text)
                return "Non, mais ils sont encore là. Va--"

        result = _translate_multiline(
            FakeTranslator(), "No, but they're--\nthey're still there. Go--"
        )
        assert received == ["No, but they're-- they're still there. Go--"]
        assert len(result.split("\n")) == 2


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


class TestRestoreTags:
    def test_roundtrip(self):
        original = "<i>Hello world</i>"
        clean, prefix, suffix = _strip_tags(original)
        assert _restore_tags(clean, prefix, suffix) == original

    def test_no_tags(self):
        assert _restore_tags("Hello", "", "") == "Hello"

    def test_translation_changes_length(self):
        """Tags should wrap correctly even when translation length differs."""
        _, prefix, suffix = _strip_tags("<i>Hi</i>")
        result = _restore_tags("Bonjour", prefix, suffix)
        assert result == "<i>Bonjour</i>"


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
        # Has both annotation and real text
        assert not _is_sdh("[laughing] That's funny")

    def test_empty_string(self):
        assert not _is_sdh("")

    def test_whitespace_only(self):
        assert not _is_sdh("   ")


# ─────────────────────────────────────────────────────────────────────────────
# _translate_single (integration of all protections)
# ─────────────────────────────────────────────────────────────────────────────

class TestTranslateSingle:
    def test_sdh_kept_as_is(self):
        """SDH annotations should not be sent to the translator."""
        class FakeTranslator:
            def translate(self, text):
                raise AssertionError("Should not be called")

        assert _translate_single(FakeTranslator(), "[music playing]") == "[music playing]"
        assert _translate_single(FakeTranslator(), "♪ la la la ♪") == "♪ la la la ♪"

    def test_html_tags_preserved(self):
        """HTML tags should be stripped before translation and restored after."""
        class FakeTranslator:
            def translate(self, text):
                assert "<" not in text  # no tags sent to translator
                return "Bonjour le monde"

        result = _translate_single(FakeTranslator(), "<i>Hello world</i>")
        assert result == "<i>Bonjour le monde</i>"

    def test_plain_text(self):
        class FakeTranslator:
            def translate(self, text):
                return "Bonjour"

        assert _translate_single(FakeTranslator(), "Hello") == "Bonjour"
