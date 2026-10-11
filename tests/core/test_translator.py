"""Tests for translatarr.translator."""

import pytest

from translatarr import translator as translator_module
from translatarr.models import Subtitle
from translatarr.translator import (
    DEFAULT_PROVIDER,
    PROVIDERS,
    ProviderSpec,
    TranslationUnavailable,
    _is_dialogue,
    _is_rate_limit,
    _is_sdh,
    _make_batches,
    _prepare,
    _PreparedSub,
    _RateLimiter,
    _reassemble,
    _resolve_lang,
    _rewrap,
    _split_and_translate,
    _strip_tags,
    _translate_batch,
    build_translator,
    describe_providers,
    resolve_provider,
)

RATE = 4.0

# Verbatim message deep-translator raises when Google throttles us
RATE_LIMIT_MESSAGE = (
    "Server Error: You made too many requests to the server."
    "According to google, you are allowed to make 5 requests per second"
    "and up to 200k requests per day. You can wait and try again later or"
    "you can try the translate_batch function"
)


def _sub(text: str) -> Subtitle:
    """Helper to create a Subtitle with only the text field set."""
    return Subtitle(index=1, start=0.0, end=1.0, text=text)


class _FakeClock:
    """Virtual clock so rate-limit tests measure spacing without real sleeping."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = _FakeClock()
    monkeypatch.setattr(translator_module, "time", fake)
    return fake


class _FakeTranslator:
    """Records every request and replays a scripted sequence of outcomes.

    *script* maps a 1-based call number to either an exception to raise or a
    canned reply; unscripted calls echo the request prefixed with "fr:".
    """

    def __init__(self, script: dict[int, object] | None = None) -> None:
        self.script = script or {}
        self.requests: list[str] = []

    def translate(self, text: str) -> str:
        self.requests.append(text)
        call = len(self.requests)
        if call in self.script:
            outcome = self.script[call]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome  # type: ignore[return-value]
        # Uses the real separator: hardcoding it here would let a change to _SEP
        # push every batch down the "mangled separator" path while tests stayed green
        units = text.split(translator_module._SEP)
        return translator_module._SEP.join(f"fr:{unit}" for unit in units)


def _spec(**overrides) -> ProviderSpec:
    """A throwaway provider spec — each one owns a fresh, isolated rate limiter."""
    defaults = dict(
        key="test",
        label="Test Engine",
        description="",
        factory=lambda source, target, config: _FakeTranslator(),
        languages={},
        requests_per_second=RATE,
        max_chars=4500,
        batch_size=40,
    )
    return ProviderSpec(**{**defaults, **overrides})


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


# ─────────────────────────────────────────────────────────────────────────────
# Rate limiting
# ─────────────────────────────────────────────────────────────────────────────

class TestIsRateLimit:
    def test_google_throttle_message(self):
        assert _is_rate_limit(Exception(RATE_LIMIT_MESSAGE))

    def test_http_429(self):
        assert _is_rate_limit(Exception("HTTP Error 429: Too Many Requests"))

    def test_unrelated_error(self):
        assert not _is_rate_limit(Exception("Connection reset by peer"))


class TestRateLimiter:
    def test_spaces_requests_below_the_limit(self, clock):
        limiter = _RateLimiter(RATE)
        for _ in range(10):
            limiter.acquire()

        interval = 1.0 / RATE
        assert all(sleep >= interval - 1e-9 for sleep in clock.sleeps[1:])
        # 10 requests may not be issued in less than 9 intervals
        assert clock.now - 1000.0 >= 9 * interval

    def test_penalize_delays_every_caller(self, clock):
        limiter = _RateLimiter(RATE)
        limiter.penalize(30.0)
        limiter.acquire()
        assert clock.sleeps == [30.0]

    def test_unlimited_rate_never_sleeps(self, clock):
        limiter = _RateLimiter(0)
        for _ in range(5):
            limiter.acquire()
        assert clock.sleeps == []

    def test_every_provider_has_its_own_limiter(self):
        limiters = {id(spec.limiter) for spec in PROVIDERS.values()}
        assert len(limiters) == len(PROVIDERS)


class TestTranslateBatchThrottling:
    def test_throttled_batch_is_retried_not_dropped(self, clock):
        fake = _FakeTranslator({1: Exception(RATE_LIMIT_MESSAGE)})

        result = _translate_batch(fake, ["Hello", "World"], _spec())

        assert result == ["fr:Hello", "fr:World"]
        assert len(fake.requests) == 2
        # The retry waited out the backoff instead of firing immediately
        assert max(clock.sleeps) >= 1.0

    def test_backoff_grows_between_retries(self, clock):
        throttle = Exception(RATE_LIMIT_MESSAGE)
        fake = _FakeTranslator({1: throttle, 2: throttle, 3: throttle})

        result = _translate_batch(fake, ["Hello"], _spec())

        assert result == ["fr:Hello"]
        assert clock.sleeps[-1] > clock.sleeps[0]

    def test_persistent_throttling_aborts_instead_of_keeping_original(self, clock):
        """A quota-exhausted engine must fail the task, not write an untranslated SRT."""
        fake = _FakeTranslator(
            {n: Exception(RATE_LIMIT_MESSAGE) for n in range(1, 200)}
        )

        with pytest.raises(TranslationUnavailable):
            _translate_batch(fake, ["Hello", "World"], _spec())

        # No splitting: the retries stop at the attempt budget for the one batch
        assert len(fake.requests) == translator_module._MAX_ATTEMPTS

    def test_healthy_batch_costs_exactly_one_request(self, clock):
        # The invariant the whole rate-limit fix rests on. If the separator the
        # units are joined with ever stops matching the one the reply is split on,
        # every batch looks mangled and recovery degrades to a request per unit.
        fake = _FakeTranslator()

        result = _translate_batch(fake, [f"line {i}" for i in range(40)], _spec())

        assert result == [f"fr:line {i}" for i in range(40)]
        assert len(fake.requests) == 1

    def test_failed_batch_splits_instead_of_one_request_per_unit(self, clock):
        units = [f"line {i}" for i in range(40)]
        # A non-throttle failure on the full batch: no retry, straight to splitting
        fake = _FakeTranslator({1: Exception("Connection reset by peer")})

        result = _translate_batch(fake, units, _spec())

        assert result == [f"fr:{unit}" for unit in units]
        # The old one-by-one fallback issued 1 + 40 requests at 10/s
        assert len(fake.requests) == 3

    def test_mangled_separator_falls_back_to_split(self, clock):
        fake = _FakeTranslator({1: "fr:Hello fr:World"})

        result = _translate_batch(fake, ["Hello", "World"], _spec())

        assert result == ["fr:Hello", "fr:World"]

    def test_single_unit_keeps_untranslatable_reply(self, clock):
        fake = _FakeTranslator({1: None})
        assert _translate_batch(fake, ["Hello"], _spec()) == ["Hello"]

    def test_single_unit_keeps_original_on_plain_failure(self, clock):
        fake = _FakeTranslator({1: Exception("Connection reset by peer")})
        assert _translate_batch(fake, ["Hello"], _spec()) == ["Hello"]

    def test_empty_batch(self, clock):
        fake = _FakeTranslator()
        assert _translate_batch(fake, [], _spec()) == []
        assert fake.requests == []

    def test_split_preserves_order(self, clock):
        fake = _FakeTranslator()

        result = _split_and_translate(fake, ["a", "b", "c", "d", "e"], _spec())

        assert result == ["fr:a", "fr:b", "fr:c", "fr:d", "fr:e"]


# ─────────────────────────────────────────────────────────────────────────────
# Batch sizing against provider limits
# ─────────────────────────────────────────────────────────────────────────────

class TestMakeBatches:
    def test_respects_unit_count(self):
        batches = _make_batches([f"u{i}" for i in range(10)], _spec(batch_size=4))
        assert [len(b) for b in batches] == [4, 4, 2]

    def test_respects_char_ceiling(self):
        # MyMemory's real constraint: 500 chars per request regardless of count
        units = ["x" * 100 for _ in range(10)]
        batches = _make_batches(units, _spec(batch_size=40, max_chars=450))
        assert all(len(translator_module._SEP.join(b)) <= 450 for b in batches)
        assert sum(len(b) for b in batches) == 10

    def test_oversized_unit_is_never_dropped(self):
        batches = _make_batches(["x" * 5000, "short"], _spec(max_chars=450))
        assert [len(b) for b in batches] == [1, 1]

    def test_no_units(self):
        assert _make_batches([], _spec()) == []

    def test_every_unit_survives_batching(self):
        units = [f"line {i}" for i in range(97)]
        batches = _make_batches(units, _spec(batch_size=8, max_chars=450))
        assert [u for b in batches for u in b] == units


# ─────────────────────────────────────────────────────────────────────────────
# Provider registry
# ─────────────────────────────────────────────────────────────────────────────

class TestResolveLang:
    GOOGLE = {"french": "fr", "english": "en"}
    MYMEMORY = {"belgian french": "fr-BE", "french": "fr-FR", "french canada": "fr-CA"}

    def test_bare_code_passes_through(self):
        assert _resolve_lang(self.GOOGLE, "fr") == "fr"

    def test_locale_engine_gets_a_language_name(self):
        assert _resolve_lang(self.MYMEMORY, "fr") == "french"

    def test_prefers_the_plain_variant_over_regional_ones(self):
        """'fr' must not resolve to Belgian French just because it sorts first."""
        assert _resolve_lang(self.MYMEMORY, "fr") == "french"

    def test_auto_passes_through(self):
        assert _resolve_lang(self.MYMEMORY, "auto") == "auto"

    def test_unknown_code_passes_through(self):
        assert _resolve_lang(self.GOOGLE, "xx") == "xx"

    def test_empty_becomes_auto(self):
        assert _resolve_lang(self.GOOGLE, "") == "auto"

    def test_real_engines_resolve_common_languages(self):
        for key in ("google", "mymemory", "libretranslate", "deepl"):
            spec = PROVIDERS[key]
            for iso in ("en", "fr", "de", "es", "pt"):
                resolved = _resolve_lang(spec.languages, iso)
                assert resolved in spec.languages or resolved in spec.languages.values()


class TestResolveProvider:
    def test_known_provider(self):
        assert resolve_provider("mymemory").key == "mymemory"

    def test_case_and_whitespace_tolerant(self):
        assert resolve_provider("  DeepL  ").key == "deepl"

    def test_unknown_falls_back_to_default(self):
        assert resolve_provider("nope").key == DEFAULT_PROVIDER

    def test_empty_falls_back_to_default(self):
        assert resolve_provider("").key == DEFAULT_PROVIDER
        assert resolve_provider(None).key == DEFAULT_PROVIDER


class TestBuildTranslator:
    def test_missing_required_field_is_reported_clearly(self):
        with pytest.raises(RuntimeError, match="API key"):
            build_translator(PROVIDERS["deepl"], "en", "fr", {})

    def test_libretranslate_needs_an_url(self):
        with pytest.raises(RuntimeError, match="Instance URL"):
            build_translator(PROVIDERS["libretranslate"], "en", "fr", {})

    def test_optional_fields_are_not_required(self):
        translator = build_translator(PROVIDERS["mymemory"], "en", "fr", {})
        assert translator is not None

    def test_keyless_engines_need_no_config(self):
        assert build_translator(PROVIDERS["google"], "en", "fr", {}) is not None

    def test_auto_source_falls_back_for_engines_without_detection(self, caplog):
        spec = _spec(supports_auto=False, factory=lambda s, t, c: s)
        assert build_translator(spec, "auto", "fr", {}) == "en"

    def test_auto_source_kept_when_supported(self):
        spec = _spec(supports_auto=True, factory=lambda s, t, c: s)
        assert build_translator(spec, "auto", "fr", {}) == "auto"


class TestDescribeProviders:
    def test_every_provider_is_described(self):
        assert set(describe_providers()) == set(PROVIDERS)

    def test_default_provider_exists(self):
        assert DEFAULT_PROVIDER in PROVIDERS

    def test_fields_carry_what_the_ui_needs(self):
        for info in describe_providers().values():
            assert info["label"]
            assert info["description"]
            for f in info["fields"]:
                assert f["key"] and f["label"]
                assert f["kind"] in ("text", "secret", "toggle")

    def test_keyless_providers_have_no_required_fields(self):
        described = describe_providers()
        for key in ("google", "mymemory"):
            assert not [f for f in described[key]["fields"] if f["required"]]

    def test_field_keys_are_unique_across_providers(self):
        keys = [f.key for spec in PROVIDERS.values() for f in spec.fields]
        assert len(keys) == len(set(keys))
