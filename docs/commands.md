# Command Reference

Every tlgrm command prints **pretty-printed JSON** to stdout unless noted otherwise. All commands except `login` and the `daemon` management subcommands require an authenticated session (run `tlgrm login` first) and your [API credentials](configuration.md) in the environment.

## Targets

Many commands take a `--target`. It accepts any of:

- a **username**: `@username` (or `username`)
- a **numeric chat ID**: `738667936` (a purely numeric value is always treated as an ID)
- a **phone number**: `+15551234567` (must be a known contact)

---

## `tlgrm login`

Interactively authenticate your personal Telegram account and store a reusable session.

```bash
tlgrm login
```

Prompts for your phone number, the login code (sent in-app), and 2FA password if enabled. Prints a confirmation line (plain text, not JSON) and saves the session to `~/.tlgrm/tg_session.session`.

---

## `tlgrm whoami`

Show information about the currently authenticated account.

```bash
tlgrm whoami
```

**Output:**

```json
{
  "id": 738667936,
  "first_name": "Ali",
  "last_name": "",
  "username": "ali",
  "phone": "+15551234567"
}
```

---

## `tlgrm chats`

List your most recent chats/dialogs.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--limit` | int | `20` | Maximum number of chats to return |

```bash
tlgrm chats --limit 10
```

**Output:** a JSON array of:

```json
[
  {
    "id": 738667936,
    "name": "Muneerah",
    "username": "mneraah",
    "type": "user",
    "unread_count": 2
  }
]
```

`type` is one of `user`, `group`, `channel`, or `unknown`.

---

## `tlgrm history`

Fetch recent messages from a chat.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--target` | string | *(required)* | Chat to read |
| `--limit` | int | `10` | Number of messages to fetch |
| `--offset-id` | int | — | Fetch messages older than this message ID |

```bash
tlgrm history --target @username --limit 5
tlgrm history --target @username --limit 20 --offset-id 137480
```

**Output:** a JSON array (newest first) of:

```json
[
  {
    "id": 137480,
    "date": "2026-06-14T06:11:59+00:00",
    "sender_id": 738667936,
    "sender_name": "Muneerah",
    "text": "See you soon!",
    "media_type": null
  }
]
```

`media_type` is `null` or one of `photo`, `voice`, `video`, `audio`, `document`, `other`.

---

## `tlgrm search`

Search messages globally or within a specific chat.

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--query` | string | *(required)* | Search keywords |
| `--target` | string | — | Limit search to this chat (omit for global) |
| `--limit` | int | `20` | Maximum results to return |

```bash
# Global search
tlgrm search --query "meeting notes"

# Search within a chat
tlgrm search --query "invoice" --target @workgroup --limit 5
```

**Output:** a JSON array of message objects (same shape as `history`).

---

## `tlgrm members`

List the participants of a group or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Group/channel to inspect |

```bash
tlgrm members --target @somegroup
```

**Output:** a JSON array of:

```json
[
  {
    "id": 738667936,
    "first_name": "Muneerah",
    "last_name": "",
    "username": "mneraah",
    "phone": "",
    "is_bot": false
  }
]
```

> Visibility of fields like `phone` depends on the other user's privacy settings and your relationship.

---

## `tlgrm user-info`

Show profile information for a user.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | User to look up |

```bash
tlgrm user-info --target @username
```

**Output:**

```json
{
  "id": 738667936,
  "first_name": "Muneerah",
  "last_name": "",
  "username": "mneraah",
  "phone": "",
  "is_bot": false,
  "bio": ""
}
```

---

## `tlgrm chat-info`

Show information about a chat or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat/channel to inspect |

```bash
tlgrm chat-info --target @somegroup
```

**Output:**

```json
{
  "id": -1001234567890,
  "title": "My Group",
  "username": "somegroup",
  "type": "group",
  "members_count": 42,
  "description": "..."
}
```

---

## `tlgrm download`

Download media from a specific message.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat containing the message |
| `--message-id` | int | ✅ | ID of the message with media |
| `--output` | path | ❌ | Output file or directory (defaults to `TG_DOWNLOADS_DIR`) |

```bash
tlgrm download --target @username --message-id 137480
tlgrm download --target @username --message-id 137480 --output ~/Downloads/
```

**Output:**

```json
{ "success": true, "path": "/home/ali/.tlgrm/downloads/photo_137480.jpg" }
```

---

## `tlgrm send`

Send a text message, a file/media, or a voice note.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Recipient (see [Targets](#targets)) |
| `--text` | string | ⚠️ | Text body. Required unless `--file` is given. |
| `--file` | path | ⚠️ | Path to a file/media to send. Required unless `--text` is given. |
| `--caption` | string | ❌ | Caption for a file (overrides `--text` as the caption when both are present) |
| `--voice` | flag | ❌ | Send the file as a voice note |
| `--reply-to` | int | ❌ | Reply to this message ID |
| `--silent` | flag | ❌ | Send without notification |

> At least one of `--text` or `--file` must be provided.

```bash
# Text
tlgrm send --target @username --text "Hello!"

