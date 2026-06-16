# Phase 2 — Server core + dual-mode (0.3.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** A persistent local `tlgrm server` that owns one hot Telethon client per account and runs commands over a Unix-domain socket; the CLI routes through it when it's running and falls back to a direct connection when it isn't. This is the phase that eliminates the session deadlock.

**Architecture:** Extract the existing `cmd→core` dispatch into a reusable `execute(client, args)`. The server (`asyncio.start_unix_server`) accepts NDJSON requests, runs them through `execute` against an `AccountManager`'s hot client, and replies. A small IPC client lets the CLI send the same requests; `cli.main` picks server-vs-direct automatically. Permission tiers are enforced server-side.

**Tech Stack:** Python `asyncio` (stdlib unix sockets), Telethon, pytest + pytest-asyncio (`asyncio_mode=auto`).

**Reference:** `docs/design/2026-06-16-server-architecture-multi-account.md` §4–§7, §14, §15, §20.

**Standing rules for every task:** use `uv` for all commands (`uv run --extra dev --extra mcp python -m pytest ...`); never vanilla pip. Don't touch the bundled-credential code in `config.py`. TDD: failing test → run → implement → run → commit. Append to each commit message: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Extract `execute(client, args)` from dispatch

**Files:** Create `src/tlgrm/execute.py`; Modify `src/tlgrm/dispatch.py`; Test `tests/test_execute.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_execute.py`):

```python
import types
import pytest
from tlgrm import execute as ex


class _Chats:
    async def list_chats(self, client, limit):
        return {"success": True, "chats": [], "limit": limit}


def test_execute_routes_read_command(monkeypatch):
    monkeypatch.setattr(ex, "chats", _Chats())
    args = types.SimpleNamespace(command="chats", limit=7)
    out = __import__("asyncio").run(ex.execute(object(), args))
    assert out == {"success": True, "chats": [], "limit": 7}


def test_execute_unknown_command_raises():
    args = types.SimpleNamespace(command="nope")
    with pytest.raises(ex.TlgrmError):
        __import__("asyncio").run(ex.execute(object(), args))
```

- [ ] **Step 2: Run** `uv run --extra dev python -m pytest tests/test_execute.py -q` → FAIL (no module).

- [ ] **Step 3: Create `src/tlgrm/execute.py`** by moving `_parse_when` and the entire `if/elif` body out of `dispatch.run_command`. Each branch `return`s its dict instead of calling `emit`:

