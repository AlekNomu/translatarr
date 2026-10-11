"""
translatarr.translator
~~~~~~~~~~~~~~~~~~
Subtitle translation through one of several interchangeable engines
(deep-translator backends — see :data:`PROVIDERS`).

All subtitles are pre-processed (SDH skipped, tags stripped, multi-line joined,
dialogues split) into flat single-line "translation units", then batch-translated
in as few HTTP requests as possible, then reassembled with their original
formatting.

Every engine is rate-limited: free endpoints throttle aggressively (Google allows
~5 requests/second per IP), so each provider owns a :class:`_RateLimiter` shared
by all threads, and throttling responses back that limiter off for everyone
instead of being retried blindly.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Protocol

from translatarr.models import Subtitle, SubtitleTrack

try:
    from deep_translator import (  # type: ignore
        DeeplTranslator,
        GoogleTranslator,
        LibreTranslator,
        MyMemoryTranslator,
    )
    from deep_translator.constants import (  # type: ignore
        DEEPL_LANGUAGE_TO_CODE,
        GOOGLE_LANGUAGES_TO_CODES,
        LIBRE_LANGUAGES_TO_CODES,
        MY_MEMORY_LANGUAGES_TO_CODES,
    )
except ImportError:
    DeeplTranslator = None  # type: ignore
    GoogleTranslator = None  # type: ignore
    LibreTranslator = None  # type: ignore
    MyMemoryTranslator = None  # type: ignore
    DEEPL_LANGUAGE_TO_CODE = {}  # type: ignore
    GOOGLE_LANGUAGES_TO_CODES = {}  # type: ignore
    LIBRE_LANGUAGES_TO_CODES = {}  # type: ignore
    MY_MEMORY_LANGUAGES_TO_CODES = {}  # type: ignore

logger = logging.getLogger("translatarr")

__all__ = [
    "PROVIDERS", "DEFAULT_PROVIDER", "ProviderField", "ProviderSpec",
    "TranslationUnavailable",
    "translate_track", "describe_providers", "resolve_provider", "build_translator",
]


class TranslationUnavailable(RuntimeError):
    """Raised when an engine throttles us so hard that retrying is pointless.

    Aborting beats degrading: a half-translated SRT written to disk under the
    target language's name looks like success and never gets retried.
    """


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Batches travel as one string with units joined by this token. It is padded on
# the way out because engines mangle a token glued to adjacent words, but split
# on bare because they just as often eat the padding. Deriving one from the other
# matters: a mismatch here makes every batch look corrupted, and the recovery
# path would quietly degrade into one request per unit.
_SEP_TOKEN = "|||SEP|||"
_SEP = f" {_SEP_TOKEN} "

_MAX_ATTEMPTS = 6
_INITIAL_BACKOFF = 1.0
_BACKOFF_FACTOR = 2.0
_MAX_BACKOFF = 60.0

# Substrings identifying a throttling response (deep-translator raises a generic
# error whose message carries the "5 requests per second" explanation). Matched
# against the message with underscores flattened, so Yandex-style
# ERR_TOO_MANY_REQUESTS codes hit the same markers.
_RATE_LIMIT_MARKERS = (
    "too many requests",
    "429",
    "requests per second",
    "quota",
    "rate limit",
    "limit exceeded",
)

# Matches any HTML/SRT tag (<i>, </b>, <font color="…">) — used to strip formatting before translation
_TAG_PATTERN = re.compile(r"</?[a-zA-Z][^>]*>")
# Same but anchored at end-of-string — lets _strip_tags peel trailing tags without touching mid-text ones
_TRAILING_TAG_PATTERN = re.compile(r"</?[a-zA-Z][^>]*>\s*$")
# Matches SDH/CC annotations ([music], (laughing), ♪…♪) — these are skipped, never sent to translation
_SDH_PATTERN = re.compile(r"\[.*?\]|\(.*?\)|♪.*?♪", re.DOTALL)


# ─────────────────────────────────────────────────────────────────────────────
# Translator protocol
# ─────────────────────────────────────────────────────────────────────────────

class _Translator(Protocol):
    def translate(self, text: str) -> str: ...


# ─────────────────────────────────────────────────────────────────────────────
# Rate limiting
# ─────────────────────────────────────────────────────────────────────────────

class _RateLimiter:
    """Spaces out requests so they never exceed *rate* per second.

    Thread-safe and shared process-wide: endpoints throttle per IP, so parallel
    translation tasks must draw from the same budget. A rate of 0 disables it.
    """

    def __init__(self, rate: float) -> None:
        self._min_interval = 1.0 / rate if rate > 0 else 0.0
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def acquire(self) -> None:
        """Block until the caller is allowed to issue its request."""
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            self._next_allowed = max(now, self._next_allowed) + self._min_interval
        if wait > 0:
            time.sleep(wait)

    def penalize(self, seconds: float) -> None:
        """Delay the next slot for *every* caller, not just the throttled one."""
        with self._lock:
            self._next_allowed = max(self._next_allowed, time.monotonic() + seconds)


# ─────────────────────────────────────────────────────────────────────────────
# Provider registry
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ProviderField:
    """One piece of provider configuration the user has to fill in.

    *key* is the settings key it is stored under, so the web layer can render
    the right inputs without knowing anything about individual engines.
    """
    key: str
    label: str
    kind: str = "text"      # text | secret | toggle — tells the UI which input to render
    required: bool = False
    help: str = ""
    placeholder: str = ""


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    """Everything the pipeline needs to drive one translation engine."""
    key: str
    label: str
    description: str
    factory: Callable[[str, str, dict[str, str]], "_Translator"]
    languages: dict[str, str]
    requests_per_second: float
    # Per-request ceilings imposed by the remote API — batches are split to fit
    max_chars: int
    batch_size: int
    supports_auto: bool = True
    fields: tuple[ProviderField, ...] = ()
    limiter: _RateLimiter = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "limiter", _RateLimiter(self.requests_per_second))

    def missing_fields(self, config: dict[str, str]) -> list[ProviderField]:
        """Return the required fields *config* does not supply."""
        return [f for f in self.fields if f.required and not (config.get(f.key) or "").strip()]


def _resolve_lang(languages: dict[str, str], lang: str) -> str:
    """Map an ISO 639-1 code onto whatever name/code *languages* accepts.

    deep-translator engines disagree on vocabulary: Google takes ``fr``, MyMemory
    only ``french`` or ``fr-FR``. Bare codes pass through; otherwise the engine's
    own table is searched for a locale with that prefix, preferring the shortest
    name so ``fr`` resolves to "french" rather than "belgian french".
    """
    lang = (lang or "").strip().lower()
    if not lang or lang == "auto" or not languages:
        return lang or "auto"
    if lang in languages or lang in {code.lower() for code in languages.values()}:
        return lang
    candidates = [
        name for name, code in languages.items() if code.lower().startswith(f"{lang}-")
    ]
    return min(candidates, key=len) if candidates else lang


def _instantiate(cls, languages: dict[str, str], source: str, target: str, **kwargs):
    return cls(
        source=_resolve_lang(languages, source),
        target=_resolve_lang(languages, target),
        **kwargs,
    )


def _build_google(source: str, target: str, config: dict[str, str]) -> _Translator:
    return _instantiate(GoogleTranslator, GOOGLE_LANGUAGES_TO_CODES, source, target)


def _build_mymemory(source: str, target: str, config: dict[str, str]) -> _Translator:
    return _instantiate(
        MyMemoryTranslator, MY_MEMORY_LANGUAGES_TO_CODES, source, target,
        email=(config.get("mymemory_email") or "").strip() or None,
    )


def _build_libretranslate(source: str, target: str, config: dict[str, str]) -> _Translator:
    url = (config.get("libretranslate_url") or "").strip()
    if url and not url.endswith("/"):
        url += "/"
    return _instantiate(
        LibreTranslator, LIBRE_LANGUAGES_TO_CODES, source, target,
        # LibreTranslator refuses to build without a key; self-hosted instances
        # with authentication disabled just ignore the parameter.
        api_key=(config.get("libretranslate_api_key") or "").strip() or "-",
        custom_url=url or None,
    )


def _build_deepl(source: str, target: str, config: dict[str, str]) -> _Translator:
    return _instantiate(
        DeeplTranslator, DEEPL_LANGUAGE_TO_CODE, source, target,
        api_key=(config.get("deepl_api_key") or "").strip(),
        use_free_api=config.get("deepl_free_api", "1") != "0",
    )


DEFAULT_PROVIDER = "google"

PROVIDERS: dict[str, ProviderSpec] = {
    "google": ProviderSpec(
        key="google",
        label="Google Translate",
        description="Free, no API key. Throttled at 5 requests/second per IP.",
        factory=_build_google,
        languages=GOOGLE_LANGUAGES_TO_CODES,
        requests_per_second=4.0,
        max_chars=4500,
        batch_size=40,
    ),
    "mymemory": ProviderSpec(
        key="mymemory",
        label="MyMemory",
        description=(
            "Free, no API key. Slower than Google: 500 characters per request, "
            "plus a daily word quota that an email raises."
        ),
        factory=_build_mymemory,
        languages=MY_MEMORY_LANGUAGES_TO_CODES,
        requests_per_second=2.0,
        max_chars=450,
        batch_size=8,
        supports_auto=False,
        fields=(
            ProviderField(
                key="mymemory_email",
                label="Contact email (optional)",
                help="Raises the free daily quota from 1 000 to 50 000 words.",
                placeholder="you@example.com",
            ),
        ),
    ),
    "libretranslate": ProviderSpec(
        key="libretranslate",
        label="LibreTranslate",
        description=(
            "Self-hosted and open source, with no quota and no throttling when "
            "you run your own instance."
        ),
        factory=_build_libretranslate,
        languages=LIBRE_LANGUAGES_TO_CODES,
        requests_per_second=20.0,
        max_chars=4500,
        batch_size=40,
        fields=(
            ProviderField(
                key="libretranslate_url",
                label="Instance URL",
                required=True,
                help="Base URL of your LibreTranslate server.",
                placeholder="http://libretranslate:5000",
            ),
            ProviderField(
                key="libretranslate_api_key",
                label="API key (optional)",
                kind="secret",
                help="Only needed if your instance requires authentication.",
            ),
        ),
    ),
    "deepl": ProviderSpec(
        key="deepl",
        label="DeepL",
        description="Best quality for subtitles, but requires an API key.",
        factory=_build_deepl,
        languages=DEEPL_LANGUAGE_TO_CODE,
        requests_per_second=10.0,
        max_chars=4500,
        batch_size=40,
        supports_auto=False,
        fields=(
            ProviderField(
                key="deepl_api_key",
                label="API key",
                kind="secret",
                required=True,
                help="From your DeepL account page.",
            ),
            ProviderField(
                key="deepl_free_api",
                label="Free tier account",
                kind="toggle",
                help="Turn off if you have a DeepL Pro subscription.",
            ),
        ),
    ),
}


def describe_providers() -> dict[str, dict]:
    """Serialize :data:`PROVIDERS` for the settings API.

    ``order`` is carried explicitly because JSON objects reach the UI with their
    keys sorted, which would otherwise bury the keyless default under DeepL.
    """
    return {
        spec.key: {
            "label": spec.label,
            "description": spec.description,
            "supports_auto": spec.supports_auto,
            "order": index,
            "fields": [
                {
                    "key": f.key,
                    "label": f.label,
                    "kind": f.kind,
                    "required": f.required,
                    "help": f.help,
                    "placeholder": f.placeholder,
                }
                for f in spec.fields
            ],
        }
        for index, spec in enumerate(PROVIDERS.values())
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pre-processing: subtitle → translation units
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(slots=True)
class _PreparedSub:
    """A subtitle broken down into translatable units with reconstruction info."""
    original: Subtitle
    unit_texts: list[str]       # texts to send to the engine (empty = skip)
    num_lines: int              # original line count (for re-wrapping)
    is_dialogue: bool           # True → reassemble with "-" prefixes
    tag_prefix: str             # HTML tags to restore before text
    tag_suffix: str             # HTML tags to restore after text


def _prepare(sub: Subtitle) -> _PreparedSub:
    """Break a subtitle into flat, single-line translation units."""
    text = sub.text

    if _is_sdh(text):
        return _PreparedSub(sub, [], 1, False, "", "")

    clean, prefix, suffix = _strip_tags(text)
    if not clean.strip():
        return _PreparedSub(sub, [], 1, False, "", "")

    lines = clean.split("\n")

    if len(lines) > 1 and _is_dialogue(lines):
        speeches = [
            line.strip().lstrip("-").strip()
            for line in lines
            if line.strip().lstrip("-").strip()
        ]
        return _PreparedSub(sub, speeches, len(lines), True, prefix, suffix)

    joined = " ".join(line.strip() for line in lines)
    return _PreparedSub(sub, [joined], len(lines), False, prefix, suffix)


def _reassemble(prep: _PreparedSub, translated: list[str]) -> str:
    """Reconstruct the final subtitle text from translated units."""
    if not prep.unit_texts:
        return prep.original.text

    if prep.is_dialogue:
        text = "\n".join("-" + t for t in translated)
    elif prep.num_lines > 1:
        text = _rewrap(translated[0], prep.num_lines)
    else:
        text = translated[0]

    return prep.tag_prefix + text + prep.tag_suffix


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def translate_track(
    track: SubtitleTrack,
    source_lang: str = "auto",
    target_lang: str = "fr",
    provider: str = DEFAULT_PROVIDER,
    provider_config: dict[str, str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
) -> SubtitleTrack:
    """Return a new :class:`SubtitleTrack` with every text translated.

    Timings are preserved exactly — only the ``text`` field changes.
    *provider* selects an engine from :data:`PROVIDERS`; *provider_config* carries
    its credentials (API keys, instance URL) straight from the settings table.
    *on_progress(done, total)* is called after each batch if provided.
    """
    spec = resolve_provider(provider)
    translator = build_translator(spec, source_lang, target_lang, provider_config or {})
    subtitles = list(track)
    total = len(subtitles)

    # ── Phase 1: pre-process ───────────────────────────────────────────
    prepared = [_prepare(sub) for sub in subtitles]

    # Flat index mapping: each unit → (prep_index, unit_index_within_prep)
    all_units: list[str] = []
    unit_map: list[tuple[int, int]] = []
    for prep_idx, prep in enumerate(prepared):
        for unit_idx, text in enumerate(prep.unit_texts):
            all_units.append(text)
            unit_map.append((prep_idx, unit_idx))

    # ── Phase 2: batch translate ──────────────────────────────────────────
    translated_units = _batch_translate_all(
        translator, all_units, spec, total, on_progress,
    )

    # ── Phase 3: reassemble ──────────────────────────────────────────────
    results_per_prep: list[list[str]] = [[] for _ in prepared]
    for (prep_idx, _), translated_text in zip(unit_map, translated_units):
        results_per_prep[prep_idx].append(translated_text)

    translated_subs: list[Subtitle] = []
    for prep, result_texts in zip(prepared, results_per_prep):
        new_text = _reassemble(prep, result_texts)
        translated_subs.append(replace(prep.original, text=new_text.strip()))

    return SubtitleTrack(subtitles=translated_subs)


# ─────────────────────────────────────────────────────────────────────────────
# Batch translation engine
# ─────────────────────────────────────────────────────────────────────────────

def _make_batches(units: list[str], spec: ProviderSpec) -> list[list[str]]:
    """Group *units* into batches fitting the provider's per-request ceilings.

    Both limits matter: MyMemory caps a request at 500 characters, which a count
    based split alone would blow through on long subtitles.
    """
    batches: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for unit in units:
        added = len(unit) + len(_SEP)
        if current and (
            len(current) >= spec.batch_size or current_chars + added > spec.max_chars
        ):
            batches.append(current)
            current, current_chars = [], 0
        current.append(unit)
        current_chars += added
    if current:
        batches.append(current)
    return batches


def _batch_translate_all(
    translator: _Translator,
    units: list[str],
    spec: ProviderSpec,
    subtitle_count: int,
    on_progress: Callable[[int, int], None] | None = None,
) -> list[str]:
    """Translate all units via batched requests, splitting batches that fail."""
    if not units:
        return []

    results: list[str] = []
    for batch in _make_batches(units, spec):
        results.extend(_translate_batch(translator, batch, spec))

        if on_progress:
            # Progress based on subtitle count (not unit count) for user clarity
            progress = min(len(results) * subtitle_count // max(len(units), 1), subtitle_count)
            on_progress(progress, subtitle_count)

    return results


def _request(translator: _Translator, text: str, spec: ProviderSpec) -> str:
    """Issue one rate-limited request, retrying throttled ones with backoff.

    The backoff is applied to the provider's shared limiter, so a 429 slows every
    worker down rather than letting the others keep hammering the endpoint.
    """
    delay = _INITIAL_BACKOFF
    attempt = 0
    while True:
        attempt += 1
        spec.limiter.acquire()
        try:
            return translator.translate(text)
        except Exception as exc:
            if not _is_rate_limit(exc):
                raise
            if attempt >= _MAX_ATTEMPTS:
                raise TranslationUnavailable(
                    f"{spec.label} is still throttling after {_MAX_ATTEMPTS} attempts. "
                    "Your daily quota is likely exhausted. Pick another translation "
                    "engine in Settings, or try again later."
                ) from exc
            logger.warning(
                "%s throttled us — backing off %.0fs (attempt %d/%d)",
                spec.label, delay, attempt, _MAX_ATTEMPTS,
            )
            spec.limiter.penalize(delay)
            delay = min(delay * _BACKOFF_FACTOR, _MAX_BACKOFF)


def _translate_batch(
    translator: _Translator, batch: list[str], spec: ProviderSpec,
) -> list[str]:
    """Translate a batch of pre-processed texts in one request.

    A batch that fails or comes back with a mangled separator is split in half
    and retried — O(log n) extra requests instead of one request per unit, which
    is what used to trip the rate limit.
    """
    if not batch:
        return []

    try:
        result = _request(translator, _SEP.join(batch), spec)
    except TranslationUnavailable:
        # Exhausted throttling — splitting would only multiply the requests
        raise
    except Exception as exc:
        if len(batch) == 1:
            logger.warning("Translation failed for unit, keeping original: %s", exc)
            return list(batch)
        logger.warning("Batch of %d failed (%s) — splitting in two", len(batch), exc)
        return _split_and_translate(translator, batch, spec)

    parts = result.split(_SEP_TOKEN) if result else []
    if len(parts) == len(batch):
        return [part.strip() for part in parts]

    if len(batch) == 1:
        return [result.strip() if result else batch[0]]

    return _split_and_translate(translator, batch, spec)


def _split_and_translate(
    translator: _Translator, batch: list[str], spec: ProviderSpec,
) -> list[str]:
    mid = len(batch) // 2
    return (
        _translate_batch(translator, batch[:mid], spec)
        + _translate_batch(translator, batch[mid:], spec)
    )


def _is_rate_limit(exc: Exception) -> bool:
    """Return True if *exc* is the endpoint telling us to slow down."""
    # Underscores flattened so ERR_TOO_MANY_REQUESTS-style codes match too
    message = str(exc).lower().replace("_", " ")
    return any(marker in message for marker in _RATE_LIMIT_MARKERS)


# ─────────────────────────────────────────────────────────────────────────────
# Text pre-processing helpers
# ─────────────────────────────────────────────────────────────────────────────

def _is_sdh(text: str) -> bool:
    """Return True if *text* is purely an SDH/CC annotation."""
    stripped = _SDH_PATTERN.sub("", text).strip()
    return len(stripped) == 0 and len(text.strip()) > 0


def _is_dialogue(lines: list[str]) -> bool:
    """Return True if every non-empty line starts with ``-`` (dialogue)."""
    return all(line.strip().startswith("-") for line in lines if line.strip())


def _strip_tags(text: str) -> tuple[str, str, str]:
    """Strip leading/trailing HTML tags from *text*.

    Returns ``(clean_text, prefix_tags, suffix_tags)``.
    """
    prefix = ""
    tmp = text
    while (tag_match := _TAG_PATTERN.match(tmp)):
        prefix += tag_match.group()
        tmp = tmp[tag_match.end():]

    suffix = ""
    while (tag_match := _TRAILING_TAG_PATTERN.search(tmp)):
        suffix = tag_match.group().strip() + suffix
        tmp = tmp[:tag_match.start()]

    clean = _TAG_PATTERN.sub("", tmp)
    return clean, prefix, suffix


def _rewrap(text: str, num_lines: int) -> str:
    """Split *text* into *num_lines* lines of roughly equal word count."""
    if num_lines <= 1:
        return text
    words = text.split()
    if len(words) <= num_lines:
        return "\n".join(words)
    base, extra = divmod(len(words), num_lines)
    lines: list[str] = []
    idx = 0
    for i in range(num_lines):
        count = base + (1 if i < extra else 0)
        lines.append(" ".join(words[idx : idx + count]))
        idx += count
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Provider selection
# ─────────────────────────────────────────────────────────────────────────────

def resolve_provider(provider: str | None) -> ProviderSpec:
    """Return the spec for *provider*, falling back to the default if unknown.

    An unknown name means a stale or hand-edited setting; translating with Google
    beats failing the whole task, so it is a warning rather than an error.
    """
    key = (provider or "").strip().lower() or DEFAULT_PROVIDER
    spec = PROVIDERS.get(key)
    if spec is None:
        logger.warning("Unknown translation provider %r — falling back to Google", key)
        return PROVIDERS[DEFAULT_PROVIDER]
    return spec


def build_translator(
    spec: ProviderSpec,
    source_lang: str,
    target_lang: str,
    config: dict[str, str],
) -> _Translator:
    """Instantiate *spec*'s deep-translator backend, validating its config first."""
    _require_deep_translator()

    missing = spec.missing_fields(config)
    if missing:
        raise RuntimeError(
            f"{spec.label} is not fully configured. Missing: "
            + ", ".join(f.label for f in missing)
        )

    if source_lang == "auto" and not spec.supports_auto:
        logger.warning(
            "%s cannot auto-detect the source language — assuming English",
            spec.label,
        )
        source_lang = "en"

    return spec.factory(source_lang, target_lang, config)


# ─────────────────────────────────────────────────────────────────────────────
# Dependency check
# ─────────────────────────────────────────────────────────────────────────────

def _require_deep_translator() -> None:
    if GoogleTranslator is None:
        raise RuntimeError(
            "'deep-translator' is not installed.\n"
            "    Run: pip install deep-translator"
        )
