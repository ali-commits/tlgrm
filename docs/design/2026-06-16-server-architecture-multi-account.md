# Design: tlgrm server architecture + multi-account (0.3.0)

**Status:** approved for spec review
**Target release:** 0.3.0 (single ship; breaking changes allowed)
**Date:** 2026-06-16

## 1. Summary

Introduce a persistent local **server** that owns all Telegram connections, and
turn the CLI, the MCP server, and the webhook listener into thin **clients** of
it. The server manages **multiple accounts** at once (like the mobile app),
keeps connections and STT models hot, and hosts live-reconfigurable listening,
per-contact permission filters, and a scheduler.

The CLI stays usable with **no server running** (one-shot direct connection) for
casual send/read use. The server is opt-in for listening and the richer
features.

## 2. Goals

- **Eliminate the session deadlock at the root.** One process owns each account's
  Telethon session; nothing else opens it. The `--session` workaround becomes
  unnecessary.
- **Multi-account.** Log into several Telegram accounts, switch between them, and
  listen to all of them concurrently.
- **Hot resources.** A warm connection per account (fast CLI — no per-command
  connect/auth handshake) and STT models loaded once and shared.
- **Live reconfiguration.** Add/remove listen and write filters, toggle
  allow/block mode, enable/disable STT and pick model/device, set listening
  windows — all without restarting, all persisted.
- **Per-contact permission matrix.** Independent **listen** and **write** filters
  so the tool (and the AI/MCP path) can be allowed to listen but not write to a
  contact, write but not listen, both, or neither.
- **Dual mode.** Casual users run one-shot CLI commands with no background
  service; power users run the server for the full feature set.

## 3. Non-goals

- Windows is best-effort only (Unix-domain sockets; developed/tested on Linux).
- No remote/networked server — the control socket is local and owner-only.
- No GUI/TUI.
- Cron-style recurrence beyond daily windows is deferred (see §15).

## 4. Architecture overview

```
        ┌──────────────────────── tlgrm server (one process) ─────────────────────────┐
        │  AccountManager: one hot TelegramClient per logged-in account                │
        │    personal ─ client + NewMessage handler + per-account config               │
        │    work     ─ client + NewMessage handler + per-account config               │
        │  Shared: STT engine (hot models) · Scheduler (jobs) · Config store           │
        │  Control plane: Unix-domain socket (~/.tlgrm/server.sock, 0600), NDJSON duplex│
        └───────────▲───────────────────────▲───────────────────────▲──────────────────┘
                    │                        │                        │
            ┌───────┴──────┐         ┌───────┴───────┐        ┌───────┴────────┐
            │  tlgrm CLI   │         │   tlgrm-mcp   │        │ (internal) the  │
            │ (client OR   │         │ (stdio↔socket │        │ listener runs   │
            │  direct      │         │  bridge for   │        │ inside server   │
            │  one-shot)   │         │  the AI host) │        │                 │
            └──────────────┘         └───────────────┘        └─────────────────┘
```

- **Server**: owns connections; exposes a control socket; runs the listener,
  scheduler, and STT in-process.
- **CLI**: for each command, if the socket is alive → send a request and print
  the reply (fast path). If not → fall back to a direct one-shot Telethon
  connection for messaging/read commands (today's behavior); management commands
  edit persisted config.
- **MCP**: the `tlgrm-mcp` stdio process the AI host spawns becomes a bridge —
  it forwards tool calls to the server socket. Permission tiers are enforced
  **server-side**.

## 5. Process & dual-mode model

| Situation | Messaging/read command | Management command (filter/stt/webhook/window/account) |
|-----------|------------------------|--------------------------------------------------------|
| Server running | Routed over the socket (warm, no lock) | Update persisted config **and** push live to the server |
| No server | Direct one-shot connection (open → act → exit) | Update persisted config only (applies next server start) |

The CLI decides by attempting to connect to `~/.tlgrm/server.sock`. This keeps
casual use zero-config while making the deadlock structurally impossible: when
the server owns a session, no other process ever opens it directly.

## 6. Components

- **`tlgrm.server.core`** — server bootstrap, socket listener, request dispatch,
  lifecycle (start/stop/reload), PID/lock handling.
- **`tlgrm.server.accounts` (AccountManager)** — load/connect/disconnect hot
  clients per account; route a request to the right client; hot-add an account
  after login; per-account NewMessage handler wiring.
- **`tlgrm.server.protocol`** — NDJSON request/response/event framing, the
  message schema, and error mapping.
- **`tlgrm.server.scheduler`** — persistent job store + asyncio timer loop.
- **`tlgrm.config` (extended)** — account registry, default account, per-account
  config object, atomic read/write.
- **`tlgrm.client`** — the CLI/MCP-side socket client + the dual-mode resolver
  (server vs direct).
- **`tlgrm.core.*`** — unchanged pure operations, reused by both the server and
  the direct-mode CLI.

Each unit has one purpose and a defined boundary; the existing `tlgrm.core`
library is the shared engine both execution paths call into.

## 7. Transport protocol

- **Socket:** `~/.tlgrm/server.sock`, mode `0600`, owner-only. No TCP port.
- **Framing:** newline-delimited JSON, **duplex** (the server can push events at
  any time — live logs, incoming-message subscriptions).
- **Request:** `{"id": N, "cmd": "send", "account": "work", "args": {…}, "tier": "write"}`
- **Response:** `{"id": N, "ok": true, "data": {…}}` or
  `{"id": N, "ok": false, "error": {"type": "...", "message": "..."}}`
- **Stream/event:** `{"event": "log"|"message"|"job", "account": "...", "data": {…}}`
- **Permission tier:** a connection's granted tier (`read` default, `write`,
  `destructive`) is set at connect time; the server rejects any `cmd` above the
  connection's tier. The MCP bridge passes through `--allow-write` /
  `--allow-destructive` as its connect tier, but enforcement is the server's.