```python
"""Pure command dispatch: map parsed args to a core operation against a
connected client and RETURN the result dict. Shared by the direct CLI path and
the server, so it never prints or connects — callers own I/O."""

import datetime

from .core import messages, chats, users
from .core.errors import TlgrmError


def _parse_when(value):
    """Parse a schedule time: integer seconds-from-now, or ISO-8601 datetime."""
    if value.isdigit():
        return datetime.timedelta(seconds=int(value))
    return datetime.datetime.fromisoformat(value)


async def execute(client, args):
    """Run one command against a connected client; return its result dict."""
    cmd = args.command
    if cmd == "chats":
        return await chats.list_chats(client, args.limit)
    elif cmd == "send":
        return {"success": True, **await messages.send(
            client, args.target, text=args.text, file_path=args.file,
            caption=args.caption, voice=args.voice,
            reply_to=args.reply_to, silent=args.silent)}
    elif cmd == "reply":
        return {"success": True, **await messages.send(
            client, args.target, text=args.text, file_path=args.file,
            caption=args.caption, voice=args.voice,
            reply_to=args.message_id, silent=args.silent)}
    elif cmd == "edit":
        return {"success": True, **await messages.edit(
            client, args.target, args.message_id, args.text)}
    elif cmd == "delete":
        return {"success": True, **await messages.delete(
            client, args.target, args.message_ids)}
    elif cmd == "history":
        return await messages.get_history(client, args.target, args.limit, args.offset_id)
    elif cmd == "search":
        return await messages.search(client, args.query, args.target, args.limit)
    elif cmd == "read":
        return {"success": True, **await messages.mark_read(client, args.target, args.max_id)}
    elif cmd == "download":
        return {"success": True, **await messages.download(
            client, args.target, args.message_id, args.output)}
    elif cmd == "whoami":
        return await users.whoami(client)
    elif cmd == "user-info":
        return await users.user_info(client, args.target)
    elif cmd == "chat-info":
        return await chats.chat_info(client, args.target)
    elif cmd == "members":
        return await users.get_members(client, args.target)
    elif cmd == "forward":
        return {"success": True, **await messages.forward(
            client, args.from_chat, args.to_chat, args.message_ids)}
    elif cmd == "react":
        return {"success": True, **await messages.react(
            client, args.target, args.message_id, args.emoji, args.big)}
    elif cmd == "pin":
        return {"success": True, **await chats.pin(
            client, args.target, args.message_id, args.notify)}
    elif cmd == "unpin":
        return {"success": True, **await chats.unpin(client, args.target, args.message_id)}
    elif cmd == "mute":
        return {"success": True, **await chats.mute(client, args.target, args.duration)}
    elif cmd == "unmute":
        return {"success": True, **await chats.unmute(client, args.target)}
    elif cmd == "saved":
        return {"success": True, **await messages.send(
            client, "me", text=args.text, file_path=args.file,
            caption=args.caption, voice=args.voice)}
    elif cmd == "create-group":
        return {"success": True, **await chats.create_group(
            client, args.title, args.members, args.channel)}
    elif cmd == "add-members":
        return {"success": True, **await users.add_members(client, args.target, args.members)}
    elif cmd == "remove-members":
        return {"success": True, **await users.remove_members(client, args.target, args.members)}
    elif cmd == "leave":
        return {"success": True, **await chats.leave(client, args.target)}
    elif cmd == "schedule":
        return {"success": True, **await messages.schedule_message(
            client, args.target, _parse_when(args.at), args.text)}
    elif cmd == "poll":
        return {"success": True, **await messages.send_poll(
            client, args.target, args.question, args.options,
            args.multiple, args.quiz, args.correct)}
    raise TlgrmError(f"Unknown command: {cmd!r}")
```

- [ ] **Step 4: Rewrite `dispatch.run_command`** to delegate. Replace the whole `async with open_client(account) as client:` block (the if/elif) with:

```python
    async with open_client(account) as client:
        emit(await execute(client, args))
```

Add `from .execute import execute` at the top of `dispatch.py`, and remove the now-unused `_parse_when` from `dispatch.py` plus the now-unused `messages, chats, users` import there (keep `get_client, open_client`). Leave `_login` and `run_account_command` untouched.

- [ ] **Step 5: Run** the full suite: `uv run --extra dev --extra mcp python -m pytest -q` → PASS (the existing dispatch/core tests now exercise `execute` indirectly). Then **commit**:

```bash
git add src/tlgrm/execute.py src/tlgrm/dispatch.py tests/test_execute.py
git commit -m "refactor: extract execute(client,args) shared by CLI and server"
```

---

### Task 2: NDJSON protocol helpers

**Files:** Create `src/tlgrm/server/__init__.py` (empty), `src/tlgrm/server/protocol.py`; Test `tests/test_protocol.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_protocol.py`):

```python
import asyncio
from tlgrm.server import protocol as p


def test_request_and_response_builders():
    req = p.request(1, "chats", account="work", args={"limit": 5}, tier="read")
    assert req == {"id": 1, "cmd": "chats", "account": "work",
                   "args": {"limit": 5}, "tier": "read"}
    assert p.ok(1, {"x": 2}) == {"id": 1, "ok": True, "data": {"x": 2}}
    assert p.err(1, "Boom", "bad") == {
        "id": 1, "ok": False, "error": {"type": "Boom", "message": "bad"}}


def test_read_write_roundtrip_over_a_pipe():
    async def go():
        rd, wr = asyncio.StreamReader(), None

        class _W:
            def __init__(self): self.buf = b""
            def write(self, b): self.buf += b
            async def drain(self): pass

        w = _W()
        await p.write_message(w, {"hello": "world"})
        # feed what was written into a reader and read it back
        reader = asyncio.StreamReader()
        reader.feed_data(w.buf)
        reader.feed_eof()
        assert await p.read_message(reader) == {"hello": "world"}
        assert await p.read_message(reader) is None  # EOF
    asyncio.run(go())
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Create `src/tlgrm/server/protocol.py`:**

```python
"""Newline-delimited JSON framing for the local control socket."""