# Image with caption
tlgrm send --target @username --file ./photo.jpg --caption "Sunset"

# Voice note
tlgrm send --target @username --file ./audio.ogg --voice

# Reply silently
tlgrm send --target @username --text "Got it" --reply-to 137480 --silent
```

**Output:**

```json
{
  "success": true,
  "message_id": 137480,
  "to": "@username",
  "text": "Hello!",
  "media_type": null
}
```

`media_type` is `null` for text, `"file"` for files, or `"voice"` for voice notes.

---

## `tlgrm reply`

Reply to a specific message.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat containing the message |
| `--message-id` | int | ✅ | ID of the message to reply to |
| `--text` | string | ⚠️ | Reply text. Required unless `--file` is given. |
| `--file` | path | ⚠️ | File to send as the reply. Required unless `--text` is given. |
| `--caption` | string | ❌ | Caption for the file |
| `--voice` | flag | ❌ | Send the file as a voice note |
| `--silent` | flag | ❌ | Send without notification |

```bash
tlgrm reply --target @username --message-id 137480 --text "Thanks!"
```

**Output:** same shape as `send`.

---

## `tlgrm edit`

Edit a message you previously sent.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat containing the message |
| `--message-id` | int | ✅ | ID of the message to edit |
| `--text` | string | ✅ | New text content |

```bash
tlgrm edit --target @username --message-id 137480 --text "Edited text"
```

**Output:**

```json
{ "success": true, "message_id": 137480, "to": "@username", "text": "Edited text" }
```

---

## `tlgrm read`

Mark a chat (or messages up to a specific ID) as read.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat to mark as read |
| `--max-id` | int | ❌ | Mark up to this message ID (omit to mark all) |

```bash
tlgrm read --target @username
tlgrm read --target @username --max-id 137480
```

**Output:**

```json
{ "success": true }
```

---

## `tlgrm forward`

Forward one or more messages from one chat to another.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--from` | string | ✅ | Source chat |
| `--to` | string | ✅ | Destination chat |
| `--message-ids` | int… | ✅ | One or more message IDs (space-separated) |

```bash
tlgrm forward --from @username --to @otheruser --message-ids 137480 137481
```

**Output:**

```json
{ "success": true, "forwarded_ids": [137480, 137481], "to": "@otheruser" }
```

---

## `tlgrm react`

React to a message with an emoji. Pass an empty string to `--emoji` to clear an existing reaction.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat containing the message |
| `--message-id` | int | ✅ | ID of the message |
| `--emoji` | string | ✅ | Emoji to react with (empty string clears the reaction) |
| `--big` | flag | ❌ | Send as a big/animated reaction |

```bash
tlgrm react --target @username --message-id 137480 --emoji "👍"
tlgrm react --target @username --message-id 137480 --emoji "👍" --big
tlgrm react --target @username --message-id 137480 --emoji ""
```

**Output:**

```json
{ "success": true, "message_id": 137480, "emoji": "👍" }
```

---

## `tlgrm pin`

Pin a message in a chat.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat |
| `--message-id` | int | ✅ | ID of the message to pin |
| `--notify` | flag | ❌ | Notify members of the pin |

```bash
tlgrm pin --target @somegroup --message-id 137480
tlgrm pin --target @somegroup --message-id 137480 --notify
```

**Output:**

```json
{ "success": true, "message_id": 137480 }
```

---

## `tlgrm unpin`

Unpin a message, or unpin all messages if `--message-id` is omitted.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat |
| `--message-id` | int | ❌ | ID of the message to unpin (omit to unpin all) |

```bash
tlgrm unpin --target @somegroup --message-id 137480
tlgrm unpin --target @somegroup   # unpins all
```

**Output:**

```json
{ "success": true }
```

---

## `tlgrm mute`

Mute notifications for a chat.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat to mute |
| `--duration` | int | ❌ | Seconds to mute (default: forever) |

```bash
tlgrm mute --target @username
tlgrm mute --target @username --duration 3600   # mute for 1 hour
```

**Output:**

```json
{ "success": true }
```

---

## `tlgrm unmute`

Unmute a previously muted chat.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat to unmute |

