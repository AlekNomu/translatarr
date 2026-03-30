# Translatarr

> Automatic subtitle generation for your media library — transcription via **OpenAI Whisper**, translation via **Google Translate**, no API key required.

Translatarr is a self-hosted web application that scans your movie and TV series directories and shows you which subtitles are missing. Generation is always **on demand**, you decide when to trigger it, per episode, per season, or per series. Generated `.srt` files are written directly alongside your media files and picked up automatically by **Jellyfin** and **Plex**.

---

# Status

[![GitHub stars](https://img.shields.io/github/stars/aleknomu/translatarr?style=flat-square)](https://github.com/aleknomu/translatarr/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/aleknomu/translatarr?style=flat-square)](https://github.com/aleknomu/translatarr/issues)
[![CI](https://github.com/aleknomu/translatarr/actions/workflows/ci.yml/badge.svg)](https://github.com/aleknomu/translatarr/actions/workflows/ci.yml)
[![Docker Pulls](https://img.shields.io/docker/pulls/aleknomu/translatarr?style=flat-square)](https://hub.docker.com/r/aleknomu/translatarr)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

---

# Support

- Report bugs and request features on [GitHub Issues](https://github.com/aleknomu/translatarr/issues)

---

## Major Features Include

- **Smart pipeline**: detects existing English and target-language subtitles and picks the best strategy automatically: resync, translate, or transcribe from audio
- **Auto-resync**: if a translated `.srt` and a source `.srt` both exist with matching entry counts, Translatarr realigns the translated timestamps without re-translating anything
- **Automatic translation** via `deep-translator` (free Google Translate, no API key required)
- **Smart subtitle handling**: multi-line entries joined before translation, dialogue lines (`- Speaker`) translated independently and reassembled, HTML tags (`<i>`, `<font>`) preserved, SDH annotations (`[music]`, `(laughing)`, `♪…♪`) skipped
- **Whisper transcription**: when no source subtitle exists, extracts audio with ffmpeg and transcribes with Whisper (auto language detection)
- **Sync validator**: detects overlaps, negative durations, empty entries, and out-of-bounds subtitles after generation
- **Configurable**: choose Whisper model size, source language, target language, sync check on/off
- **Web UI**: manage movies and TV series, trigger generation per episode / season / series, view history and live logs
- **Task queue**: subtitle generation runs in the background with progress tracking and cancellation support
- **Scheduled scans**: periodic library scan to pick up newly added media automatically
- **Delete subtitles**: remove a generated subtitle at any level (episode, season, full series, movie) and reset the database entry

---

## Screenshot



---

## Getting Started

### Docker Run

```bash
docker run -d \
  --name translatarr \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Europe/Paris \
  -p 6868:6868 \
  -v /path/to/config:/config \
  -v /path/to/movies:/movies \
  -v /path/to/tv:/tv \
  --restart unless-stopped \
  aleknomu/translatarr:latest
```

The web interface is then available at `http://your-server-ip:6868`.

> **Port note:** Translatarr listens internally on **6868**.

---

### Docker Compose

```yaml
services:
  translatarr:
    image: aleknomu/translatarr:latest
    container_name: translatarr
    environment:
      - PUID=1000
      - PGID=1000
      - TZ=Europe/Paris
    volumes:
      - ./config:/config
      - /path/to/movies:/movies
      - /path/to/tv:/tv
    ports:
      - "6868:6868"
    restart: unless-stopped
```

### Manual installation

```bash
# Requires Python 3.10+ and ffmpeg installed
git clone https://github.com/aleknomu/translatarr.git
cd translatarr
uv sync          # or: pip install -e .

translatarr      # starts on http://localhost:6868
```

Options:

```bash
translatarr --port 6868 --host 0.0.0.0 --config-dir /data/config
```

---

## Configuration

After starting, open the web UI and go to **Settings → General**:

| Setting | Description | Default |
|---|---|---|
| Movies path | Directory containing your movie `.mkv` files | `/movies` |
| Series path | Directory containing your TV series `.mkv` files | `/tv` |
| Target language | Subtitle output language (ISO 639-1 code) | `fr` |
| Whisper model | Transcription model size (see table below) | `medium` |
| Source language | Force audio language, skip auto-detection | auto |
| Sync check | Validate subtitle timing after generation | enabled |

### Whisper model comparison

| Model | Speed | Accuracy | VRAM |
|---|---|---|---|
| `tiny`   | ⚡⚡⚡⚡ | ★☆☆☆☆ | ~1 GB |
| `base`   | ⚡⚡⚡  | ★★☆☆☆ | ~1 GB |
| `small`  | ⚡⚡   | ★★★☆☆ | ~2 GB |
| `medium` | ⚡    | ★★★★☆ | ~5 GB |
| `large`  | 🐢   | ★★★★★ | ~10 GB |

`medium` is the recommended default. Use `large` for professional results on noisy or multi-speaker content.

---

## How it works

When Translatarr processes an MKV file, it follows this priority order:

1. **Looks for existing target-language `.srt`** (e.g. `.fr.srt`, `.fre.srt`, `.french.srt`)
2. **Looks for existing source-language `.srt`** (e.g. `.en.srt`, `.eng.srt`, `.srt`) or embedded subtitle track in the MKV
3. **Both exist, same entry count, already aligned** → skip (nothing to do)
4. **Both exist, same entry count, different timestamps** → resync: apply source timestamps to translated text (no translation)
5. **Both exist but different entry counts** → translate source to target language
6. **Only source exists** → translate to target language, preserve all timings
7. **Neither exists** → extract audio with ffmpeg → transcribe with Whisper → translate to target language

---

## License

MIT — see [LICENSE](LICENSE) for details.
