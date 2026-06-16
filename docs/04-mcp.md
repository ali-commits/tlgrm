# MCP server (`tlgrm-mcp`)

tlgrm ships a **stdio MCP server** that exposes your Telegram account to AI
assistants (Claude Desktop/Code, and any MCP-compatible client) as tools.

It is a **thin bridge** to the tlgrm [background server](03-configuration.md#background-server): every tool call routes through the one connection the server owns (which enforces the permission tier and the [write guard](03-configuration.md#write-guard-who-an-account-may-message)), and it **auto-spawns** a server if none is running. That means the MCP server, the webhook listener, and your CLI can all use the same account at once — no `database is locked`.

## Install & log in

```bash
uv tool install "tlgrm[mcp]"     # or: pip install "tlgrm[mcp]"
tlgrm login                      # the MCP server uses your logged-in account(s)
```

## Client configuration

Add it to your MCP client (here, the common `mcpServers` JSON shape). Using
`uvx` it needs no separate install:

```json
{
  "mcpServers": {
    "tlgrm": {
      "command": "uvx",
      "args": ["--from", "tlgrm[mcp]", "tlgrm-mcp", "--allow-write"],
      "env": { "TG_API_ID": "...", "TG_API_HASH": "..." }
    }
  }
}
```

### Flags

| Flag | Effect |
|------|--------|
| *(none)* | **Read-only** — only the read tools are exposed (default, safest). |
| `--allow-write` | Adds write tools (send, edit, react, forward, pin, mute, schedule, …). |
| `--allow-destructive` | With `--allow-write`, also adds delete / leave / remove-members. |
| `--account NAME` | Act as a specific [account](03-configuration.md#accounts-multi-login). Omit to use the server's default account. |

`--session` is accepted but **ignored** (the bridge delegates to the server).

## Permission tiers

Tiers are enforced **server-side**, not just by which tools are advertised — so
even a misbehaving client can't exceed the tier you granted.

- **Read** (always on): `whoami`, `list_chats`, `search_messages`, `get_history`, `get_members`, `user_info`, `chat_info`, `download_media`
- **Write** (`--allow-write`): `send_message`, `edit_message`, `mark_read`, `react`, `forward_messages`, `pin`, `unpin`, `mute`, `unmute`, `create_group`, `add_members`, `schedule_message`, `send_poll`
- **Destructive** (`--allow-write --allow-destructive`): `delete_messages`, `leave_chat`, `remove_members`

The [write guard](03-configuration.md#write-guard-who-an-account-may-message) applies on top of the tier: even with `--allow-write`, the AI can only message contacts your `filter write` rules permit.

## How it runs

1. On startup the bridge checks for a running tlgrm server and **auto-spawns one** if needed.
2. Each tool call is forwarded to the server, which runs it against the account's hot connection and returns the result.
3. Downloaded media goes to the **server-controlled** downloads directory (not a caller-specified path), so the AI can't write files to arbitrary locations.

## Recommended setup

For an always-available assistant, run the server as a service and point the MCP
client at it:

```bash
tlgrm account add personal      # log in the account the assistant should use
tlgrm server install            # run the server on boot
# MCP client config: tlgrm-mcp --allow-write --account personal
```

See also: [configuration](03-configuration.md) · [command reference](02-commands.md#mcp-tools) · [all features](01-features.md).
