# Configuration

tlgrm is configured entirely through **environment variables** (and an optional `~/.tlgrm/config.toml`). Only the API credentials are required; everything else has sensible defaults.

## Environment variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TG_API_ID` | Yes | — | Your Telegram `api_id` from [my.telegram.org](https://my.telegram.org). Must be an integer. |
| `TG_API_HASH` | Yes | — | Your Telegram `api_hash` from my.telegram.org. |
| `TG_SESSION_PATH` | No | `~/.tlgrm/tg_session` | Base path for the Telethon session file (`.session` appended automatically). |
| `TG_DOWNLOADS_DIR` | No | `~/.tlgrm/downloads` | Directory where incoming media is saved by the webhook listener. |

If `TG_API_ID` or `TG_API_HASH` is missing, tlgrm prints setup instructions and exits with status `1`.

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

systemd **user** services do **not** inherit your interactive shell's exports (`~/.bashrc` / `~/.zshrc`). So `tlgrm daemon install` snapshots the relevant settings from the installing shell into an owner-only env file at `~/.tlgrm/daemon.env`, which the unit loads via `EnvironmentFile=`. The captured variables include your STT config (`TG_STT_MODEL`, `TG_STT_DEVICE`, `TG_STT_LANGUAGE`, …), any cloud STT keys (`OPENAI_API_KEY`, …), `HF_TOKEN`, and `LD_LIBRARY_PATH` (so a GPU build keeps working under the service).

Recommended flow — export everything you want first, then install:

```bash
export TG_STT_MODEL=large-v3-turbo
export OPENAI_API_KEY=...        # only if using a cloud STT backend
tlgrm daemon install --webhook-url https://example.com/webhook
```

To change a setting later, edit `~/.tlgrm/daemon.env` and restart the service:

```bash
systemctl --user restart tlgrm-daemon
```

### Running the daemon (or MCP server) and the CLI at the same time

The Telethon session is a **single-connection SQLite file**, so only **one** long-running process can hold it at a time. If the `tlgrm daemon`/`listen` listener or the `tlgrm-mcp` server is running and you also run a CLI command (e.g. `tlgrm send`) against the same account, you'll get a `database is locked` error.

Options:
- Stop the long-running consumer while you run one-off CLI commands, or
- Point the second consumer at a **separate session** with its own `TG_SESSION_PATH` (it will need its own `tlgrm login`).

## Files and directories

| Path | Created by | Contents |
|------|-----------|----------|
| `~/.tlgrm/` | tlgrm (on first run) | Application data root |
| `~/.tlgrm/tg_session.session` | `tlgrm login` | **Sensitive** — your authenticated session |
| `~/.tlgrm/downloads/` | webhook listener | Auto-downloaded incoming media |
| `~/.tlgrm/config.toml` | user (optional) | STT backend preferences |
| `~/.config/systemd/user/tlgrm-daemon.service` | `tlgrm daemon install` | systemd unit (written `0600`) |
| `~/.tlgrm/daemon.env` | `tlgrm daemon install` | env snapshot the service loads (owner-only `0600`) |

> **Security:** the session file grants full access to your Telegram account, and the systemd unit may embed webhook auth headers. Both are kept private. Never commit them to version control — the default `.gitignore` already excludes session files.

## Changing storage locations

Point tlgrm at custom locations, e.g. an encrypted volume:

```bash
export TG_SESSION_PATH=/secure/vault/tlgrm/session
export TG_DOWNLOADS_DIR=/secure/vault/tlgrm/media
```

Parent directories are created automatically if they do not exist.

---

## Speech-to-text backends

tlgrm supports pluggable STT backends. When the `stt` extra is installed, the webhook daemon transcribes incoming voice notes automatically, and the `tlgrm transcribe` command is available for standalone use (no login required).

### Selection precedence

1. `TG_STT_BACKEND` environment variable (highest priority)
2. `backend` key in `[stt]` section of `~/.tlgrm/config.toml`
3. Cloud API key auto-detect (first found wins, in order: openai, groq, deepgram, elevenlabs, google)
4. `faster-whisper` — the default

### Environment variables

