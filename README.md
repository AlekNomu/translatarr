# mkv2srt

> Generate French subtitles (`.srt`) from MKV files using **OpenAI Whisper** for transcription and **Google Translate** for translation — no API key required.

---

## Features

- **Smart pipeline** — detects existing English and French subtitles, chooses the best strategy automatically (resync, translate, or transcribe)
- **Auto-resync** — if a French `.srt` and an English `.srt` both exist with matching entry counts, aligns the French timestamps to the English ones (no translation needed)
- **Automatic translation** to French via `deep-translator` (free, no API key)
- **Smart subtitle handling** — multi-line subtitles are joined before translation for natural phrasing, dialogues (`-Speaker`) are translated independently then reassembled, HTML tags (`<i>`, `<font>`) are preserved, and SDH annotations (`[music]`, `(laughing)`, `♪…♪`) are skipped
- **Batch processing** — `--scan` processes an entire directory of MKV files recursively
- **SRT-only mode** — translate an existing `.srt` file while preserving all timings exactly
- **Sync checker** — runs by default; detects overlaps, negative durations, empty entries, and out-of-bounds subtitles
- **Auto language detection** — Whisper detects the audio language when no `.srt` is available
- **Configurable** — choose Whisper model size, force source language, and more

---

## Installation

```bash
# 1. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# 2. install as a CLI command
pip install -e .
```

---

## Usage

### Default workflow — MKV → French subtitles (default)

```bash
mkv2srt movie.mkv
# Output: movie.fr.srt
```

### Translate to another language

```bash
mkv2srt movie.mkv --target es
# Output: movie.es.srt
```

What happens under the hood:

1. **Looks for an existing French `.srt`** next to the MKV (`movie.fr.srt`, `movie.fre.srt`, `movie.french.srt`)
2. **Looks for an existing English `.srt`** next to the MKV (`movie.en.srt`, `movie.eng.srt`, `movie.english.srt`, `movie.srt`) or embedded in the MKV
3. **If both exist with the same number of entries** → applies English timestamps to the French text (resync, no translation needed)
4. **If both exist but entry counts differ** → translates the English `.srt` to French instead
5. **If only English exists** → translates it to French, keeping all timings intact
6. **If neither exists** → extracts audio, runs Whisper (medium model, auto language detection), translates to French
7. **If already aligned** → skips the file entirely (nothing to do)
8. **Sync check** runs automatically at the end

### Force source language (faster, skips auto-detection)

```bash
mkv2srt movie.mkv --language en
```

### Use a more accurate Whisper model

```bash
mkv2srt movie.mkv --model large
```

### Translate an existing English `.srt` (timings preserved)

```bash
mkv2srt --from-srt movie.en.srt -o movie.fr.srt
```

### Disable sync validation

```bash
mkv2srt movie.mkv --no-sync-check
```

### Process an entire directory

```bash
# Scan a directory recursively for all MKV files
mkv2srt --scan /mnt/my_series

# Scan the current directory
mkv2srt --scan
```

Each MKV is processed with the full smart pipeline (resync → translate → transcribe). Files are processed in parallel (4 workers by default, configurable with `--workers`). Whisper transcription is serialized (one at a time) to avoid GPU memory issues, while ffmpeg extraction and translation run concurrently. Files that fail are reported at the end without stopping the batch. Already-aligned files are skipped automatically.

### Custom output path

```bash
mkv2srt movie.mkv -o /subtitles/my_movie.fr.srt
```

---

## Options

| Flag | Default | Description |
|---|---|---|
| `INPUT.mkv` | — | Source video file |
| `-o / --output` | `<input>.<target>.srt` | Output `.srt` file path |
| `-t / --target` | `fr` | Target language code (`fr`, `es`, `de`, …) |
| `--model` | `medium` | Whisper model: `tiny`, `base`, `small`, `medium`, `large` |
| `--language` | auto | Audio language code (`en`, `de`, `es`, …) |
| `--from-srt FILE` | — | Translate an existing `.srt` (timings untouched) |
| `--no-sync-check` | off | Disable timing validation (on by default) |
| `--scan [DIR]` | — | Scan a directory recursively for MKV files (defaults to `.`) |
| `--workers N` | `4` | Number of parallel workers for `--scan` (Whisper stays serialized) |
| `--version` | — | Show version and exit |

---

## Whisper model comparison

| Model | Speed | Accuracy | RAM |
|---|---|---|---|
| `tiny` | ⚡⚡⚡⚡ | ★☆☆☆☆ | ~1 GB |
| `base` | ⚡⚡⚡ | ★★☆☆☆ | ~1 GB |
| `small` | ⚡⚡ | ★★★☆☆ | ~2 GB |
| `medium` | ⚡ | ★★★★☆ | ~5 GB |
| `large` | 🐢 | ★★★★★ | ~10 GB |

`medium` is the recommended default. Use `large` for professional results on longer or noisy content.

---

## How sync accuracy works

Whisper produces **millisecond-precise timestamps** from the audio waveform directly — there is no drift by design. The main causes of sync issues are:

1. **Silent intro / black screen** — if the video has a long silence before dialogue, Whisper may shift its internal clock. Passing `--language en` (or the correct language) avoids the silence-detection phase.
2. **Multiple audio tracks** — ffmpeg picks the first track by default. If your MKV has a commentary track listed first, the transcription will be wrong. Use ffprobe to inspect tracks if needed.
3. **Variable-frame-rate (VFR) video** — rare, but can cause drift over long files. Re-mux with ffmpeg first: `ffmpeg -i input.mkv -c copy -video_track_timescale 90000 fixed.mkv`.

The sync check runs by default and will catch any timing anomalies in the final `.srt`. Use `--no-sync-check` to disable it.

---

## Running the tests

```bash
pytest
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
