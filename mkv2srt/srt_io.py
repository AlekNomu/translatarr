"""
mkv2srt.srt_io
~~~~~~~~~~~~~~
Read and write ``.srt`` subtitle files.
"""

from __future__ import annotations

from __future__ import annotations

from pathlib import Path

from mkv2srt.models import SubtitleTrack


def read_srt(path: Path) -> SubtitleTrack:
    """
    Parse an SRT file and return a :class:`~mkv2srt.models.SubtitleTrack`.

    Handles UTF-8 files with or without BOM, and accepts both ``,`` and ``.``
    as the millisecond separator in timestamps.

    :param path: Path to the ``.srt`` file.
    :raises FileNotFoundError: If *path* does not exist.
    """
    raw = path.read_text(encoding="utf-8-sig")
    return SubtitleTrack.from_srt_text(raw)


def write_srt(track: SubtitleTrack, path: Path) -> None:
    """
    Write a :class:`~mkv2srt.models.SubtitleTrack` to an SRT file.

    The file is always written in UTF-8 (no BOM).

    :param track: Subtitle track to serialise.
    :param path:  Destination file path.
    """
    path.write_text(track.to_srt(), encoding="utf-8")