| Variable | Description |
|----------|-------------|
| `TG_STT_BACKEND` | Force a backend: `faster-whisper`, `whisper`, `openai`, `groq`, `deepgram`, `elevenlabs`, `google` |
| `TG_STT_MODEL` | Override the model name/size used by the backend |
| `TG_STT_DEVICE` | faster-whisper device: `auto` (default), `cpu`, or `cuda` |
| `TG_STT_COMPUTE` | faster-whisper compute type (default: `int8` on CPU, `float16` on GPU) |
| `TG_STT_LANGUAGE` | Force a language for whisper-family backends (e.g. `ar`, `en`); use `en-US`-style codes for Google |
| `OPENAI_API_KEY` | API key for the OpenAI backend |
| `GROQ_API_KEY` | API key for the Groq backend |
| `DEEPGRAM_API_KEY` | API key for the Deepgram backend |
| `ELEVENLABS_API_KEY` | API key for the ElevenLabs backend |
| `GOOGLE_API_KEY` | API key for the Google Speech-to-Text backend |

### Backends and install commands

| Backend | Type | Install | Notes |
|---------|------|---------|-------|
| `faster-whisper` | Local | `pip install "tlgrm[stt]"` | **Default.** Fast, low RAM. Auto-downloads models. GPU-aware. |
| `whisper` | Local | `pip install "tlgrm[stt-whisper]"` | Original OpenAI Whisper. Auto-downloads models. |
| `openai` | Cloud | *(no extra needed)* | Requires `OPENAI_API_KEY`. Audio sent to OpenAI. |
| `groq` | Cloud | *(no extra needed)* | Requires `GROQ_API_KEY`. Audio sent to Groq. |
| `deepgram` | Cloud | *(no extra needed)* | Requires `DEEPGRAM_API_KEY`. Audio sent to Deepgram. |
| `elevenlabs` | Cloud | *(no extra needed)* | Requires `ELEVENLABS_API_KEY`. Audio sent to ElevenLabs. |
| `google` | Cloud | *(no extra needed)* | Requires `GOOGLE_API_KEY`. Audio sent to Google. |

All local backends require **FFmpeg** on your system path.

### Model guidance

The default model is **`tiny`** — it is fast but has lower accuracy, especially for non-English audio. For good **Arabic or multilingual** transcription accuracy, use a larger model:

```bash
export TG_STT_MODEL=large-v3-turbo   # good balance of speed and accuracy (recommended)
export TG_STT_MODEL=large-v3         # highest accuracy
```

Models are downloaded automatically on first use and cached locally (`~/.cache/huggingface/hub/`).

To force a language and avoid auto-detection overhead:

```bash
export TG_STT_LANGUAGE=ar   # Arabic
export TG_STT_LANGUAGE=en   # English
```

### GPU acceleration

With `TG_STT_DEVICE=auto` (the default), `faster-whisper` uses an NVIDIA GPU when one is available and falls back to CPU automatically. Using a GPU requires the CUDA 12 runtime and cuDNN:

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

Alternatively, a system CUDA toolkit (e.g. installed via your OS package manager) works too. Without the CUDA libraries, faster-whisper logs a warning and runs on CPU. To override device selection:

```bash
export TG_STT_DEVICE=cpu    # force CPU even if a GPU is present
export TG_STT_DEVICE=cuda   # force GPU (fails if no usable CUDA device)
export TG_STT_COMPUTE=float32   # override compute type (default: int8/float16)
```

The daemon pre-warms the STT model at startup so the first voice note transcribes without delay.

### Standalone transcription

`tlgrm transcribe` does not require a Telegram login:

```bash
# Use the default backend (faster-whisper, tiny model)
tlgrm transcribe --file voice.ogg

# Use a large model for Arabic
tlgrm transcribe --file voice.ogg --model large-v3-turbo

# Use a cloud backend
tlgrm transcribe --file voice.ogg --backend openai   # needs OPENAI_API_KEY

# Specify a backend and model together
tlgrm transcribe --file voice.ogg --backend faster-whisper --model large-v3-turbo
```

### Config file (`~/.tlgrm/config.toml`)

You can persist STT preferences without environment variables:

```toml
[stt]
backend = "faster-whisper"
model = "large-v3-turbo"
```

Environment variables override config file values.

> **Privacy note:** Cloud backends transmit voice audio to a third-party provider. Review your chosen provider's privacy policy before enabling cloud transcription.
