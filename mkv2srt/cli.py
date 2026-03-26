"""
mkv2srt.cli
~~~~~~~~~~~
Command-line interface for mkv2srt.

Entry point: ``python -m mkv2srt`` or the ``mkv2srt`` console script.
"""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from mkv2srt import __version__
from mkv2srt.audio import (
    extract_audio,
    extract_subtitle,
    find_embedded_sub_index,
    get_duration,
    require_ffmpeg,
)
from mkv2srt.models import SubtitleTrack
from mkv2srt.srt_io import read_srt, write_srt
from mkv2srt.sync_checker import check_sync
from mkv2srt.transcriber import WHISPER_MODELS, transcribe
from mkv2srt.translator import translate_track

_OUTPUT_SUFFIXES = (".srt", ".cc.srt", ".sdh.srt")

# ─────────────────────────────────────────────────────────────────────────────
# Argument parser
# ─────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mkv2srt",
        description="Generate or translate French subtitles (.srt) from MKV files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
examples:
  # MKV → transcribe (Whisper) + translate → French .srt (default)
  mkv2srt movie.mkv

  # Translate to Spanish instead
  mkv2srt movie.mkv --target es

  # Force source language (skips auto-detection, faster)
  mkv2srt movie.mkv --language en

  # Use a more accurate Whisper model
  mkv2srt movie.mkv --model large

  # Translate an existing English .srt (timings preserved)
  mkv2srt --from-srt movie.en.srt -o movie.fr.srt

  # Disable sync validation (on by default)
  mkv2srt movie.mkv --no-sync-check

  # Scan a directory recursively for all MKV files
  mkv2srt --scan /mnt/my_series

  # Scan the current directory
  mkv2srt --scan

Whisper models  (fastest → most accurate):
  {'  '.join(WHISPER_MODELS)}   [default: medium]