## 8. Account model

- An **account** is a named profile with its own Telethon session
  (`~/.tlgrm/accounts/<name>.session`) — its own auth key, a separate Telegram
  "device". Telegram permits many sessions per account, so this is the native
  multi-device model.
- A `default_account` is recorded in config; commands without `--account` use it.
- **Migration:** on first 0.3.0 run, an existing `~/.tlgrm/tg_session.session` is
  moved to `accounts/default.session` and registered as `default`, so upgrades
  keep their login.

Commands:
```
tlgrm account add [<name>]      # interactive login; default name "default"
tlgrm account list              # names, default marker, connected? (if server up)
tlgrm account use <name>        # set default
tlgrm account rename <old> <new>
tlgrm account remove <name>     # log out + delete session + config
tlgrm login                     # alias: account add default
```

## 9. Per-account configuration

Each account independently owns its listening behavior. STT is a shared,
server-global resource (one set of hot models).

```toml
default_account = "personal"

[accounts.personal]
listen_enabled = true
webhook_url    = "https://example.com/personal"
webhook_headers = ["Authorization: Bearer …"]
listen_window  = "09:00-17:00"   # optional; empty = always

[accounts.personal.filter.listen]
mode = "block"                   # "allow" | "block"
list = ["@noisygroup", "-1001234567890"]

[accounts.personal.filter.write]
mode = "block"                   # "allow" | "block"
list = []

[stt]                            # server-global
enabled = true
backend = "faster-whisper"
model   = "large-v3-turbo"
device  = "auto"                 # auto | cpu | cuda
```

Config writes are atomic (temp file + rename); the file is `0600` since it can
contain webhook auth headers.

## 10. Filters & write guard

Two domains, identical grammar, evaluated per account:

- **listen** — decides whether an *incoming* message is processed/forwarded
  (the existing `--only`/`--ignore` behavior, now stateful + live).
- **write** — decides whether an *outgoing* action (send/reply/edit/forward/react
  to a target) is permitted. A blocked write returns a clear `PermissionError`
  without contacting Telegram. This guards the AI/MCP path especially.

Each domain has a **mode** (`allow` = only listed targets pass; `block` =
everyone except listed targets passes) and a **list** of targets (`@username`,
id, or phone). Matching is by chat **or** sender, normalized via Telethon's
marked peer-id (reusing the logic already shipped in 0.2.1).

```
tlgrm filter listen show
tlgrm filter listen mode <allow|block>
tlgrm filter listen add <chat...>
tlgrm filter listen remove <chat...>
tlgrm filter listen clear
tlgrm filter write  show | mode | add | remove | clear     # same grammar
```

Each command updates persisted config and, if the server is running, applies
live to the relevant account's handler/guard.

## 11. Speech-to-text (live, shared)

STT lives in the server, models load once and are shared across all accounts'
listeners. Settings are live-reconfigurable:

```
tlgrm stt status                                   # backend, model, device, loaded?
tlgrm stt enable | disable
tlgrm stt set [--backend …] [--model …] [--device auto|cpu|cuda]
```

`set` updates config and tells the server to (re)load the model lazily on next
use. Default device remains `auto` (GPU when usable, else CPU), as in 0.2.x.

## 12. Scheduler

A scheduled **job** is uniform: `{id, account, when, command, args}` where
`when` is a one-shot datetime, a relative delay, or a daily time. The job runs a
normal tlgrm action, so scheduling generalizes beyond messages.

- **Store:** persisted to `~/.tlgrm/jobs.json` (atomic writes) so jobs survive
  restarts.
- **Loop:** a single asyncio task wakes at the next due job, executes it through
  the same core operations the CLI uses, and reschedules recurring jobs.
- **Listening windows** are implemented *as* scheduler jobs: a window of
  `09:00-17:00` creates two daily jobs that flip `listen_enabled` on/off for that
  account. No separate mechanism.
- **Caveat:** a job fires only while the server is up (acceptable for the
  always-on model). An optional `--native` flag on `schedule send` can use
  Telegram's own server-side scheduling for messages that must fire offline —
  deferred enhancement.

```
tlgrm schedule send --target X --text Y --at "2026-06-20 09:00"   # or --in 2h
tlgrm schedule list
tlgrm schedule cancel <id>
```

## 13. Login flow (direct-then-reload)

