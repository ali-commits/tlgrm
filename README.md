<div align="center">

# tlgrm

**An unofficial, feature-rich command-line client, MCP server, and webhook daemon for Telegram, built on [Telethon](https://github.com/LonamiWebs/Telethon).**

Drive your *personal* Telegram account from the terminal — list chats, send and edit messages, pull history, download media, react, pin, schedule, run polls — and bridge incoming messages to an HTTP webhook in real time. Also ships as an **MCP server** so AI assistants like Claude can drive Telegram on your behalf.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Status: unofficial](https://img.shields.io/badge/Telegram-unofficial%20client-lightgrey.svg)](https://github.com/ali-commits/tlgrm)

</div>

> **Unofficial app notice:** tlgrm is an independent, unofficial client built on the Telegram API (via Telethon). It is **not affiliated with, endorsed by, or sponsored by Telegram**.

---

## Table of Contents

- [Features](#features)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Telegram API credentials](#telegram-api-credentials)
- [Quick start](#quick-start)
- [Commands](#commands)
- [MCP server](#mcp-server)
- [Claude Code skill](#claude-code-skill)
- [Configuration](#configuration)
- [Webhooks & background daemon](#webhooks--background-daemon)
- [Speech-to-text (optional)](#speech-to-text-optional)
- [Output format](#output-format)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)
- [Disclaimer](#disclaimer)

## Features

- 🔐 **Personal account access** — acts as *you* (user account, MTProto), not a bot, so it can read history and list members.
- 💬 **Messaging** — send text, files, media, and voice notes; reply, edit, forward, react, pin, mute, save to Saved Messages.
- 📜 **History & members** — fetch recent messages or participant lists from any chat.
- 📁 **Chats** — list your recent dialogs with unread counts and types.
- 🛠️ **Group management** — create groups/channels, add/remove members, leave chats.
- 📅 **Scheduled messages & polls** — schedule a text message at a future time, or send a poll/quiz.
- 🤖 **MCP server** — expose ~24 Telegram tools to any MCP-compatible AI assistant (Claude Desktop, Claude Code, etc.) with tiered read/write/destructive permissions.
- 🔔 **Real-time webhooks** — forward every incoming message to an HTTP endpoint as JSON, with automatic media download. Self-destructing (TTL) media is skipped; the webhook payload includes `media.self_destruct: true`.
- ⚙️ **Background daemon** — run the listener as a managed `systemd` user service.
- 🗣️ **Optional speech-to-text** — auto-transcribe incoming voice notes locally with Whisper.
- 🖥️ **~30 commands** — every command prints structured JSON to stdout, making tlgrm easy to pipe into `jq` or other tools.

## How it works

tlgrm uses the **Telegram client API (MTProto)** through Telethon, authenticating as your personal account with a login code (and 2FA if enabled). Your authenticated session is stored locally and reused, so you only log in once.

> Because it acts as your user account, tlgrm can do things the [Bot API](https://core.telegram.org/bots/api) cannot (read arbitrary history, list group members, send as yourself). This is also why it requires your own `api_id`/`api_hash` — see [below](#telegram-api-credentials).

## Installation

**Requirements:** Python ≥ 3.10. [FFmpeg](https://ffmpeg.org/) is only needed for optional speech-to-text.

### From PyPI

```bash
# CLI only
pip install tlgrm

# CLI + MCP server
pip install "tlgrm[mcp]"

# CLI + Whisper speech-to-text
pip install "tlgrm[stt]"

# Everything
pip install "tlgrm[all]"
```

### With `uv` (recommended)

```bash
# CLI only
uv tool install tlgrm

# CLI + MCP server
uv tool install "tlgrm[mcp]"
```

### From source (development)

```bash
git clone https://github.com/ali-commits/tlgrm.git
cd tlgrm
pip install -e .
```

To enable optional voice-note transcription, install the `stt` extra (see [Speech-to-text](#speech-to-text-optional)):

```bash
pip install "tlgrm[stt]"     # or:  uv tool install "tlgrm[stt]"
```

## Telegram API credentials

tlgrm does **not** ship with Telegram API credentials — you must supply your own. This protects you from a single shared `api_id` being rate-limited for everyone.

1. Go to **[my.telegram.org](https://my.telegram.org)** → **API development tools**.
2. Create an application (Platform: *Desktop*). We suggest a name like `tlgrm` — the title must not contain the word "Telegram".
3. Copy the `api_id` (a number) and `api_hash` (a hex string).
4. Export them before running tlgrm:

```bash
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here
```

> Add these to your `~/.bashrc` / `~/.zshrc` to persist them across sessions. See [docs/configuration.md](docs/configuration.md) for all options.

## Quick start

```bash
# 1. Authenticate once (interactive: phone → code → 2FA)
tlgrm login

# 2. List your recent chats
tlgrm chats --limit 10

# 3. Send a message (target = @username, numeric chat ID, or phone)
tlgrm send --target @username --text "Hello from the terminal!"

# 4. Read the last 5 messages of a chat
tlgrm history --target @username --limit 5
```

## Commands

> **`--target`** accepts a `@username`, a numeric chat ID, or a phone number. A purely numeric value is treated as a chat ID.

### Read

| Command | Description |
|---------|-------------|
| `tlgrm login` | Interactively authenticate your Telegram account |
| `tlgrm whoami` | Show the logged-in account |
| `tlgrm chats [--limit N]` | List recent chats/dialogs (default 20) |
| `tlgrm history --target T [--limit N] [--offset-id ID]` | Fetch message history (default 10) |
| `tlgrm search --query Q [--target T] [--limit N]` | Search messages globally or within a chat |
| `tlgrm members --target T` | List members/participants of a group or channel |
| `tlgrm user-info --target T` | Show profile info for a user |
| `tlgrm chat-info --target T` | Show info about a chat/channel |
| `tlgrm download --target T --message-id ID [--output PATH]` | Download media from a message |

### Write

| Command | Description |
|---------|-------------|
| `tlgrm send --target T (--text … \| --file … [--voice]) [--caption …] [--reply-to ID] [--silent]` | Send a message, file, media, or voice note |
| `tlgrm reply --target T --message-id ID (--text … \| --file …) [--caption …] [--voice] [--silent]` | Reply to a specific message |
| `tlgrm edit --target T --message-id ID --text …` | Edit a sent message |
| `tlgrm read --target T [--max-id ID]` | Mark a chat (or up to a message ID) as read |
| `tlgrm forward --from A --to B --message-ids ID …` | Forward one or more messages between chats |
| `tlgrm react --target T --message-id ID --emoji E [--big]` | React to a message with an emoji |
| `tlgrm pin --target T --message-id ID [--notify]` | Pin a message in a chat |
| `tlgrm unpin --target T [--message-id ID]` | Unpin a message (or all if `--message-id` omitted) |
| `tlgrm mute --target T [--duration SECONDS]` | Mute a chat (default: forever) |
| `tlgrm unmute --target T` | Unmute a chat |
| `tlgrm saved (--text … \| --file …) [--caption …] [--voice]` | Send a message to your Saved Messages |

### Tier 3 — Group management & advanced

| Command | Description |
|---------|-------------|
| `tlgrm create-group --title TITLE [--members …] [--channel]` | Create a group or broadcast channel |
| `tlgrm add-members --target T --members …` | Add members to a group/channel |
| `tlgrm remove-members --target T --members …` | Remove members from a group/channel |
| `tlgrm leave --target T` | Leave a group or channel |
| `tlgrm schedule --target T --text TEXT --at (SECONDS\|ISO8601)` | Schedule a text message |
| `tlgrm poll --target T --question Q --option A --option B … [--multiple] [--quiz --correct N]` | Send a poll or quiz |

### Daemon & listener

| Command | Description |
|---------|-------------|
| `tlgrm listen [--webhook-url URL] [--webhook-header "N: V"] [--verbose]` | Listen for new messages (foreground) |
| `tlgrm daemon install\|uninstall\|status\|logs` | Manage the background `systemd` daemon |
| `tlgrm delete --target T --message-ids ID …` | Delete one or more messages |

📖 Full reference with every flag, examples, and output shapes: **[docs/commands.md](docs/commands.md)**.

## MCP server

tlgrm ships a **stdio MCP server** (`tlgrm-mcp`) that exposes Telegram operations as tools to any MCP-compatible AI assistant.

### Installation

```bash
pip install "tlgrm[mcp]"
```

The MCP server requires a prior `tlgrm login` — it reuses the same session file as the CLI.

### Claude Desktop configuration

Add this to your Claude Desktop `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tlgrm": {
      "command": "uvx",
      "args": ["--from", "tlgrm[mcp]", "tlgrm-mcp"],
      "env": {
        "TG_API_ID": "...",
        "TG_API_HASH": "..."
      }
    }
  }
}
```

### Permission tiers

The MCP server is **read-only by default**. Write and destructive operations must be explicitly enabled at startup:

| Tier | Flag | Tools exposed |
|------|------|---------------|
| **Read-only** (default) | *(none)* | `whoami`, `list_chats`, `search_messages`, `get_history`, `get_members`, `user_info`, `chat_info`, `download_media` (8 tools) |
| **Write** | `--allow-write` | Adds: `send_message`, `edit_message`, `mark_read`, `react`, `forward_messages`, `pin`, `unpin`, `mute`, `unmute`, `create_group`, `add_members`, `schedule_message`, `send_poll` (13 more) |
| **Destructive** | `--allow-write --allow-destructive` | Adds: `delete_messages`, `leave_chat`, `remove_members` (3 more) |

To enable write access in Claude Desktop, pass the flags via `args`:

```json
"args": ["--from", "tlgrm[mcp]", "tlgrm-mcp", "--allow-write"]
```

> **Safety note:** The read-only default ensures an AI assistant can never send or delete messages unless you have explicitly opted in. Always review what permissions you grant.

## Claude Code skill

A Claude Code skill lives at `skills/tlgrm/` in this repository. It teaches Claude Code how to drive tlgrm — both via the CLI and the MCP server — and includes a capability map, safety rules, and workflow recipes.

### Installation

```bash
cp -r skills/tlgrm ~/.claude/skills/
```

Once installed, Claude Code will automatically use it when you ask things like "check my Telegram", "send a message to @someone", or "summarize my unread chats".

## Configuration

All configuration is via environment variables. None are required except the API credentials.

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `TG_API_ID` | ✅ | — | Your Telegram `api_id` |
| `TG_API_HASH` | ✅ | — | Your Telegram `api_hash` |
| `TG_SESSION_PATH` | ❌ | `~/.tlgrm/tg_session` | Where the login session is stored |
| `TG_DOWNLOADS_DIR` | ❌ | `~/.tlgrm/downloads` | Where incoming media is downloaded |
| `TG_STT_BACKEND` | ❌ | `faster-whisper` | STT backend (`faster-whisper`, `whisper`, `openai`, `groq`, …) |
| `TG_STT_MODEL` | ❌ | *(backend default)* | Model name/size for the selected STT backend |

See **[docs/configuration.md](docs/configuration.md)** for the full reference including all STT backend options.

## Webhooks & background daemon

tlgrm can forward every incoming message to an HTTP endpoint as JSON, downloading any attached media automatically:

```bash
tlgrm listen --webhook-url https://your-server.com/webhook \
             --webhook-header "Authorization: Bearer YOUR_TOKEN"
```

To run it persistently as a `systemd` user service:

```bash
tlgrm daemon install --webhook-url https://your-server.com/webhook
tlgrm daemon status
tlgrm daemon logs
tlgrm daemon uninstall
```

> **Note:** self-destructing (TTL) media is **not** downloaded — the webhook payload includes `"media.self_destruct": true` but the file is skipped.

📖 Full guide, payload schema, and security notes: **[docs/webhook-guide.md](docs/webhook-guide.md)**.

## Speech-to-text (optional)

When the `stt` extra is installed, the webhook daemon automatically transcribes incoming **voice notes and audio**, populating `media.transcription` in the webhook payload. You can also transcribe any audio file directly with **`tlgrm transcribe`** (no login required). tlgrm supports **pluggable STT backends**: local models and cloud APIs.

**Default:** `faster-whisper` (local, lightweight, auto-downloads the model on first use; CPU by default, set `TG_STT_DEVICE=cuda` for GPU).

```bash
tlgrm transcribe --file voice.ogg                       # default backend
tlgrm transcribe --file voice.ogg --backend faster-whisper
```

```bash
# Local faster-whisper (default — recommended)
pip install "tlgrm[stt]"     # requires FFmpeg on your system

# Original OpenAI Whisper
pip install "tlgrm[stt-whisper]"

# Cloud backends — just set an API key (no extra package needed)
export OPENAI_API_KEY=sk-...   # uses openai backend automatically
export GROQ_API_KEY=gsk_...    # uses groq backend automatically
```

If no STT backend is available, transcription is silently skipped — all other features work unchanged.

See **[docs/configuration.md](docs/configuration.md#speech-to-text-backends)** for the full list of backends, selection precedence, config file format, and privacy considerations for cloud backends.

## Output format

Every command prints **pretty-printed JSON** to stdout (non-ASCII preserved), making tlgrm easy to pipe into `jq` or other tools:

```bash
tlgrm chats --limit 3 | jq '.[].name'
```

Errors are reported as `{"success": false, "error": "..."}` with a non-zero exit code on authentication failure.

## Security

- Your **session file** (`~/.tlgrm/tg_session.session`) grants full access to your Telegram account. Keep it private; it is git-ignored by default.
- The systemd unit file is written with owner-only permissions (`0600`) because it may embed webhook auth headers.
- Enable **Two-Step Verification** on your Telegram account.
- Found a vulnerability? See [CONTRIBUTING.md](CONTRIBUTING.md#reporting-security-issues).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Telegram API credentials are not configured` | Export `TG_API_ID` and `TG_API_HASH` ([credentials](#telegram-api-credentials)) |
| `Not authorized. Run 'tlgrm login' first.` | Run `tlgrm login` to create a session |
| Transcription never appears | Install the `stt` extra **and** FFmpeg |
| `systemctl not found` | The daemon needs `systemd`; use `tlgrm listen` directly otherwise |
| Cannot create an app at my.telegram.org | Brand-new accounts are often blocked; wait, retry in incognito with no extensions |
| MCP tool not available | Check the permission tier — write/destructive tools need `--allow-write` / `--allow-destructive` |

## Documentation

- [Getting Started](docs/getting-started.md) — install, log in, send your first message
- [Configuration](docs/configuration.md) — environment variables and paths
- [Command Reference](docs/commands.md) — every command, flag, and output shape
- [Webhook & Daemon Guide](docs/webhook-guide.md) — webhooks, systemd, payload schema

## Contributing

Contributions are welcome! Please read **[CONTRIBUTING.md](CONTRIBUTING.md)** for development setup, coding conventions, and how to report issues.

## License

Released under the [MIT License](LICENSE) © 2026 Ali Alrabeei.

## Disclaimer

tlgrm is an unofficial client and is not affiliated with, endorsed by, or sponsored by Telegram. Use at your own risk.
