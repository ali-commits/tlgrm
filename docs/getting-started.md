# Getting Started

`tlgrm` is a personal Telegram account CLI client and webhook background service built on the [Telethon](https://github.com/LonamiWebs/Telethon) library. It lets you script interactions, manage conversations, and bridge your personal Telegram messages into downstream automated workflows.

> **Unofficial app notice:** tlgrm is an independent, unofficial client built on the Telegram API (via Telethon). It is not affiliated with, endorsed by, or sponsored by Telegram.

## Prerequisites

- **Python** `>=3.10`
- **A Telegram account** and access to its phone number (for the login code)
- **Your own Telegram API credentials** — `api_id` and `api_hash` (see below)
- **FFmpeg** — only required for optional local speech-to-text of voice messages

## 1. Get your Telegram API credentials

tlgrm acts as your *user account* via the Telegram client API (MTProto), which requires your own application credentials. tlgrm does **not** bundle any — a shared `api_id` would be rate-limited for everyone.

1. Open **[my.telegram.org](https://my.telegram.org)** and log in (a code is sent **inside the Telegram app**).
2. Click **API development tools**.
3. Create a new application:
   - **App title:** we suggest `tlgrm` — the title must not contain the word "Telegram"
   - **Short name:** `tlgrm`
   - **Platform:** Desktop
4. Copy the resulting **`api_id`** (number) and **`api_hash`** (hex string).

> ℹ️ Each phone number can have only **one** `api_id`, and the `api_hash` cannot be reset — so register it on the account you intend to keep.

## 2. Install tlgrm

With [`uv`](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install .
```

Or with `pip`:

```bash
pip install .
```

To enable voice-to-text transcription, install the `stt` extra (also requires FFmpeg on your system). This installs `faster-whisper`, the default local backend:

```bash
uv tool install ".[stt]"
```

Other backends are available via `stt-whisper` (original OpenAI Whisper), `stt-whispercpp`, `stt-vosk`, or cloud providers (just set an API key — no extra package needed). See [configuration.md](configuration.md#speech-to-text-backends) for details.

## 3. Configure your credentials

Export the credentials from step 1 so tlgrm can find them:

```bash
export TG_API_ID=1234567
export TG_API_HASH=your_api_hash_here
```

Add these lines to your shell profile (`~/.bashrc`, `~/.zshrc`, …) to persist them. See [configuration.md](configuration.md) for all available settings.

## 4. First-time login

Before any other command, authenticate your personal Telegram account. Because Telegram uses a dynamic login code (and 2FA if enabled), run this **interactively**:

```bash
tlgrm login
```

Follow the prompts to enter:
1. Your phone number (international format, e.g. `+15551234567`)
2. The verification code sent to your Telegram app
3. Your 2FA password, if you have one enabled

On success you'll see your account details, and an authenticated session is stored locally at `~/.tlgrm/tg_session.session`. You won't need to log in again unless you delete that file or log out.

> 🔐 **Keep your session file private** — anyone with it can access your account. It is git-ignored by default.

## 5. Send your first message

```bash
# By username
tlgrm send --target @username --text "Hello from tlgrm!"

# By numeric chat ID
tlgrm send --target 738667936 --text "Hi!"
```

Every command returns JSON, so you can pipe results into tools like `jq`:

```bash
tlgrm chats --limit 5 | jq '.[].name'
```

## Next steps

- 📖 Explore every command in the [Command Reference](commands.md).
- 🔔 Forward incoming messages to an HTTP endpoint with the [Webhook & Daemon Guide](webhook-guide.md).
- ⚙️ Tune paths and behavior via [Configuration](configuration.md).
