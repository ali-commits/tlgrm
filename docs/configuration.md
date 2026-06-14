# Configuration

tlgrm is configured entirely through **environment variables**. Only the API credentials are required; everything else has sensible defaults.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TG_API_ID` | ✅ Yes | — | Your Telegram `api_id` from [my.telegram.org](https://my.telegram.org). Must be an integer. |
| `TG_API_HASH` | ✅ Yes | — | Your Telegram `api_hash` from my.telegram.org. |
| `TG_SESSION_PATH` | No | `~/.tlgrm/tg_session` | Base path for the Telethon session file. Telethon appends `.session`. |
| `TG_DOWNLOADS_DIR` | No | `~/.tlgrm/downloads` | Directory where incoming media is saved by the webhook listener. |

If `TG_API_ID` or `TG_API_HASH` is missing (or `TG_API_ID` is not an integer), tlgrm prints setup instructions and exits with status `1` before doing anything else.

## Setting variables

### Temporarily (current shell only)

```bash
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here
```

### Permanently

Add the `export` lines to your shell profile:

- **bash:** `~/.bashrc`
- **zsh:** `~/.zshrc`
- **fish:** `set -Ux TG_API_ID 1234567`

### For the systemd daemon

The background daemon ([webhook guide](webhook-guide.md)) inherits the environment of the user session that runs it. If `tlgrm daemon install` runs in a shell where the variables are exported, the service will pick them up. To set them explicitly for the systemd user manager:

```bash
systemctl --user set-environment TG_API_ID=1234567 TG_API_HASH=your_api_hash_here
```

## Files and directories

| Path | Created by | Contents |
|------|-----------|----------|
| `~/.tlgrm/` | tlgrm (on first run) | Application data root |
| `~/.tlgrm/tg_session.session` | `tlgrm login` | **Sensitive** — your authenticated session |
| `~/.tlgrm/downloads/` | webhook listener | Auto-downloaded incoming media |
| `~/.config/systemd/user/tlgrm-daemon.service` | `tlgrm daemon install` | systemd unit (written `0600`) |

> 🔐 **Security:** the session file grants full access to your Telegram account, and the systemd unit may embed webhook auth headers. Both are kept private (the unit is written owner-only). Never commit them to version control — the default `.gitignore` already excludes session files.

## Changing storage locations

Point tlgrm at custom locations, e.g. an encrypted volume:

```bash
export TG_SESSION_PATH=/secure/vault/tlgrm/session
export TG_DOWNLOADS_DIR=/secure/vault/tlgrm/media
```

tlgrm creates the parent directories automatically if they don't exist.

---

## Speech-to-text backends

tlgrm supports pluggable STT backends selected via environment variables or a config file at `~/.tlgrm/config.toml`.

### Selection precedence

1. `TG_STT_BACKEND` environment variable (highest priority)
2. `backend` key in `[stt]` section of `~/.tlgrm/config.toml`
3. Cloud API key auto-detect (first found wins, in order: openai, groq, deepgram, elevenlabs, google)
4. `faster-whisper` — the default

### Environment variables

| Variable | Description |
|----------|-------------|
| `TG_STT_BACKEND` | Force a specific backend: `faster-whisper`, `whisper`, `whispercpp`, `vosk`, `openai`, `groq`, `deepgram`, `elevenlabs`, `google` |
| `TG_STT_MODEL` | Override the model name/size used by the selected backend |
| `TG_STT_LANGUAGE` | Language code for Google STT (default `en-US`) |
| `TG_STT_DEVICE` | faster-whisper device: `cpu` (default) or `cuda` for GPU |
| `TG_STT_COMPUTE` | faster-whisper compute type (default `int8` on CPU) |
| `OPENAI_API_KEY` | API key for the OpenAI backend |
| `GROQ_API_KEY` | API key for the Groq backend |
| `DEEPGRAM_API_KEY` | API key for the Deepgram backend |
| `ELEVENLABS_API_KEY` | API key for the ElevenLabs backend |
| `GOOGLE_API_KEY` | API key for the Google Speech-to-Text backend |
| `VOSK_MODEL_PATH` | Path to a downloaded Vosk model directory |

### Config file example (`~/.tlgrm/config.toml`)

```toml
[stt]
backend = "faster-whisper"   # or whisper, whispercpp, vosk, openai, groq, deepgram, elevenlabs, google
model = "base"
```

### Backends and install commands

| Backend | Type | Install command | Notes |
|---------|------|-----------------|-------|
| `faster-whisper` | Local | `pip install "tlgrm[stt]"` | **Default.** Fast, low RAM. Models auto-download on first use. |
| `whisper` | Local | `pip install "tlgrm[stt-whisper]"` | Original OpenAI Whisper. Models auto-download on first use. |
| `whispercpp` | Local | `pip install "tlgrm[stt-whispercpp]"` | whisper.cpp binding. Models auto-download on first use. |
| `vosk` | Local | `pip install "tlgrm[stt-vosk]"` | Offline, fast. Requires manual model download (see below). |
| `openai` | Cloud | *(no extra needed)* | Requires `OPENAI_API_KEY`. Sends audio to OpenAI. |
| `groq` | Cloud | *(no extra needed)* | Requires `GROQ_API_KEY`. Sends audio to Groq. |
| `deepgram` | Cloud | *(no extra needed)* | Requires `DEEPGRAM_API_KEY`. Sends audio to Deepgram. |
| `elevenlabs` | Cloud | *(no extra needed)* | Requires `ELEVENLABS_API_KEY`. Sends audio to ElevenLabs. |
| `google` | Cloud | *(no extra needed)* | Requires `GOOGLE_API_KEY`. Sends audio to Google. |

All local backends also require **FFmpeg** on your system path. `whispercpp` and `vosk` additionally require FFmpeg for audio decoding.

**Local models** (`faster-whisper`, `whisper`, `whispercpp`) auto-download on first use and cache locally. **Vosk** requires a manually downloaded model directory: download one from [https://alphacephei.com/vosk/models](https://alphacephei.com/vosk/models) and set `VOSK_MODEL_PATH` (or `TG_STT_MODEL`) to the extracted folder path.

> **Privacy caveat:** Cloud backends transmit private voice data to a third-party provider. Review your chosen cloud provider's terms before enabling cloud transcription.