""",
    )

    parser.add_argument(
        "input",
        type=Path,
        nargs="?",
        metavar="INPUT.mkv",
        help="Source MKV file. Optional when using --from-srt alone.",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        metavar="OUTPUT.srt",
        help="Output SRT path. Defaults to <input>.fr.srt.",
    )
    parser.add_argument(
        "--model",
        default="medium",
        choices=WHISPER_MODELS,
        metavar="MODEL",
        help=f"Whisper model size. Choices: {', '.join(WHISPER_MODELS)}. (default: medium)",
    )
    parser.add_argument(
        "--language",
        default=None,
        metavar="LANG",
        help="Audio language for Whisper, e.g. 'en', 'de', 'es'. Auto-detected when omitted.",
    )
    parser.add_argument(
        "-t", "--target",
        default="fr",
        metavar="LANG",
        help="Target language code for translation, e.g. 'fr', 'es', 'de'. (default: fr)",
    )
    parser.add_argument(
        "--from-srt",
        type=Path,
        default=None,
        metavar="FILE.srt",
        help="Translate an existing SRT file (timings are preserved).",
    )
    parser.add_argument(
        "--no-sync-check",
        action="store_false",
        dest="sync_check",
        help="Disable timing validation (sync check runs by default).",
    )
    parser.add_argument(
        "--scan",
        nargs="?",
        const=".",
        type=Path,
        default=None,
        metavar="DIR",
        help="Scan a directory recursively for MKV files. Defaults to current dir.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"mkv2srt {__version__}",
    )

    return parser

def _resolve_output(args: argparse.Namespace) -> Path:
    if args.output:
        return args.output
    lang = args.target
    base = args.input if args.input else args.from_srt
    stem = base.stem
    parent = base.parent
    for suffix in _OUTPUT_SUFFIXES:
        candidate = parent / f"{stem}.{lang}{suffix}"
        if not candidate.exists():
            return candidate
    i = 2
    while True:
        candidate = parent / f"{stem}.{lang}.{i}.srt"
        if not candidate.exists():
            return candidate
        i += 1


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    print(f"  {msg}")


def _log_sync(issues: list) -> None:
    if not issues:
        _log("Sync check: OK")
    else:
        _log(f"Sync check: {len(issues)} issue(s)")
        for issue in issues:
            _log(f"  {issue}")


# ─────────────────────────────────────────────────────────────────────────────
# Subtitle lookup
# ─────────────────────────────────────────────────────────────────────────────

_EN_SRT_TAGS = ("en", "eng", "english", "")

# ISO 639 short → common variants for finding existing SRT files
_LANG_TAG_ALIASES: dict[str, tuple[str, ...]] = {
    "fr": ("fr", "fre", "french"),
    "en": ("en", "eng", "english"),
    "es": ("es", "spa", "spanish"),
    "de": ("de", "deu", "ger", "german"),
    "it": ("it", "ita", "italian"),
    "pt": ("pt", "por", "portuguese"),
}


def _target_srt_tags(lang: str) -> tuple[str, ...]:
    return _LANG_TAG_ALIASES.get(lang, (lang,))


def _find_srt_by_lang(mkv_path: Path, lang_tags: tuple[str, ...]) -> Path | None:
    """Look for an existing .srt next to the MKV file matching one of the language tags."""
    stem = mkv_path.stem
    parent = mkv_path.parent
    for tag in lang_tags:
        suffix = f".{tag}.srt" if tag else ".srt"
        candidate = parent / f"{stem}{suffix}"
        if candidate.exists():
            return candidate
    return None


def _get_english_srt(args: argparse.Namespace) -> tuple[Path | None, Path | None]:
    """Find an English .srt (external file or embedded in MKV).

    Returns (english_srt_path, embedded_srt_path).
    embedded_srt_path is set only when extraction was needed (for cleanup).
    """
    existing_srt = _find_srt_by_lang(args.input, _EN_SRT_TAGS)
    embedded_srt_path: Path | None = None

    if not existing_srt:
        sub_index = find_embedded_sub_index(args.input)
        if sub_index is not None:
            tmp = tempfile.NamedTemporaryFile(suffix=".srt", delete=False)
            embedded_srt_path = Path(tmp.name)
            tmp.close()
            extract_subtitle(args.input, sub_index, embedded_srt_path)
            existing_srt = embedded_srt_path

    return existing_srt, embedded_srt_path


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline modes
# ─────────────────────────────────────────────────────────────────────────────

def _run_from_srt(args: argparse.Namespace, output_path: Path) -> None:
    """Translate an existing SRT file."""
    track = read_srt(args.from_srt)
    _log(f"Source: {args.from_srt.name} ({len(track)} entries)")
    track = translate_track(track, target_lang=args.target)

    if args.sync_check:
        duration = get_duration(args.input) if args.input else None
        issues = check_sync(track, duration)
        _log_sync(issues)

    write_srt(track, output_path)


def _run_from_mkv(args: argparse.Namespace, output_path: Path) -> bool:
    """Full pipeline from an MKV file.

    Returns False if no work was needed (already aligned), True otherwise.
    """
    require_ffmpeg()

    video_duration = get_duration(args.input) if args.sync_check else None

    english_srt, embedded_srt_path = _get_english_srt(args)
    target_srt = _find_srt_by_lang(args.input, _target_srt_tags(args.target))

    try:
        track = _resolve_track(args, english_srt, target_srt, embedded_srt_path)
    except _AlreadyAligned:
        return False
    finally:
        if embedded_srt_path and embedded_srt_path.exists():
            embedded_srt_path.unlink()

    if args.sync_check:
        issues = check_sync(track, video_duration)
        _log_sync(issues)

    write_srt(track, output_path)
    return True


class _AlreadyAligned(Exception):
    """Raised when French and English SRTs are already in sync."""


def _resolve_track(
    args: argparse.Namespace,
    english_srt: Path | None,
    target_srt: Path | None,
    embedded_srt_path: Path | None = None,
) -> SubtitleTrack:
    """Decide which pipeline branch to run and return the resulting track."""
    target = args.target

    if target_srt and english_srt:
        en_track = read_srt(english_srt)
        tgt_track = read_srt(target_srt)
        _log(f"Target SRT: {target_srt.name} ({len(tgt_track)} entries)")
        _log(f"English SRT: {english_srt.name} ({len(en_track)} entries)")

        if len(en_track) == len(tgt_track):
            if tgt_track.has_same_timestamps(en_track):
                _log("Already aligned — nothing to do.")
                raise _AlreadyAligned

            _log("Resyncing target timestamps from English…")
            return tgt_track.resync_from(en_track)

        _log(f"Entry count mismatch (EN={len(en_track)}, TGT={len(tgt_track)}) — translating EN")
        return translate_track(en_track, source_lang="en", target_lang=target)

    if english_srt:
        track = read_srt(english_srt)
        source = "embedded" if embedded_srt_path else english_srt.name
        _log(f"English SRT: {source} ({len(track)} entries)")
        return translate_track(track, source_lang="en", target_lang=target)

    _log(f"No subtitles found — transcribing with Whisper ({args.model})")

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = Path(tmp.name)
    try:
        _log("Extracting audio…")
        extract_audio(args.input, wav_path)
        _log("Transcribing…")
        track, detected_lang = transcribe(
            wav_path, model_name=args.model, language=args.language,
        )
        _log(f"Detected language: {detected_lang} — {len(track)} segments")
    finally:
        if wav_path.exists():
            wav_path.unlink()

    return translate_track(track, source_lang=args.language or "auto", target_lang=target)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def _run_single(args: argparse.Namespace) -> None:
    """Process a single file (MKV or --from-srt)."""
    output_path = _resolve_output(args)

    if args.from_srt:
        _run_from_srt(args, output_path)
    else:
        if not _run_from_mkv(args, output_path):
            return

    print(f"→ {output_path}")


def _run_scan(args: argparse.Namespace) -> None:
    """Scan a directory recursively for MKV files and process each one."""
    scan_dir = args.scan.resolve()
    if not scan_dir.is_dir():
        print(f"Not a directory: {scan_dir}")
        return

    mkv_files = sorted(scan_dir.rglob("*.mkv"))
    if not mkv_files:
        print(f"No MKV files found in {scan_dir}")
        return

    total = len(mkv_files)
    print(f"Scanning {scan_dir} — {total} MKV file(s)\n")

    succeeded, failed = 0, 0
    for i, mkv in enumerate(mkv_files, 1):
        print(f"[{i}/{total}] {mkv.relative_to(scan_dir)}")
        args.input = mkv
        try:
            _run_single(args)
            succeeded += 1
        except Exception as exc:
            print(f"  Error: {exc}")
            failed += 1
        print()

    print(f"Done: {succeeded} succeeded, {failed} failed")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args   = parser.parse_args(argv)

    if args.scan is not None:
        if args.output:
            parser.error("--output cannot be used with --scan.")
        if args.from_srt:
            parser.error("--from-srt cannot be used with --scan.")
        _run_scan(args)
        return

    if args.input is None and args.from_srt is None:
        parser.error("Provide an INPUT.mkv file, use --from-srt <file.srt>, or use --scan [DIR].")

    if args.input and not args.input.exists():
        parser.error(f"File not found: {args.input}")

    if args.from_srt and not args.from_srt.exists():
        parser.error(f"SRT file not found: {args.from_srt}")

    _run_single(args)


if __name__ == "__main__":
    main()
