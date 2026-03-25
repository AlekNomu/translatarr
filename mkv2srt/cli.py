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
from mkv2srt.audio       import (extract_audio, extract_subtitle,
                                  find_embedded_sub_index, get_duration,
                                  require_ffmpeg)
from mkv2srt.models       import SubtitleTrack
from mkv2srt.srt_io       import read_srt, write_srt
from mkv2srt.sync_checker import check_sync
from mkv2srt.transcriber  import WHISPER_MODELS, transcribe
from mkv2srt.translator   import translate_track

_FR_SUFFIXES = [".fr.srt", ".fr.cc.srt", ".fr.sdh.srt"]

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
  # MKV → transcribe (Whisper) + translate → French .srt
  mkv2srt movie.mkv

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
        "--from-srt",
        type=Path,
        default=None,
        metavar="FILE.srt",
        help="Translate an existing SRT file to French (timings are preserved).",
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
    base = args.input if args.input else args.from_srt
    stem = base.stem
    # Strip existing .fr / .en / etc. suffix from the stem if present
    # so we build from the clean base name.
    parent = base.parent
    # For a file like "movie.en.srt", stem is "movie.en" — we want "movie".
    # For an MKV like "movie.mkv", stem is "movie" — already fine.
    # We only need the raw stem without language tags for MKV inputs.
    for suffix in _FR_SUFFIXES:
        candidate = parent / f"{stem}{suffix}"
        if not candidate.exists():
            if suffix != ".fr.srt":
                print(f"[!] {stem}.fr.srt already exists → writing to {stem}{suffix}")
            return candidate
    # All common suffixes taken — fall back to numbered
    i = 2
    while True:
        candidate = parent / f"{stem}.fr.{i}.srt"
        if not candidate.exists():
            print(f"[!] All standard suffixes taken → writing to {stem}.fr.{i}.srt")
            return candidate
        i += 1


def _run_from_srt(args: argparse.Namespace, output_path: Path) -> None:
    """Mode A — translate an existing SRT file."""
    track = read_srt(args.from_srt)
    track = translate_track(track)

    if args.sync_check:
        duration = get_duration(args.input) if args.input else None
        check_sync(track, duration)

    write_srt(track, output_path)


_EN_SRT_TAGS = ("en", "eng", "english", "")
_FR_SRT_TAGS = ("fr", "fre", "french")


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


def _run_from_mkv(args: argparse.Namespace, output_path: Path) -> bool:
    """Mode B — full pipeline from an MKV file.

    Priority order:
    1. If a French .srt AND an English .srt both exist with the same entry
       count → resync the French timestamps from the English ones.
    2. If an English .srt exists (but no French, or different count)
       → translate it to French.
    3. Otherwise → Whisper transcribe + translate to French.

    Returns False if no work was needed (already aligned), True otherwise.
    """
    require_ffmpeg()

    video_duration = get_duration(args.input) if args.sync_check else None

    # ── Look for existing subtitles ──────────────────────────────────────────
    english_srt, embedded_srt_path = _get_english_srt(args)
    french_srt = _find_srt_by_lang(args.input, _FR_SRT_TAGS)

    # ── Resync: French text + English timestamps ─────────────────────────────
    if french_srt and english_srt:
        en_track = read_srt(english_srt)
        fr_track = read_srt(french_srt)

        if len(en_track) == len(fr_track):
            if fr_track.has_same_timestamps(en_track):
                print(f"FR and EN already aligned ({len(fr_track)} entries) — nothing to do.")
                if embedded_srt_path and embedded_srt_path.exists():
                    embedded_srt_path.unlink()
                return False

            print(f"Resync: {len(fr_track)} entries match between EN and FR")
            print(f"    → Applying timestamps from {english_srt.name}")
            track = fr_track.resync_from(en_track)
        else:
            print(
                f"Entry count mismatch (EN={len(en_track)}, FR={len(fr_track)})"
                " → translating EN instead"
            )
            track = translate_track(en_track, source_lang="en")

    # ── Translate existing English .srt ──────────────────────────────────────
    elif english_srt:
        print(f"Using SRT: {english_srt}")
        print("    → Translating to French (timings preserved)…")
        track = read_srt(english_srt)
        track = translate_track(track, source_lang="en")

    # ── Full Whisper pipeline ────────────────────────────────────────────────
    else:
        print("No SRT found (external or embedded) — running Whisper transcription…")

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = Path(tmp.name)
        try:
            track = _transcribe(args, wav_path)
        finally:
            if wav_path.exists():
                wav_path.unlink()

        track = translate_track(track, source_lang=args.language or "auto")

    # ── Cleanup embedded extraction ──────────────────────────────────────────
    if embedded_srt_path and embedded_srt_path.exists():
        embedded_srt_path.unlink()

    # ── Sync check (on by default) ──────────────────────────────────────────
    if args.sync_check:
        check_sync(track, video_duration)

    write_srt(track, output_path)
    return True


def _transcribe(args: argparse.Namespace, wav_path: Path) -> SubtitleTrack:
    extract_audio(args.input, wav_path)
    return transcribe(wav_path, model_name=args.model, language=args.language)


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

    print(f"\nDone! Output → {output_path}\n")


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

    print(f"Found {len(mkv_files)} MKV file(s) in {scan_dir}\n")

    succeeded, failed = 0, 0
    for i, mkv in enumerate(mkv_files, 1):
        print(f"\n{'-' * 60}")
        print(f"  [{i}/{len(mkv_files)}] {mkv.relative_to(scan_dir)}")
        print(f"{'-' * 60}\n")

        args.input = mkv
        try:
            _run_single(args)
            succeeded += 1
        except Exception as exc:
            print(f"\nError processing {mkv.name}: {exc}\n")
            failed += 1

    print(f"\n{'-' * 60}")
    print(f"  Scan complete: {succeeded} succeeded, {failed} failed")


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args   = parser.parse_args(argv)

    # ── Scan mode ─────────────────────────────────────────────────────────────
    if args.scan is not None:
        if args.output:
            parser.error("--output cannot be used with --scan.")
        if args.from_srt:
            parser.error("--from-srt cannot be used with --scan.")
        _run_scan(args)
        return

    # ── Single-file mode ──────────────────────────────────────────────────────
    if args.input is None and args.from_srt is None:
        parser.error("Provide an INPUT.mkv file, use --from-srt <file.srt>, or use --scan [DIR].")

    if args.input and not args.input.exists():
        parser.error(f"File not found: {args.input}")

    if args.from_srt and not args.from_srt.exists():
        parser.error(f"SRT file not found: {args.from_srt}")

    _run_single(args)


if __name__ == "__main__":
    main()
