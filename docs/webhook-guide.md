# Webhook & Daemon Guide

> **Unofficial app notice:** tlgrm is an independent, unofficial client built on the Telegram API (via Telethon). It is not affiliated with, endorsed by, or sponsored by Telegram.

One of tlgrm's most powerful capabilities is acting as a real-time bridge that forwards your **incoming** Telegram messages to an external HTTP webhook. This is useful for connecting your personal Telegram account to a database or workflow automation system (n8n, Make, custom APIs, etc.).

When a message arrives, tlgrm:

1. Builds a structured JSON payload (sender, chat, message, media).
2. Downloads any attached media to `TG_DOWNLOADS_DIR`.
3. Optionally transcribes voice/audio using the configured [STT backend](configuration.md#speech-to-text-backends) (if the `stt` extra or a cloud API key is available).
4. POSTs the payload to your webhook URL (with retries), or prints it if no URL is set.

> Only **incoming** messages trigger the webhook — your own outgoing messages are ignored.

---

## Foreground mode

Run the listener in your terminal to test an endpoint:

```bash
tlgrm listen --webhook-url https://your-server.com/webhook \
             --webhook-header "Authorization: Bearer YOUR_SECRET_TOKEN"
```

Without `--webhook-url`, payloads are printed to the console instead of forwarded — handy for development:

```bash
tlgrm listen --verbose
```

### Custom headers

Secure or tag your endpoint by passing one or more `--webhook-header` options (repeatable):

```bash
tlgrm listen --webhook-url https://example.com/webhook \
             --webhook-header "X-Auth-Token: secret123" \
             --webhook-header "X-Client-ID: personal-bot"
```

Header values are redacted from logs.

---

## Background daemon (systemd)

Instead of keeping a terminal open, run tlgrm as a persistent `systemd` **user** service. Requires `systemd`/`systemctl`.

### 1. Install & start

Builds the unit at `~/.config/systemd/user/tlgrm-daemon.service` (written owner-only, `0600`, since it may embed auth headers), enables start-on-boot, and starts the process:

```bash
tlgrm daemon install --webhook-url https://your-server.com/webhook \
                     --webhook-header "Authorization: Bearer YOUR_TOKEN"
```

> The webhook URL and headers are validated before the unit is written (no whitespace, control characters, or quotes that could corrupt the unit file).

### 2. Check status

```bash
tlgrm daemon status
```

### 3. Read logs

```bash
tlgrm daemon logs
```

Shows the 30 most recent journal entries. For a live tail, use `journalctl` directly:

```bash
journalctl --user -u tlgrm-daemon -f
```

### 4. Stop & uninstall

```bash
tlgrm daemon uninstall
```

> **Credentials for the daemon:** the service inherits your environment. Ensure `TG_API_ID` / `TG_API_HASH` are available to the systemd user manager — see [configuration.md](configuration.md#for-the-systemd-daemon).

---

## Webhook payload schema

Each webhook POST sends a JSON body with this structure:

```json
{
  "event": "new_message",
  "timestamp": "2026-06-14T06:12:00.123456+00:00",
  "message": {
    "id": 137475,
    "text": "Check this out!",
    "date": "2026-06-14T06:11:59+00:00",
    "reply_to_msg_id": null
  },
  "chat": {
    "id": 738667936,
    "name": "Muneerah",
    "username": "mneraah",
    "type": "user"
  },
  "sender": {
    "id": 738667936,
    "first_name": "Muneerah",
    "last_name": "",
    "username": "mneraah",
    "phone": "+601****6023",
    "display_name": "Muneerah"
  },
  "media": {
    "present": true,
    "type": "voice",
    "local_path": "/home/ali/.tlgrm/downloads/voice_137475.ogg",
    "transcription": "Hello, I will be home in ten minutes!"
  }
}
```

### Field reference

| Field | Type | Notes |
|-------|------|-------|
| `event` | string | Always `"new_message"` |
| `timestamp` | string | UTC ISO-8601 time the event was processed |
| `message.id` | int | Telegram message ID |
| `message.text` | string | Message text (empty string for media-only messages) |
| `message.date` | string | ISO-8601 send time |
| `message.reply_to_msg_id` | int \| null | ID of the message being replied to, if any |
| `chat.type` | string | `user`, `group`, `channel`, or `unknown` |
| `sender.*` | object | Sender identity fields (may be empty per privacy settings) |
| `media.present` | bool | Whether the message has media |
| `media.type` | string \| null | `photo`, `voice`, `video`, `audio`, `document`, or `other` |
| `media.local_path` | string \| null | Absolute path to the downloaded file |
| `media.transcription` | string \| null | STT transcription of voice/audio (see [STT backends](configuration.md#speech-to-text-backends)) |

> If the `stt` extra is installed (provides `faster-whisper`) or a cloud API key is set, incoming voice notes and audio are transcribed automatically and the text appears in `media.transcription`. Without any STT backend, the field is `null` and everything else works unchanged.

---

## Delivery behavior

- Forwarding runs as a background task so it never blocks the listener.
- Failed POSTs are retried up to 3 times with exponential backoff, then logged and dropped.
- A `2xx` response is considered success; anything else is logged as an error.

> tlgrm does not currently sign webhook payloads (e.g. HMAC). If your endpoint is public, protect it with a secret header and verify it server-side.