import json


async def read_message(reader):
    """Read one NDJSON message, or None at EOF."""
    line = await reader.readline()
    if not line:
        return None
    return json.loads(line.decode())


async def write_message(writer, obj):
    writer.write((json.dumps(obj) + "\n").encode())
    await writer.drain()


def request(rid, cmd, account=None, args=None, tier="destructive"):
    return {"id": rid, "cmd": cmd, "account": account,
            "args": args or {}, "tier": tier}


def ok(rid, data):
    return {"id": rid, "ok": True, "data": data}


def err(rid, etype, message):
    return {"id": rid, "ok": False, "error": {"type": etype, "message": message}}
```

Also create an empty `src/tlgrm/server/__init__.py`.

- [ ] **Step 4: Run** `uv run --extra dev python -m pytest tests/test_protocol.py -q` → PASS. **Commit:**

```bash
git add src/tlgrm/server/__init__.py src/tlgrm/server/protocol.py tests/test_protocol.py
git commit -m "feat(server): NDJSON protocol helpers"
```

---

### Task 3: Permission tiers

**Files:** Create `src/tlgrm/server/tiers.py`; Test `tests/test_tiers.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_tiers.py`):

```python
from tlgrm.server import tiers


def test_read_tier_blocks_write_and_destructive():
    assert tiers.is_allowed("read", "chats")
    assert not tiers.is_allowed("read", "send")
    assert not tiers.is_allowed("read", "delete")


def test_write_tier_allows_write_not_destructive():
    assert tiers.is_allowed("write", "send")
    assert not tiers.is_allowed("write", "delete")


def test_destructive_tier_allows_everything():
    for cmd in ("chats", "send", "delete", "leave", "remove-members"):
        assert tiers.is_allowed("destructive", cmd)


def test_unknown_command_defaults_to_destructive_requirement():
    assert not tiers.is_allowed("write", "totally-unknown")
    assert tiers.is_allowed("destructive", "totally-unknown")
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Create `src/tlgrm/server/tiers.py`:**

```python
"""Permission tiers for control-socket commands. A connection is granted a tier
(read < write < destructive); the server rejects commands above it."""

_ORDER = {"read": 0, "write": 1, "destructive": 2}

COMMAND_TIERS = {
    # read
    "chats": "read", "history": "read", "search": "read", "whoami": "read",
    "user-info": "read", "chat-info": "read", "members": "read", "download": "read",
    "ping": "read",
    # write
    "send": "write", "reply": "write", "edit": "write", "read": "write",
    "react": "write", "forward": "write", "pin": "write", "unpin": "write",
    "mute": "write", "unmute": "write", "saved": "write", "create-group": "write",
    "add-members": "write", "schedule": "write", "poll": "write",
    # destructive
    "delete": "destructive", "remove-members": "destructive", "leave": "destructive",
}


def is_allowed(conn_tier, cmd):
    """True if a connection granted `conn_tier` may run `cmd`. Unknown commands
    require the highest tier (fail safe)."""
    need = COMMAND_TIERS.get(cmd, "destructive")
    return _ORDER.get(conn_tier, -1) >= _ORDER[need]
```

- [ ] **Step 4: Run** → PASS. **Commit:**

```bash
git add src/tlgrm/server/tiers.py tests/test_tiers.py
git commit -m "feat(server): command permission tiers"
```

---

### Task 4: AccountManager (hot clients)

**Files:** Create `src/tlgrm/server/manager.py`; Test `tests/test_manager.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_manager.py`):

