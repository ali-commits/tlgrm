# Changelog

All notable changes to tlgrm are documented here. This project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Multi-account support.** Log into multiple Telegram accounts, each a named
  profile (`tlgrm account add/list/use/rename/remove`) with its own session.
  Select one per command with `-a/--account`. A pre-0.3.0 single session is
  migrated to account `default` automatically.
- **Background server + dual-mode CLI.** `tlgrm server start` runs a persistent
  process that owns one hot connection per account over an owner-only Unix
  socket. CLI commands automatically route through it when it's running (fast,
  no per-command login) and fall back to a direct connection when it isn't —
  which structurally eliminates the "database is locked" session conflict.

## [0.2.1] — 2026-06-16

### Added

- **Listener chat/user filtering.** `tlgrm listen` and `tlgrm daemon install` now
  accept `--only CHAT` (whitelist — forward only matching chats/users) and
  `--ignore CHAT` (blacklist — never forward matching chats/users). Each takes an
  `@username`, id, or phone, is repeatable and comma-separated, and matches a
  message by its chat *or* its sender. The filter is applied before any media
  download, so ignored chats cost nothing.

## [0.2.0] — 2026-06-16

This release rolls up everything since the first public release (0.1.0). The
headline change is that the **CLI, webhook daemon, and MCP server can now run at
the same time** against one account, plus a much stronger speech-to-text stack
and a more robust daemon.

### Added

- **Per-consumer sessions (`--session PATH`).** A Telethon session is
  single-process, so running the daemon and the MCP server against the same
  session deadlocked. You can now give each long-running consumer its own
  session/login with `--session` on both `tlgrm` and `tlgrm-mcp` (it overrides
  `TG_SESSION_PATH` for that process). The daemon, MCP server, and your CLI then
  run concurrently — no `database is locked`, no risk of `AUTH_KEY_DUPLICATED`.
  See [docs/configuration.md](docs/configuration.md#running-the-daemon-mcp-server-and-cli-at-the-same-time).
- **`tlgrm transcribe`** — standalone speech-to-text for any audio file, no
  Telegram login required (`--file`, `--backend`, `--model`).
- **GPU acceleration for faster-whisper.** With `TG_STT_DEVICE=auto` (default),
  an NVIDIA GPU is detected and used when its CUDA runtime is available, with an
  automatic fall back to CPU at load *or* inference time.
- **`TG_STT_LANGUAGE`** — force a transcription language (e.g. `ar`, `en`) to
  skip auto-detection.
- **Daemon environment snapshot.** systemd user services don't inherit your
  shell, so `tlgrm daemon install` now snapshots the relevant settings (STT
  model, cloud API keys, GPU `LD_LIBRARY_PATH`, …) into an owner-only
  `~/.tlgrm/daemon.env` that the unit loads via `EnvironmentFile=`.
- **STT model pre-warming.** The daemon loads the STT model at startup so the
  first incoming voice note transcribes without delay.
- `uv.lock` is now tracked for reproducible installs.

### Changed

- **Speech-to-text is now multilingual-only.** Backends were narrowed to the
  multilingual whisper family plus cloud providers — `faster-whisper` (default),
  `whisper`, and cloud `openai` / `groq` / `deepgram` / `elevenlabs` / `google`.
  faster-whisper defaults to CPU and downloads models on demand. For good Arabic
  or multilingual accuracy, set `TG_STT_MODEL=large-v3-turbo`.
- **Logs go to stderr.** All progress and log output is on stderr, so stdout is
  pure JSON and pipeable to `jq`.
- **Friendlier errors.** Common Telethon failures (rate limits, invalid
  credentials, unresolved targets, permission errors, …) are mapped to clear,
  human-readable messages instead of raw tracebacks.
- **Documentation overhaul.** README trimmed to ≤200 lines; expanded and
  reorganized `docs/` (configuration, commands, getting-started, webhook guide).

### Fixed

- **`whisper` backend ffmpeg preflight.** The `whisper` backend now checks for
  `ffmpeg` up front and reports a clear error if it's missing (the default
  `faster-whisper` backend bundles its own decoder and needs no system ffmpeg).
- Broken/failed STT model loads are no longer cached, so a transient failure
  doesn't poison later transcriptions.

### Removed

- Non-multilingual STT backends (which couldn't handle Arabic) were dropped in
  favor of the multilingual-only set above.

### Internal

- The CLI was split into focused modules (`parser`, `dispatch`, `output`) over a
  thin `main()`; the session path is resolved at client-build time so flags and
  environment overrides are always honored.

## [0.1.3] — 2026-06-15

- Daemon: snapshot environment into an `EnvironmentFile`; ffmpeg preflight for
  the `whisper` backend; documented the single-process session limitation.

## [0.1.2] — 2026-06-15

- Speech-to-text narrowed to multilingual backends; logs moved to stderr; CLI
  split into modules; friendly Telethon error messages; docs refresh.

## [0.1.1] — 2026-06-14

- Added the `tlgrm transcribe` command; faster-whisper became the default and
  defaults to CPU.

## [0.1.0] — 2026-06-14

- Initial public release: unofficial Telegram command-line client, MCP server,
  and webhook daemon built on Telethon.
