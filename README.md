# mkv2srt

> Generate French subtitles (`.srt`) from MKV files using **OpenAI Whisper** for transcription and **Google Translate** for translation — no API key required.

---

## Features

- **Smart pipeline** — automatically detects an existing English `.srt` next to the MKV; if found, translates it directly (faster); otherwise runs full Whisper transcription
- **Automatic translation** to French via `deep-translator` (free, no API key)
- **SRT-only mode** — translate an existing `.srt` file while preserving all timings exactly
- **Sync checker** — runs by default; detects overlaps, negative durations, empty entries, and out-of-bounds subtitles
- **Auto language detection** — Whisper detects the audio language when no `.srt` is available
- **Configurable** — choose Whisper model size, force source language, skip translation, and more

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourname/mkv2srt.git
cd mkv2srt

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) install as a CLI command
pip install -e .
```

---

## Usage

### Default workflow — MKV → French subtitles

```bash
mkv2srt movie.mkv
# Output: movie.fr.srt
```

What happens under the hood:

1. **Looks for an existing `.srt`** next to the MKV (`movie.en.srt`, `movie.eng.srt`, `movie.english.srt`, or `movie.srt`)
2. **If found** → translates it to French, keeping all timings intact (fast, no Whisper needed)
3. **If not found** → extracts audio, runs Whisper (medium model, auto language detection), translates to French
4. **Sync check** runs automatically at the end

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

Each MKV is processed with the standard pipeline (existing SRT → translate, or Whisper → translate). Progress is displayed as `[1/N]`, `[2/N]`, etc. Files that fail are reported at the end without stopping the batch.

### Custom output path

```bash
mkv2srt movie.mkv -o /subtitles/my_movie.fr.srt
```

---

## Options

| Flag | Default | Description |
|---|---|---|
| `INPUT.mkv` | — | Source video file |
| `-o / --output` | `<input>.fr.srt` | Output `.srt` file path |
| `--model` | `medium` | Whisper model: `tiny`, `base`, `small`, `medium`, `large` |
| `--language` | auto | Audio language code (`en`, `de`, `es`, …) |
| `--from-srt FILE` | — | Translate an existing `.srt` (timings untouched) |
| `--no-sync-check` | off | Disable timing validation (on by default) |
| `--scan [DIR]` | — | Scan a directory recursively for MKV files (defaults to `.`) |
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
pip install pytest
pytest
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