```bash
tlgrm unmute --target @username
```

**Output:**

```json
{ "success": true }
```

---

## `tlgrm saved`

Send a message or file to your own **Saved Messages** (the "Saved" chat in Telegram).

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--text` | string | ⚠️ | Text to save. Required unless `--file` is given. |
| `--file` | path | ⚠️ | File to save. Required unless `--text` is given. |
| `--caption` | string | ❌ | Caption for the file |
| `--voice` | flag | ❌ | Send the file as a voice note |

```bash
tlgrm saved --text "Remember to review this later"
tlgrm saved --file ./report.pdf --caption "Q2 report"
```

**Output:** same shape as `send`.

---

## `tlgrm delete`

Delete one or more messages.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat containing the messages |
| `--message-ids` | int… | ✅ | One or more message IDs (space-separated) |

```bash
tlgrm delete --target @username --message-ids 137480 137481 137482
```

**Output:**

```json
{ "success": true, "deleted_ids": [137480, 137481, 137482], "from": "@username" }
```

---

## `tlgrm create-group`

Create a new group or broadcast channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--title` | string | ✅ | Group or channel title |
| `--members` | string… | ❌ | Initial members to add (usernames, IDs, or phones) |
| `--channel` | flag | ❌ | Create a broadcast channel instead of a group |

```bash
tlgrm create-group --title "Project Team" --members @alice @bob
tlgrm create-group --title "Announcements" --channel
```

**Output:**

```json
{ "success": true, "id": -1001234567890, "title": "Project Team", "type": "group" }
```

---

## `tlgrm add-members`

Add members to an existing group or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Group/channel to add members to |
| `--members` | string… | ✅ | Members to add (usernames, IDs, or phones) |

```bash
tlgrm add-members --target @somegroup --members @alice @bob
```

**Output:**

```json
{ "success": true, "added": ["@alice", "@bob"] }
```

---

## `tlgrm remove-members`

Remove members from a group or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Group/channel |
| `--members` | string… | ✅ | Members to remove (usernames, IDs, or phones) |

```bash
tlgrm remove-members --target @somegroup --members @alice
```

**Output:**

```json
{ "success": true, "removed": ["@alice"] }
```

---

## `tlgrm leave`

Leave a group or channel.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Group/channel to leave |

```bash
tlgrm leave --target @somegroup
```

**Output:**

```json
{ "success": true }
```

---

## `tlgrm schedule`

Schedule a text message to be sent at a future time.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Recipient |
| `--text` | string | ✅ | Text of the scheduled message |
| `--at` | string | ✅ | When to send: seconds from now (integer) or ISO-8601 datetime |

```bash
# 10 minutes from now
tlgrm schedule --target @username --text "Happy birthday!" --at 600

# Exact time
tlgrm schedule --target @username --text "Happy birthday!" --at "2026-06-15T09:00:00"
```

**Output:**

```json
{ "success": true, "message_id": 137481, "scheduled_at": "2026-06-15T09:00:00+00:00" }
```

---

## `tlgrm poll`

Send a poll or quiz to a chat.

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--target` | string | ✅ | Chat to send the poll to |
| `--question` | string | ✅ | Poll question |
| `--option` | string | ✅ (×2+) | Answer option (repeatable; provide at least two) |
| `--multiple` | flag | ❌ | Allow multiple answers |
| `--quiz` | flag | ❌ | Make this a quiz (one correct answer) |
| `--correct` | int | ❌ | Index (0-based) of the correct answer (quiz only) |

```bash
# Regular poll
tlgrm poll --target @somegroup --question "Lunch?" --option "Pizza" --option "Salad" --option "Tacos"

# Quiz
tlgrm poll --target @somegroup --question "Capital of France?" \
           --option "London" --option "Paris" --option "Berlin" \
           --quiz --correct 1