```python
import asyncio
import pytest
from tlgrm.server.manager import AccountManager


def test_manager_connects_once_and_caches(monkeypatch):
    built = []

    class _FakeClient:
        def __init__(self, name): self.name = name; self.connected = False
        async def connect(self): self.connected = True
        async def is_user_authorized(self): return True
        async def disconnect(self): self.connected = False

    def fake_get_client(account=None, must_exist=True):
        built.append(account)
        return _FakeClient(account)

    import tlgrm.core.client as cc
    monkeypatch.setattr(cc, "get_client", fake_get_client)
    monkeypatch.setattr("tlgrm.accounts.resolve_account", lambda name=None: name or "default")

    async def go():
        m = AccountManager()
        c1 = await m.get("work")
        c2 = await m.get("work")
        assert c1 is c2           # cached, built once
        assert built == ["work"]
        assert c1.connected
        await m.disconnect_all()
        assert not c1.connected
    asyncio.run(go())


def test_manager_get_unauthorized_raises(monkeypatch):
    class _Unauth:
        async def connect(self): pass
        async def is_user_authorized(self): return False
        async def disconnect(self): pass

    import tlgrm.core.client as cc
    monkeypatch.setattr(cc, "get_client", lambda account=None, must_exist=True: _Unauth())
    monkeypatch.setattr("tlgrm.accounts.resolve_account", lambda name=None: name or "default")

    async def go():
        from tlgrm.core.errors import NotAuthorizedError
        m = AccountManager()
        with pytest.raises(NotAuthorizedError):
            await m.get("work")
    asyncio.run(go())
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Create `src/tlgrm/server/manager.py`:**

```python
"""Owns one connected Telethon client per account for the lifetime of the
server. Clients are created lazily and reused (hot connections)."""

import logging

logger = logging.getLogger("tlgrm-server")


class AccountManager:
    def __init__(self):
        self._clients = {}  # account name -> connected TelegramClient

    async def get(self, account=None):
        """Return a connected, authorized client for `account` (or the default),
        creating and connecting it on first use."""
        from ..accounts import resolve_account
        from ..core import client as core_client

        name = resolve_account(account)
        if name not in self._clients:
            c = core_client.get_client(name)
            await core_client.ensure_authorized(c)  # connect + check
            self._clients[name] = c
        return self._clients[name]

    async def load_all(self):
        """Connect every configured account; skip (with a warning) any that
        aren't authorized yet, so one bad account doesn't sink startup."""
        from ..accounts import load_config
        for name in load_config().get("accounts", {}):
            try:
                await self.get(name)
                logger.info(f"Connected account '{name}'.")
            except Exception as e:
                logger.warning(f"Skipping account '{name}': {e}")

    async def disconnect_all(self):
        for c in self._clients.values():
            try:
                await c.disconnect()
            except Exception:
                pass
        self._clients.clear()
```

- [ ] **Step 4: Run** → PASS. **Commit:**

```bash
git add src/tlgrm/server/manager.py tests/test_manager.py
git commit -m "feat(server): AccountManager hot client registry"
```

---

### Task 5: Request handler

**Files:** Create `src/tlgrm/server/handler.py`; Test `tests/test_handler.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_handler.py`):

```python
import asyncio
import types
from tlgrm.server import handler


class _Manager:
    def __init__(self, client=None, exc=None): self._c = client; self._exc = exc
    async def get(self, account=None):
        if self._exc:
            raise self._exc
        return self._c


def test_ping_returns_pong():
    out = asyncio.run(handler.handle_request(_Manager(), {"id": 1, "cmd": "ping"}))
    assert out["ok"] and out["data"] == {"pong": True}


def test_tier_rejection():
    req = {"id": 2, "cmd": "delete", "tier": "read", "args": {}}
    out = asyncio.run(handler.handle_request(_Manager(), req))
    assert out["ok"] is False
    assert out["error"]["type"] == "PermissionError"


def test_executes_command(monkeypatch):
    async def fake_execute(client, args):
        assert args.command == "chats" and args.limit == 3
        return {"success": True, "chats": []}
    monkeypatch.setattr(handler, "execute", fake_execute)
    req = {"id": 3, "cmd": "chats", "tier": "read", "args": {"limit": 3}}
    out = asyncio.run(handler.handle_request(_Manager(client=object()), req))
    assert out["ok"] and out["data"]["success"]


def test_error_is_mapped(monkeypatch):
    from tlgrm.core.errors import NotAuthorizedError
    out = asyncio.run(handler.handle_request(
        _Manager(exc=NotAuthorizedError("nope")),
        {"id": 4, "cmd": "chats", "tier": "read", "args": {}}))
    assert out["ok"] is False
    assert out["error"]["type"] == "NotAuthorizedError"
    assert "nope" in out["error"]["message"]
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Create `src/tlgrm/server/handler.py`:**

