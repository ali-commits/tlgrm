<div align="center">

# tlgrm

**An unofficial, feature-rich command-line client, MCP server, and webhook daemon for Telegram, built on [Telethon](https://github.com/LonamiWebs/Telethon).**

Drive your *personal* Telegram account from the terminal — send messages, pull history, download media, react, pin, schedule, run polls — and bridge incoming messages to an HTTP webhook in real time. Also ships as an **MCP server** so AI assistants like Claude can drive Telegram on your behalf.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: unofficial](https://img.shields.io/badge/Telegram-unofficial%20client-lightgrey.svg)](https://github.com/ali-commits/tlgrm)

</div>

> **Unofficial app notice:** tlgrm is an independent, unofficial client built on the Telegram API (via Telethon). It is **not affiliated with, endorsed by, or sponsored by Telegram**.

---

## Quick start

```bash
# 1. Get your API credentials from my.telegram.org → API development tools
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here

# 2. Install
pip install tlgrm          # CLI only
pip install "tlgrm[mcp]"   # + MCP server
pip install "tlgrm[stt]"   # + speech-to-text (faster-whisper)
pip install "tlgrm[all]"   # everything

# 3. Log in once
tlgrm login

# 4. Go
tlgrm chats --limit 10
tlgrm send --target @username --text "Hello!"
tlgrm chats | jq '.[].name'   # stdout is clean JSON; logs go to stderr
```

With [`uv`](https://docs.astral.sh/uv/): `uv tool install "tlgrm[mcp]"`.

---

## Telegram API credentials

tlgrm does **not** ship with API credentials — you must supply your own:

1. Go to **[my.telegram.org](https://my.telegram.org)** → **API development tools**.
2. Create an application (Platform: *Desktop*). The title must not contain the word "Telegram".
3. Copy the `api_id` (a number) and `api_hash` (a hex string).
4. Export them (add to your shell profile to persist):

```bash
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here
```

See [docs/configuration.md](docs/configuration.md) for all configuration options.

---

## Commands (29)

Every command prints **clean JSON to stdout** — logs and progress go to **stderr**, so piping into `jq` works reliably.

### Account & read

| Command | Description |
|---------|-------------|
| `tlgrm login` | Authenticate your Telegram account (interactive, one-time) |
| `tlgrm whoami` | Show the logged-in account |
| `tlgrm chats [--limit N]` | List recent chats/dialogs |
| `tlgrm history --target T [--limit N] [--offset-id ID]` | Fetch message history |
| `tlgrm search --query Q [--target T] [--limit N]` | Search messages globally or in a chat |
| `tlgrm members --target T` | List members of a group or channel |
| `tlgrm user-info --target T` | Show profile info for a user |
| `tlgrm chat-info --target T` | Show info about a chat/channel |
| `tlgrm download --target T --message-id ID [--output PATH]` | Download media from a message |

### Write

| Command | Description |
|---------|-------------|
| `tlgrm send --target T (--text … \| --file …) [--caption …] [--voice] [--reply-to ID] [--silent]` | Send a message, file, media, or voice note |
| `tlgrm reply --target T --message-id ID (--text … \| --file …) [--caption …] [--voice] [--silent]` | Reply to a specific message |
| `tlgrm edit --target T --message-id ID --text …` | Edit a sent message |
| `tlgrm read --target T [--max-id ID]` | Mark a chat as read |
| `tlgrm forward --from A --to B --message-ids ID …` | Forward messages between chats |
| `tlgrm react --target T --message-id ID --emoji E [--big]` | React to a message |
| `tlgrm pin --target T --message-id ID [--notify]` | Pin a message |
| `tlgrm unpin --target T [--message-id ID]` | Unpin a message (or all) |
| `tlgrm mute --target T [--duration SECONDS]` | Mute a chat |
| `tlgrm unmute --target T` | Unmute a chat |
| `tlgrm saved (--text … \| --file …) [--caption …] [--voice]` | Send to Saved Messages |

### Groups, scheduling & advanced

| Command | Description |
|---------|-------------|
| `tlgrm create-group --title TITLE [--members …] [--channel]` | Create a group or channel |
| `tlgrm add-members --target T --members …` | Add members to a group/channel |
| `tlgrm remove-members --target T --members …` | Remove members from a group/channel |
| `tlgrm leave --target T` | Leave a group or channel |
| `tlgrm schedule --target T --text TEXT --at (SECONDS\|ISO8601)` | Schedule a text message |
| `tlgrm poll --target T --question Q --option A --option B … [--quiz --correct N]` | Send a poll or quiz |
| `tlgrm transcribe --file PATH [--backend …] [--model …]` | Transcribe audio (no login required) |

### Webhook daemon

| Command | Description |
|---------|-------------|
| `tlgrm listen [--webhook-url URL] [--webhook-header "N: V"] [--verbose]` | Listen for incoming messages (foreground) |
| `tlgrm daemon install\|uninstall\|status\|logs` | Manage the background systemd daemon |

Full reference with all flags, output shapes, and examples: **[docs/commands.md](docs/commands.md)**.

---

## MCP server

tlgrm ships a **stdio MCP server** (`tlgrm-mcp`). It is **read-only by default**; add `--allow-write` for write tools and `--allow-write --allow-destructive` for delete/leave/remove.

```json
{
  "mcpServers": {
    "tlgrm": {
      "command": "uvx",
      "args": ["--from", "tlgrm[mcp]", "tlgrm-mcp"],
      "env": { "TG_API_ID": "...", "TG_API_HASH": "..." }
    }
  }
}
```

Requires a prior `tlgrm login`. The MCP server reuses the same session file as the CLI.

---

## Speech-to-text (optional)

Install the `stt` extra to auto-transcribe incoming voice notes in the webhook daemon, or to run `tlgrm transcribe` standalone (no login needed).

```bash
pip install "tlgrm[stt]"         # faster-whisper (default, recommended)
pip install "tlgrm[stt-whisper]" # original openai-whisper
pip install "tlgrm[stt-all]"     # all local backends
```

Cloud backends (openai, groq, deepgram, elevenlabs, google) need no extra package — just set the API key:

```bash
export OPENAI_API_KEY=sk-...   # auto-selects openai backend
```

**Model tip:** the default model is `tiny` (fast, lower accuracy). For good **Arabic / multilingual** accuracy, use a larger model:

```bash
export TG_STT_MODEL=large-v3-turbo   # recommended for Arabic
```

**GPU:** faster-whisper auto-detects NVIDIA GPUs (`TG_STT_DEVICE=auto`). CUDA 12 runtime required: `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`. Full backend reference: **[docs/configuration.md](docs/configuration.md#speech-to-text-backends)**.

---

## Security

- Your **session file** (`~/.tlgrm/tg_session.session`) grants full account access — keep it private (git-ignored by default).
- Enable **Two-Step Verification** on your Telegram account.
- The systemd unit file is written owner-only (`0600`).

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Telegram API credentials are not configured` | Export `TG_API_ID` and `TG_API_HASH` (see [above](#telegram-api-credentials)) |
| `Not authorized. Run 'tlgrm login' first.` | Run `tlgrm login` |
| Transcription never appears | Install the `stt` extra **and** FFmpeg |
| `systemctl not found` | The daemon needs systemd; use `tlgrm listen` directly |
| Cannot create an app at my.telegram.org | Brand-new accounts are sometimes blocked; wait and retry |
| MCP tool not available | Check the permission tier — write/destructive tools need explicit flags |

---

## Documentation

| Guide | What it covers |
|-------|----------------|
| [Getting Started](docs/getting-started.md) | Install, credentials, login, first message |
| [Configuration](docs/configuration.md) | All env vars, paths, STT backends |
| [Command Reference](docs/commands.md) | Every command, flag, output shape |
| [Webhook & Daemon Guide](docs/webhook-guide.md) | Webhooks, systemd, payload schema |

---

## Contributing & License

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md). Released under the [MIT License](LICENSE) © 2026 Ali Alrabeei. tlgrm is unofficial and not affiliated with, endorsed by, or sponsored by Telegram.
