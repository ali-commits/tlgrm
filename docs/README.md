# tlgrm Documentation

Welcome to the tlgrm documentation. tlgrm is an unofficial, feature-rich command-line client, MCP server, and webhook daemon for Telegram, built on Telethon.

> **Unofficial app notice:** tlgrm is not affiliated with, endorsed by, or sponsored by Telegram.

## Contents

| Guide | What it covers |
|-------|----------------|
| [Getting Started](getting-started.md) | Prerequisites, installation, API credentials, first login, first message, STT quick-start |
| [Configuration](configuration.md) | All environment variables, session/download paths, STT backends, GPU setup |
| [Command Reference](commands.md) | All 29 commands, flags, examples, JSON output shapes, and MCP tools |
| [Webhook & Daemon Guide](webhook-guide.md) | Real-time webhooks, the systemd daemon, payload schema, delivery behavior |

## Quick links

- Source & issues: <https://github.com/ali-commits/tlgrm>
- Contributing: [../CONTRIBUTING.md](../CONTRIBUTING.md)
- License: [MIT](../LICENSE)

## A 60-second tour

```bash
# Install (CLI + MCP server)
pip install "tlgrm[mcp]"

# Configure credentials (one-time, from my.telegram.org)
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here

# Authenticate (one-time, interactive)
tlgrm login

# Use it — every command prints clean JSON to stdout; logs go to stderr
tlgrm chats --limit 10
tlgrm chats | jq '.[].name'
tlgrm send --target @username --text "Hello!"
tlgrm react --target @username --message-id 137480 --emoji "👍"
```

New here? Start with **[Getting Started](getting-started.md)**.

## MCP server

tlgrm ships a stdio MCP server (`tlgrm-mcp`) that exposes 24 Telegram tools to AI assistants like Claude Desktop or Claude Code. It is **read-only by default**; write and destructive operations require explicit opt-in flags.

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

See the [Command Reference — MCP tools](commands.md#mcp-tools) section for the full tool list and permission tiers.

## Speech-to-text highlights

- **Local (multilingual):** `faster-whisper` (default) and `whisper` handle Arabic, English, and code-switching.
- **Default model is `tiny`** — fast but limited. Use `TG_STT_MODEL=large-v3-turbo` for Arabic or multilingual accuracy.
- **GPU:** faster-whisper auto-detects NVIDIA GPUs and falls back to CPU. Requires CUDA 12 runtime.
- **Cloud:** openai, groq, deepgram, elevenlabs, google — set the API key, no extra package needed.
- **Standalone:** `tlgrm transcribe --file voice.ogg` works without a Telegram login.

See [Configuration → Speech-to-text backends](configuration.md#speech-to-text-backends) for the full reference.