```python
"""Turn one decoded request into a response dict: tier check, run the command
against the account's hot client, map exceptions to error responses."""

from types import SimpleNamespace

from ..execute import execute
from .protocol import ok, err
from .tiers import is_allowed


async def handle_request(manager, req):
    rid = req.get("id")
    cmd = req.get("cmd")
    if cmd == "ping":
        return ok(rid, {"pong": True})
    if not is_allowed(req.get("tier", "read"), cmd):
        return err(rid, "PermissionError",
                   f"'{cmd}' requires a higher permission tier")
    try:
        client = await manager.get(req.get("account"))
        args = SimpleNamespace(command=cmd, **(req.get("args") or {}))
        data = await execute(client, args)
        return ok(rid, data)
    except Exception as e:  # noqa: BLE001 — every failure becomes a response
        return err(rid, type(e).__name__, str(e))
```

- [ ] **Step 4: Run** → PASS. **Commit:**

```bash
git add src/tlgrm/server/handler.py tests/test_handler.py
git commit -m "feat(server): request handler with tier check + error mapping"
```

---

### Task 6: The server process (socket + lifecycle)

**Files:** Create `src/tlgrm/server/app.py`; Test `tests/test_server_app.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_server_app.py`) — start a real server with a stub manager on a tmp socket, round-trip a ping and a command, then stop:

```python
import asyncio
import pytest
from tlgrm.server import app, protocol


class _StubManager:
    async def load_all(self): pass
    async def get(self, account=None): return object()
    async def disconnect_all(self): pass


@pytest.mark.asyncio
async def test_server_roundtrip(tmp_path, monkeypatch):
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(app, "socket_path", lambda: sock)
    monkeypatch.setattr(app, "pid_path", lambda: str(tmp_path / "s.pid"))
    monkeypatch.setattr(app, "execute",
                        lambda client, args: _aval({"success": True, "echo": args.command}))

    srv = await app.start_server(_StubManager())
    try:
        reader, writer = await asyncio.open_unix_connection(sock)
        await protocol.write_message(writer, protocol.request(1, "ping"))
        assert (await protocol.read_message(reader))["data"] == {"pong": True}
        await protocol.write_message(writer, protocol.request(2, "whoami", tier="read"))
        resp = await protocol.read_message(reader)
        assert resp["ok"] and resp["data"]["echo"] == "whoami"
        writer.close()
    finally:
        await app.stop_server(srv)


async def _aval(v):
    return v
```

NOTE: the test monkeypatches `app.execute` so it doesn't need a real Telegram client; the handler imports `execute` from `..execute`, so `app.start_server` must inject the manager and the handler must use the patched symbol. To keep the test simple, `app` re-exports `execute` is NOT required — instead the handler already calls the real `execute`; for this test we patch `tlgrm.server.handler.execute`. Adjust the monkeypatch target to `tlgrm.server.handler.execute` and drop the `app.execute` patch.