`account add` performs the interactive login **in the CLI process** (a new
account is a fresh auth key, so it never collides with the running server),
writes `accounts/<name>.session`, then sends the server a `load_account` control
message. The server connects the new client and starts its handler. All TTY/code
handling stays in the CLI; the protocol only carries a reload signal. Works
identically whether or not the server is running.

## 14. Server lifecycle

```
tlgrm server start [--foreground]    # owns all accounts' connections + STT + scheduler
tlgrm server stop | restart
tlgrm server status                  # uptime, accounts + connection state, STT, jobs
tlgrm server logs
tlgrm server install | uninstall     # systemd user unit (always-on); EnvironmentFile as today
tlgrm daemon …                       # hidden alias for `server …` (back-compat)
```

`server status` and `logs` query the running process over the socket;
`install` reuses the 0.1.3 `EnvironmentFile`/`daemon.env` snapshot mechanism.

## 15. MCP integration

`tlgrm-mcp` becomes a thin bridge: on startup it connects to the server socket
with its declared tier (`read`/`write`/`destructive` from the existing flags)
and an optional `--account`. Each MCP tool call is forwarded as a server request;
the server enforces the tier and the write-guard. If no server is running, the
bridge starts one on demand (or errors with guidance — see open questions). The
tool surface (`whoami`, `list_chats`, `send_message`, …) is unchanged for the AI
host.

## 16. Webhook payload change

The payload gains an `account` object so downstreams know which account received
a message (and so replies route back through the same account):

```json
{ "event": "new_message", "account": {"name": "work", "id": 12345}, "message": {…}, … }
```

Everything else in the 0.2.x payload is unchanged.

## 17. Security

- Control socket is owner-only (`0600`) in `~/.tlgrm` (`0700`); no network
  exposure.
- Session files and config (which may hold webhook auth headers) remain `0600`.
- Write-guard adds a second line of defense for the AI path: even a compromised
  or over-eager MCP client cannot message blocked contacts.
- MCP permission tiers are enforced server-side, not just advertised client-side.

## 18. File layout

```
~/.tlgrm/
  accounts/<name>.session     # one per account (0600)
  config.toml                 # default account + per-account config + stt (0600)
  server.sock                 # control socket (0600)
  server.pid                  # liveness/lock
  jobs.json                   # scheduler store (0600)
  downloads/                  # incoming media (per existing behavior)
  daemon.env                  # systemd EnvironmentFile (existing)
```

## 19. Backward compatibility & migration

- `tg_session.session` → auto-migrated to `accounts/default.session` (account
  `default`); existing users keep their login.
- `tlgrm daemon …` keeps working as an alias for `tlgrm server …`.
- `--session PATH` is **deprecated** (kept working in direct one-shot mode) in
  favor of `--account`; documented as deprecated, removed in a later major.
- `tlgrm listen --webhook-url …` still works for ad-hoc foreground listening;
  the persistent path now reads per-account config.
- Single-account users notice nothing except faster commands once the server runs.

## 20. Error handling

- Typed errors from `tlgrm.core` propagate over the protocol as
  `{type, message}` and render with the existing friendly-error mapping.
- No server + a server-only command → clear "server not running; run `tlgrm
  server start`" message (exit 1), except management commands which simply edit
  config and say "applied; will take effect when the server starts."
- Socket present but stale (server crashed) → CLI detects refused/closed socket,
  cleans up, and falls back to direct mode for messaging commands.

## 21. Testing strategy

All Telegram I/O mocked; no live network.
- Protocol framing round-trips (request/response/event, partial lines).
- AccountManager routing + hot-add (mock clients).
- Filter/write-guard evaluation (allow/block × listen/write × chat/sender).
- Scheduler firing with an injected clock; window jobs toggle `listen_enabled`.
- Config store: atomic read/write, migration of a legacy session.
- Dual-mode resolver: socket-alive → routed; socket-absent → direct.
- Integration: start a real server on a tmp socket, round-trip a mocked command,
  stop cleanly.

## 22. Phasing (one spec → multiple plans → single 0.3.0 ship)

1. **Config + accounts** — extended config store, account registry, session
   migration, `--account`, `account` commands (works in direct mode).
2. **Server core + dual-mode** — unix-socket transport, AccountManager, CLI
   routing + fallback, `server` lifecycle. *Deadlock fixed here.*
3. **Listener in the server** — per-account listening, `account` in payload,
   live `filter listen`, `listen enable`/window, `webhook` config.
4. **Write guard** — `filter write` + outgoing permission checks.
5. **STT hot + live** — shared models in server, `stt` commands.
6. **Scheduler** — jobs, `schedule`, windows.
7. **MCP bridge** — `tlgrm-mcp` as a server client; server-side tier enforcement.
8. **Docs, migration, polish** — ship 0.3.0.

## 23. Open questions

- **MCP with no server:** auto-spawn a server on demand, or require the user to
  start one? (Leaning: auto-spawn if installed, else a clear error.)
- **Recurring schedules** beyond daily windows (cron expressions): include a
  minimal `--daily` now, defer cron.
- **`server status` for non-server users:** should `status` with no server simply
  report "not running" rather than error (yes, planned).
