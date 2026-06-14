# tlgrm Documentation

Welcome to the tlgrm documentation. tlgrm is an unofficial, feature-rich command-line client, MCP server, and webhook daemon for Telegram, built on Telethon.

> **Unofficial app notice:** tlgrm is not affiliated with, endorsed by, or sponsored by Telegram.

## Contents

| Guide | What it covers |
|-------|----------------|
| [Getting Started](getting-started.md) | Prerequisites, installation, API credentials, first login, first message |
| [Configuration](configuration.md) | Environment variables, session and download paths |
| [Command Reference](commands.md) | Every command (~30 total), all flags, examples, and JSON output shapes; includes the MCP tools section |
| [Webhook & Daemon Guide](webhook-guide.md) | Real-time webhooks, the systemd daemon, and the payload schema |

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

# Use it
tlgrm chats --limit 10
tlgrm send --target @username --text "Hello!"
tlgrm react --target @username --message-id 137480 --emoji "👍"
```

New here? Start with **[Getting Started](getting-started.md)**.

## MCP server

tlgrm ships a stdio MCP server (`tlgrm-mcp`) that exposes ~24 Telegram tools to AI assistants like Claude Desktop or Claude Code. It is **read-only by default**; write and destructive operations require explicit opt-in flags. See the [Command Reference — MCP tools](commands.md#mcp-tools) section and [../README.md#mcp-server](../README.md#mcp-server) for the Claude Desktop configuration.