(When implementing, FIX the test's monkeypatch target to `handler.execute` — import `from tlgrm.server import handler` and `monkeypatch.setattr(handler, "execute", lambda c, a: _aval(...))`.)

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Create `src/tlgrm/server/app.py`:**

```python
"""The persistent server: owns the AccountManager and serves the control
socket. One process per machine/user."""

import os
import asyncio
import logging
import signal

from .protocol import read_message, write_message
from .handler import handle_request
from .manager import AccountManager

logger = logging.getLogger("tlgrm-server")


def _dir():
    return os.path.expanduser("~/.tlgrm")


def socket_path():
    return os.getenv("TG_SERVER_SOCK", os.path.join(_dir(), "server.sock"))


def pid_path():
    return os.path.join(_dir(), "server.pid")


async def _handle_conn(reader, writer, manager):
    try:
        while True:
            req = await read_message(reader)
            if req is None:
                break
            resp = await handle_request(manager, req)
            await write_message(writer, resp)
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    finally:
        writer.close()


async def start_server(manager=None):
    """Bind the socket and begin serving. Returns the asyncio server object."""
    manager = manager or AccountManager()
    await manager.load_all()
    sock = socket_path()
    os.makedirs(os.path.dirname(sock), mode=0o700, exist_ok=True)
    if os.path.exists(sock):
        os.remove(sock)  # stale socket from a previous run
    server = await asyncio.start_unix_server(
        lambda r, w: _handle_conn(r, w, manager), path=sock)
    os.chmod(sock, 0o600)
    server._tlgrm_manager = manager  # stash for shutdown
    with open(pid_path(), "w") as f:
        f.write(str(os.getpid()))
    logger.info(f"tlgrm server listening on {sock}")
    return server


async def stop_server(server):
    server.close()
    await server.wait_closed()
    mgr = getattr(server, "_tlgrm_manager", None)
    if mgr:
        await mgr.disconnect_all()
    for path in (socket_path(), pid_path()):
        if os.path.exists(path):
            os.remove(path)


async def serve_forever(manager=None):
    """Run the server until SIGTERM/SIGINT (used by `tlgrm server start`)."""
    server = await start_server(manager)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        await stop_server(server)
```

- [ ] **Step 4: Run** `uv run --extra dev python -m pytest tests/test_server_app.py -q` → PASS. **Commit:**

```bash
git add src/tlgrm/server/app.py tests/test_server_app.py
git commit -m "feat(server): unix-socket server process + lifecycle"
```

---

### Task 7: IPC client + dual-mode resolver

**Files:** Create `src/tlgrm/ipc.py`; Test `tests/test_ipc.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_ipc.py`) — run a tiny real server, prove the client round-trips, and prove `is_server_running` is False with no socket:

```python
import asyncio
import pytest
from tlgrm import ipc
from tlgrm.server import protocol


def test_is_server_running_false_without_socket(tmp_path, monkeypatch):
    monkeypatch.setattr(ipc, "socket_path", lambda: str(tmp_path / "nope.sock"))
    assert ipc.is_server_running() is False


@pytest.mark.asyncio
async def test_request_roundtrip(tmp_path, monkeypatch):
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(ipc, "socket_path", lambda: sock)

    async def echo(reader, writer):
        req = await protocol.read_message(reader)
        await protocol.write_message(writer, protocol.ok(req["id"], {"echo": req["cmd"]}))
        writer.close()

    server = await asyncio.start_unix_server(echo, path=sock)
    try:
        assert ipc.is_server_running() is True
        resp = await ipc.request_async("whoami", account="work", args={}, tier="read")
        assert resp["data"]["echo"] == "whoami"
    finally:
        server.close()
        await server.wait_closed()
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Create `src/tlgrm/ipc.py`:**

```python
"""Client side of the control socket: detect a running server and send requests.
Used by the CLI's dual-mode resolver and (later) the MCP bridge."""

import os
import socket
import asyncio
import itertools

from .server.protocol import read_message, write_message, request

_ids = itertools.count(1)


def socket_path():
    return os.getenv("TG_SERVER_SOCK", os.path.expanduser("~/.tlgrm/server.sock"))


def is_server_running():
    """True if a server is accepting connections on the socket."""
    path = socket_path()
    if not os.path.exists(path):
        return False
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(path)
        return True
    except OSError:
        return False
    finally:
        s.close()


async def request_async(cmd, account=None, args=None, tier="destructive"):
    reader, writer = await asyncio.open_unix_connection(socket_path())
    try:
        await write_message(writer, request(next(_ids), cmd, account, args, tier))
        return await read_message(reader)
    finally:
        writer.close()


def request_sync(cmd, account=None, args=None, tier="destructive"):
    return asyncio.run(request_async(cmd, account, args, tier))
```

- [ ] **Step 4: Run** → PASS. **Commit:**

```bash
git add src/tlgrm/ipc.py tests/test_ipc.py
git commit -m "feat(ipc): control-socket client + server detection"
```

---

### Task 8: Route CLI commands through the server when it's running

**Files:** Modify `src/tlgrm/cli.py`; Modify `src/tlgrm/dispatch.py`; Test `tests/test_dual_mode.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_dual_mode.py`) — when a server is running, an authenticated command is sent over IPC and NOT run directly:

```python
import types
import pytest
from tlgrm import dispatch, ipc


