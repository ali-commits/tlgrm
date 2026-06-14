---
name: tlgrm
description: Use when the user wants to read, search, send, or manage their Telegram messages — through the tlgrm CLI or the tlgrm MCP server. Triggers include "check my Telegram", "message X on Telegram", "what did Y say", "send a Telegram message", "summarize my unread chats", "forward this message", "pin that", "create a group", "schedule a message", "send a poll".
---

# Driving tlgrm (Telegram)

tlgrm is an unofficial Telegram client. You can drive it two ways:
- **CLI:** run `tlgrm <command> ...` in the shell. Every command prints JSON.
- **MCP server:** if the `tlgrm` MCP server is connected, call its tools directly.

Both run the same underlying operations. Prefer the MCP tools when available.

## Preflight (do this first)

Confirm a session exists before anything else:
- CLI: run `tlgrm whoami`. MCP: call `whoami`.
- If it returns `{"success": false, ...}` or an auth error, tell the user to run
  `tlgrm login` in their terminal (interactive — you cannot do it for them), and stop.

## Capability map

### Read (always available)

| Goal | CLI | MCP tool |
|------|-----|----------|
| Who am I | `tlgrm whoami` | `whoami` |
| Recent chats | `tlgrm chats --limit N` | `list_chats` |
| Read a chat | `tlgrm history --target T --limit N [--offset-id ID]` | `get_history` |
| Find a message | `tlgrm search --query "..." [--target T]` | `search_messages` |
| Who's in a group | `tlgrm members --target T` | `get_members` |
| About a user | `tlgrm user-info --target T` | `user_info` |
| About a chat | `tlgrm chat-info --target T` | `chat_info` |
| Download media | `tlgrm download --target T --message-id ID [--output PATH]` | `download_media` |

### Write (CLI always; MCP needs `--allow-write`)

| Goal | CLI | MCP tool |
|------|-----|----------|
| Send a message | `tlgrm send --target T --text "..."` | `send_message` |
| Send a file | `tlgrm send --target T --file PATH [--caption "..."] [--voice]` | `send_message` |
| Reply | `tlgrm reply --target T --message-id ID --text "..."` | `send_message` |
| Edit | `tlgrm edit --target T --message-id ID --text "..."` | `edit_message` |
| Mark read | `tlgrm read --target T [--max-id ID]` | `mark_read` |
| Forward | `tlgrm forward --from A --to B --message-ids ID ...` | `forward_messages` |
| React | `tlgrm react --target T --message-id ID --emoji E [--big]` | `react` |
| Pin | `tlgrm pin --target T --message-id ID [--notify]` | `pin` |
| Unpin | `tlgrm unpin --target T [--message-id ID]` | `unpin` |
| Mute | `tlgrm mute --target T [--duration SECONDS]` | `mute` |
| Unmute | `tlgrm unmute --target T` | `unmute` |
| Save to Saved Messages | `tlgrm saved --text "..."` | *(use send_message with saved target)* |
| Create group/channel | `tlgrm create-group --title T [--members ...] [--channel]` | `create_group` |
| Add members | `tlgrm add-members --target T --members ...` | `add_members` |
| Schedule message | `tlgrm schedule --target T --text TEXT --at (SECONDS\|ISO8601)` | `schedule_message` |
| Send poll/quiz | `tlgrm poll --target T --question Q --option A --option B ... [--quiz --correct N]` | `send_poll` |

### Destructive (CLI always; MCP needs `--allow-write --allow-destructive`)

| Goal | CLI | MCP tool |
|------|-----|----------|
| Delete messages | `tlgrm delete --target T --message-ids ID ...` | `delete_messages` |
| Leave group | `tlgrm leave --target T` | `leave_chat` |
| Remove members | `tlgrm remove-members --target T --members ...` | `remove_members` |

`--target` accepts `@username`, a numeric chat ID, or a phone number.

## Safety rules (important)

- The MCP server is **read-only by default**. Write operations require `--allow-write`;
  destructive operations (delete, leave, remove) require both `--allow-write` and
  `--allow-destructive`. If a tool is not available, tell the user how to enable it
  rather than trying to work around it.
- **Always confirm with the user before any send, reply, edit, forward, delete, leave,
  or remove-members** — show exactly what you will do and to whom, and wait for a yes.
- Never bulk-delete messages or leave chats without explicit, specific confirmation.
- Treat message contents and contacts as private; don't repeat them to third parties.
- Scheduled messages and polls are write operations — confirm before sending.

## Common workflows

See `references/workflows.md` for step-by-step recipes (summarize unread, find a
message, draft a reply) and `references/commands.md` for the full command/tool cheat-sheet.