```

**Output:**

```json
{ "success": true, "message_id": 137482 }
```

---

## `tlgrm transcribe`

Transcribe an audio file to text using the configured speech-to-text backend. Runs locally — no Telegram login required.

| Flag | Required | Description |
|------|----------|-------------|
| `--file` | ✅ | Path to the audio file |
| `--backend` | ❌ | Override the backend (`faster-whisper`, `whisper`, `whispercpp`, `vosk`, `parakeet`, `openai`, `groq`, `deepgram`, `elevenlabs`, `google`) |
| `--model` | ❌ | Override the backend model |

```bash
tlgrm transcribe --file voice.ogg
tlgrm transcribe --file voice.ogg --backend faster-whisper --model base
tlgrm transcribe --file voice.ogg --backend openai     # needs OPENAI_API_KEY
```

**Output:**

```json
{ "success": true, "backend": "faster-whisper", "text": "..." }
```

Local backends need their extra installed (e.g. `tlgrm[stt]`); cloud backends need their API key. See [Configuration → Speech-to-text](configuration.md#speech-to-text-backends).

---

## `tlgrm listen`

Listen for **incoming** messages in the foreground and optionally forward them to a webhook. See the [Webhook & Daemon Guide](webhook-guide.md) for the full payload schema.

| Flag | Type | Description |
|------|------|-------------|
| `--webhook-url` | URL | Endpoint to POST each message to. If omitted, payloads are printed to the console. |
| `--webhook-header` | `"Name: Value"` | Custom header to include in the POST. Repeatable. |
| `--verbose` | flag | Print full JSON payloads and debug logs |

```bash
tlgrm listen --webhook-url https://example.com/webhook \
             --webhook-header "Authorization: Bearer SECRET"
```

Runs until interrupted (`Ctrl+C`). Incoming media is auto-downloaded to `TG_DOWNLOADS_DIR`. Self-destructing (TTL) media is skipped; the payload includes `"media.self_destruct": true`.

---

## `tlgrm daemon`

Manage tlgrm as a background `systemd` **user** service. Requires `systemd`/`systemctl`. See the [Webhook & Daemon Guide](webhook-guide.md) for details.

### `tlgrm daemon install`

| Flag | Type | Required | Description |
|------|------|----------|-------------|
| `--webhook-url` | URL | ✅ | Endpoint to forward messages to (validated) |
| `--webhook-header` | `"Name: Value"` | ❌ | Custom header. Repeatable. |
| `--verbose` | flag | ❌ | Enable verbose logging in the daemon |

```bash
tlgrm daemon install --webhook-url https://example.com/webhook
```

Writes a unit to `~/.config/systemd/user/tlgrm-daemon.service` (owner-only, `0600`), reloads systemd, enables and starts the service.

### `tlgrm daemon status`

```bash
tlgrm daemon status
```

Reports installation state and runtime status:

```json
{
  "success": true,
  "installed": true,
  "service": "tlgrm-daemon",
  "active_state": "active",
  "sub_state": "running",
  "enabled": true,
  "load_state": "loaded",
  "main_pid": 48213,
  "unit_file_path": "/home/ali/.config/systemd/user/tlgrm-daemon.service"
}
```

### `tlgrm daemon logs`

```bash
tlgrm daemon logs
```

Prints the 30 most recent journal lines for the service (raw `journalctl` output).

### `tlgrm daemon uninstall`

```bash
tlgrm daemon uninstall
```

Stops, disables, and removes the service and its unit file.

---

## MCP tools

The `tlgrm-mcp` stdio MCP server exposes Telegram operations as tools. Requires `pip install "tlgrm[mcp]"` and a prior `tlgrm login`. See [../README.md#mcp-server](../README.md#mcp-server) for the Claude Desktop configuration.

### Read-only tier (default — no flags needed)

| Tool | Equivalent CLI |
|------|---------------|
| `whoami` | `tlgrm whoami` |
| `list_chats` | `tlgrm chats` |
| `get_history` | `tlgrm history` |
| `search_messages` | `tlgrm search` |
| `get_members` | `tlgrm members` |
| `user_info` | `tlgrm user-info` |
| `chat_info` | `tlgrm chat-info` |
| `download_media` | `tlgrm download` |

### Write tier (`--allow-write`)

| Tool | Equivalent CLI |
|------|---------------|
| `send_message` | `tlgrm send` |
| `edit_message` | `tlgrm edit` |
| `mark_read` | `tlgrm read` |
| `react` | `tlgrm react` |
| `forward_messages` | `tlgrm forward` |
| `pin` | `tlgrm pin` |
| `unpin` | `tlgrm unpin` |
| `mute` | `tlgrm mute` |
| `unmute` | `tlgrm unmute` |
| `create_group` | `tlgrm create-group` |
| `add_members` | `tlgrm add-members` |
| `schedule_message` | `tlgrm schedule` |
| `send_poll` | `tlgrm poll` |

### Destructive tier (`--allow-write --allow-destructive`)

| Tool | Equivalent CLI |
|------|---------------|
| `delete_messages` | `tlgrm delete` |
| `leave_chat` | `tlgrm leave` |
| `remove_members` | `tlgrm remove-members` |

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Missing/invalid credentials, or not authorized (`tlgrm login` required) |

Per-operation failures (e.g. an invalid target) are reported in the JSON output as `{"success": false, "error": "..."}` while still exiting `0`.