def test_run_command_routes_to_server(monkeypatch, capsys):
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)

    sent = {}
    def fake_request_sync(cmd, account=None, args=None, tier="destructive"):
        sent.update(cmd=cmd, account=account, args=args)
        return {"id": 1, "ok": True, "data": {"success": True, "routed": True}}
    monkeypatch.setattr(ipc, "request_sync", fake_request_sync)

    # If it tried to connect directly this would explode:
    def boom(*a, **k): raise AssertionError("should not open a direct client")
    monkeypatch.setattr(dispatch, "open_client", boom)

    args = types.SimpleNamespace(command="whoami", account="work")
    dispatch.run_command_routed(args)
    assert sent["cmd"] == "whoami" and sent["account"] == "work"
    assert '"routed": true' in capsys.readouterr().out.lower()


def test_run_command_routed_falls_back_when_no_server(monkeypatch):
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)
    called = {}
    async def fake_run_command(args): called["direct"] = True
    monkeypatch.setattr(dispatch, "run_command", fake_run_command)
    args = types.SimpleNamespace(command="whoami", account=None)
    dispatch.run_command_routed(args)
    assert called.get("direct") is True
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Add `run_command_routed` to `dispatch.py`** (the dual-mode entry the CLI calls for authenticated commands). It serializes the argparse namespace to a plain dict and sends it, or falls back to the direct async path:

```python
def run_command_routed(args):
    """Dual-mode entry for authenticated commands: route through a running
    server, else run directly. login / account-add always go direct (they own
    interactive TTY and session creation)."""
    import asyncio
    from . import ipc
    from .output import emit

    direct_only = args.command in ("login",) or (
        args.command == "account" and getattr(args, "account_command", None) == "add")
    if direct_only or not ipc.is_server_running():
        asyncio.run(run_command(args))
        return

    payload = {k: v for k, v in vars(args).items()
               if k not in ("command", "account", "session")}
    resp = ipc.request_sync(args.command, account=getattr(args, "account", None),
                            args=payload, tier="destructive")
    if resp.get("ok"):
        emit(resp["data"])
    else:
        e = resp.get("error", {})
        emit({"success": False, "error": e.get("message", "server error")})
```

- [ ] **Step 4: Point `cli.main`'s final `else` branch at the router.** Change `else: asyncio.run(run_command(args))` to:

```python
        else:
            from .dispatch import run_command_routed
            run_command_routed(args)
```

- [ ] **Step 5: Run** the new test and full suite: `uv run --extra dev --extra mcp python -m pytest -q` → PASS. **Commit:**

```bash
git add src/tlgrm/cli.py src/tlgrm/dispatch.py tests/test_dual_mode.py
git commit -m "feat(cli): dual-mode — route commands through the server when running"
```

---

### Task 9: `tlgrm server` lifecycle commands

**Files:** Create `src/tlgrm/serverctl.py`; Modify `src/tlgrm/parser.py`, `src/tlgrm/cli.py`; Test `tests/test_serverctl.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_serverctl.py`):

```python
from tlgrm import serverctl, ipc


def test_status_reports_not_running(monkeypatch, capsys):
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)
    serverctl.status()
    out = capsys.readouterr().out
    assert '"running": false' in out.lower()


def test_status_reports_running(monkeypatch, capsys):
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    serverctl.status()
    assert '"running": true' in capsys.readouterr().out.lower()


def test_start_when_already_running_is_noop(monkeypatch, capsys):
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    spawned = {"v": False}
    monkeypatch.setattr(serverctl, "_spawn_detached", lambda: spawned.update(v=True))
    serverctl.start()
    assert spawned["v"] is False  # did not spawn a second server
```

- [ ] **Step 2: Run** → FAIL.

- [ ] **Step 3: Create `src/tlgrm/serverctl.py`:**

