"""
mkv2srt.cli
~~~~~~~~~~~
Command-line interface for mkv2srt.

Entry point: ``python -m mkv2srt`` or the ``mkv2srt`` console script.
"""

from __future__ import annotations

import argparse
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from mkv2srt import __version__
from mkv2srt.pipeline import run_from_mkv, run_from_srt
from mkv2srt.transcriber import WHISPER_MODELS

_OUTPUT_SUFFIXES = (".srt", ".cc.srt", ".sdh.srt")
_DEFAULT_WORKERS = 4

logger = logging.getLogger("mkv2srt")

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
        "--workers",
        type=int,
        default=_DEFAULT_WORKERS,
        metavar="N",
        help=f"Number of parallel workers for --scan (default: {_DEFAULT_WORKERS}).",
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
# Progress callback
# ─────────────────────────────────────────────────────────────────────────────

def _log_progress(done: int, total: int) -> None:
    sys.stderr.write(f"\r  Translating… {done}/{total}   ")
    sys.stderr.flush()
    if done >= total:
        sys.stderr.write("\n")


# ─────────────────────────────────────────────────────────────────────────────
# Scan-mode logging (per-worker buffering)
# ─────────────────────────────────────────────────────────────────────────────

_output_lock = threading.Lock()


class _ScanHandler(logging.Handler):
    """Buffers log records per thread and flushes them atomically to stderr."""

    def __init__(self):
        super().__init__()
        self._local = threading.local()

    def emit(self, record):
        buf = getattr(self._local, "buffer", None)
        if buf is not None:
            buf.append(self.format(record))
        else:
            sys.stderr.write(self.format(record) + "\n")

    def start_capture(self):
        self._local.buffer = []

    def flush_capture(self):
        lines = getattr(self._local, "buffer", [])
        self._local.buffer = None
        if lines:
            with _output_lock:
                sys.stderr.write("\n".join(lines) + "\n")
                sys.stderr.flush()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def _run_single(args: argparse.Namespace) -> None:
    """Process a single file (MKV or --from-srt)."""
    output_path = _resolve_output(args)

    if args.from_srt:
        run_from_srt(
            args.from_srt, output_path,
            target_lang=args.target,
            mkv_path=args.input,
            sync_check=args.sync_check,
            on_progress=_log_progress,
        )
    else:
        if not run_from_mkv(
            args.input, output_path,
            target_lang=args.target,
            model=args.model,
            language=args.language,
            sync_check=args.sync_check,
            on_progress=_log_progress,
        ):
            return

    logger.info("→ %s", output_path)


def _run_scan(args: argparse.Namespace) -> int:
    """Scan a directory recursively for MKV files and process each one.

    Returns the number of failed files.
    """
    scan_dir = args.scan.resolve()
    if not scan_dir.is_dir():
        logger.error("Not a directory: %s", scan_dir)
        return 1

    mkv_files = sorted(scan_dir.rglob("*.mkv"))
    if not mkv_files:
        logger.info("No MKV files found in %s", scan_dir)
        return 0

    total = len(mkv_files)
    workers = min(args.workers, total)

    scan_handler = _ScanHandler()
    scan_handler.setFormatter(logging.Formatter("  %(message)s"))
    logger.handlers.clear()
    logger.addHandler(scan_handler)

    logger.info("Scanning %s — %d MKV file(s), %d worker(s)\n", scan_dir, total, workers)

    def _process(i: int, mkv: Path) -> tuple[Path, Exception | None]:
        scan_handler.start_capture()
        file_args = argparse.Namespace(**vars(args))
        file_args.input = mkv
        output_path = _resolve_output(file_args)
        logger.info("[%d/%d] %s", i, total, mkv.relative_to(scan_dir))
        try:
            if run_from_mkv(
                file_args.input, output_path,
                target_lang=file_args.target,
                model=file_args.model,
                language=file_args.language,
                sync_check=file_args.sync_check,
            ):
                logger.info("→ %s", output_path)
            return mkv, None
        except Exception as exc:
            logger.error("Error (%s): %s", mkv.name, exc)
            return mkv, exc
        finally:
            scan_handler.flush_capture()

    succeeded, failed = 0, 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_process, i, mkv)
            for i, mkv in enumerate(mkv_files, 1)
        ]
        for future in as_completed(futures):
            _, error = future.result()
            if error is None:
                succeeded += 1
            else:
                failed += 1

    logger.info("\nDone: %d succeeded, %d failed", succeeded, failed)
    return failed


def _setup_logging() -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("  %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def main(argv: list[str] | None = None) -> int:
    _setup_logging()

    parser = build_parser()
    args   = parser.parse_args(argv)

    if args.scan is not None:
        if args.output:
            parser.error("--output cannot be used with --scan.")
        if args.from_srt:
            parser.error("--from-srt cannot be used with --scan.")
        failed = _run_scan(args)
        return 1 if failed else 0

    if args.input is None and args.from_srt is None:
        parser.error("Provide an INPUT.mkv file, use --from-srt <file.srt>, or use --scan [DIR].")

    if args.input and not args.input.exists():
        parser.error(f"File not found: {args.input}")

    if args.from_srt and not args.from_srt.exists():
        parser.error(f"SRT file not found: {args.from_srt}")

    _run_single(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