```python
"""CLI-side control of the background server: start (spawn detached), stop, status."""

import os
import sys
import signal
import subprocess

from . import ipc
from .output import emit
from .server.app import pid_path, serve_forever


def _spawn_detached():
    """Launch `tlgrm server start --foreground` in its own session."""
    exe = sys.argv[0]
    subprocess.Popen([exe, "server", "start", "--foreground"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def start(foreground=False):
    if foreground:
        import asyncio
        asyncio.run(serve_forever())
        return
    if ipc.is_server_running():
        emit({"success": True, "running": True, "message": "server already running"})
        return
    _spawn_detached()
    emit({"success": True, "running": True, "message": "server started"})


def stop():
    path = pid_path()
    if not os.path.exists(path):
        emit({"success": True, "running": False, "message": "server not running"})
        return
    with open(path) as f:
        pid = int(f.read().strip() or "0")
    try:
        os.kill(pid, signal.SIGTERM)
        emit({"success": True, "message": f"sent SIGTERM to {pid}"})
    except ProcessLookupError:
        os.remove(path)
        emit({"success": True, "message": "server not running (stale pid removed)"})


def status():
    emit({"success": True, "running": ipc.is_server_running()})


def restart():
    stop()
    start()
```

- [ ] **Step 4: Add the parser group** in `parser.py` (near `daemon`):

```python
    sp = sub.add_parser("server", help="Manage the background tlgrm server")
    spsub = sp.add_subparsers(dest="server_command", required=True)
    spstart = spsub.add_parser("start", help="Start the server")
    spstart.add_argument("--foreground", action="store_true",
                         help="Run in the foreground instead of detaching")
    spsub.add_parser("stop", help="Stop the server")
    spsub.add_parser("status", help="Show server status")
    spsub.add_parser("restart", help="Restart the server")
```

- [ ] **Step 5: Route it in `cli.main`** — add before the final `else`:

```python
        elif args.command == "server":
            from . import serverctl
            if args.server_command == "start":
                serverctl.start(args.foreground)
            elif args.server_command == "stop":
                serverctl.stop()
            elif args.server_command == "status":
                serverctl.status()
            elif args.server_command == "restart":
                serverctl.restart()
```

- [ ] **Step 6: Run** the full suite → PASS. Then a real smoke test:
`uv run tlgrm server status` → `{"success": true, "running": false}`

**Commit:**

```bash
git add src/tlgrm/serverctl.py src/tlgrm/parser.py src/tlgrm/cli.py tests/test_serverctl.py
git commit -m "feat(cli): tlgrm server start/stop/status/restart"
```

---

### Task 10: Docs + CHANGELOG

**Files:** Modify `docs/configuration.md`, `CHANGELOG.md`.

- [ ] **Step 1: Add a "Background server" section to `configuration.md`** explaining: what the server is (owns connections, one hot client per account, kills the deadlock), `tlgrm server start/stop/status`, that the CLI auto-routes through it when running and falls back to a direct connection otherwise, and that the socket is owner-only at `~/.tlgrm/server.sock`. Note `--session` is unnecessary once the server runs.

- [ ] **Step 2: Append to the CHANGELOG `[Unreleased]` "Added" list:**

```markdown
- **Background server + dual-mode CLI.** `tlgrm server start` runs a persistent
  process that owns one hot connection per account over an owner-only Unix
  socket. CLI commands automatically route through it when it's running (fast,
  no per-command login) and fall back to a direct connection when it isn't —
  which structurally eliminates the "database is locked" session conflict.
```

- [ ] **Step 3: Commit:**

```bash
git add docs/configuration.md CHANGELOG.md
git commit -m "docs: document the background server + dual-mode CLI"
```

---

## Self-Review Notes

- **Spec coverage:** transport §7 → T2/T7; AccountManager §6 → T4; handler + tiers §7/§15 → T3/T5; server process + lifecycle §14 → T6/T9; dual-mode routing + fallback §5 → T8; `execute` reuse (DRY engine §6) → T1; docs §20 → T10. Listener-in-server, write-guard, STT, scheduler, MCP bridge are explicitly LATER phases — not here.
- **Type consistency:** `request(rid, cmd, account, args, tier)`, `ok/err(rid, …)`, `handle_request(manager, req)`, `AccountManager.get(account)/load_all/disconnect_all`, `is_allowed(conn_tier, cmd)`, `execute(client, args)`, `ipc.is_server_running()/request_sync(cmd, account, args, tier)`, `app.socket_path()/pid_path()/start_server/stop_server/serve_forever` are used consistently across tasks.
- **Known nuance (flag to implementer):** in Task 6 the test should patch `tlgrm.server.handler.execute` (not `app.execute`); the inline note says so. `account add`/`login` always go direct (Task 8) because they create sessions / need a TTY.
