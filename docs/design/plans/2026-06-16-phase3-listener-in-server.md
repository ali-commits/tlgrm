# Phase 3 — Listener in the server + live config (0.3.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Move incoming-message listening into the server as one listener per account, driven by **persisted, live-reconfigurable** per-account config (enable/disable, webhook, and a `filter listen` allow/block list). Add the `account` field to the webhook payload.

**Architecture:** Extract the message-processing pipeline out of `webhooks.py` into a shared `listen_core.py` (filters, payload build, download/STT, forward). A new `server/listener.py` defines `ListenState` + `AccountListener` built from per-account config and rebuildable on demand. `AccountManager` owns one listener per connected account and exposes `reload_listener`. A new `reload` control command lets the CLI push config changes to a running server live. New CLI: `listen enable/disable`, `webhook set/show/clear`, `filter listen show/mode/add/remove/clear`.

**Scope / non-goals:** Listening **windows** are deferred to Phase 6 (scheduler). The **write** filter domain is Phase 4 (but the config helpers here are written domain-generic so Phase 4 reuses them). STT stays as-is (Phase 5 makes it server-hot).

**Tech Stack:** Python asyncio, Telethon events, pytest (`asyncio_mode=auto`).

**Reference:** `docs/design/2026-06-16-server-architecture-multi-account.md` §6, §9, §10, §16.

**Standing rules:** `uv` for all commands (`uv run --extra dev --extra mcp python -m pytest ...`); never pip. Don't touch the bundled-cred code in `config.py`. TDD. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Per-account listen config (accounts.py)

Per-account config lives under `[accounts.<name>]` in `config.toml`:
`listen_enabled` (bool), `webhook_url` (str), `webhook_headers` (list[str]),
and `[accounts.<name>.filter.listen]` with `mode` (`allow`|`block`) + `list`.

**Files:** Modify `src/tlgrm/accounts.py`; Test `tests/test_account_listen_config.py`.

- [ ] **Step 1: Write the failing test:**

```python
import pytest
from tlgrm import accounts


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    return tmp_path


def test_defaults(tmp_home):
    cfg = accounts.listen_config("work")
    assert cfg == {"enabled": False, "webhook_url": None, "webhook_headers": [],
                   "filter": {"mode": "block", "list": []}}


def test_set_enabled_and_webhook(tmp_home):
    accounts.set_listen_enabled("work", True)
    accounts.set_webhook("work", "https://x/y", ["A: b"])
    cfg = accounts.listen_config("work")
    assert cfg["enabled"] is True
    assert cfg["webhook_url"] == "https://x/y"
    assert cfg["webhook_headers"] == ["A: b"]
    accounts.clear_webhook("work")
    assert accounts.listen_config("work")["webhook_url"] is None


def test_filter_mode_and_list(tmp_home):
    accounts.filter_set_mode("work", "listen", "allow")
    accounts.filter_add("work", "listen", ["@a", "@b"])
    accounts.filter_add("work", "listen", ["@a"])           # dedup
    assert accounts.listen_config("work")["filter"] == {"mode": "allow", "list": ["@a", "@b"]}
    accounts.filter_remove("work", "listen", ["@a"])
    assert accounts.listen_config("work")["filter"]["list"] == ["@b"]
    accounts.filter_clear("work", "listen")
    assert accounts.listen_config("work")["filter"]["list"] == []


def test_bad_mode_raises(tmp_home):
    with pytest.raises(accounts.TlgrmError):
        accounts.filter_set_mode("work", "listen", "nonsense")
```

- [ ] **Step 2:** Run `uv run --extra dev python -m pytest tests/test_account_listen_config.py -q` → FAIL.

- [ ] **Step 3: Append to `src/tlgrm/accounts.py`:**

```python
def _account(cfg, name):
    if name not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {name!r}. See 'tlgrm account list'.")
    return cfg["accounts"][name]


def listen_config(name):
    """Normalized per-account listen settings (with defaults applied)."""
    acc = _account(load_config(), name)
    flt = (acc.get("filter") or {}).get("listen") or {}
    return {
        "enabled": bool(acc.get("listen_enabled", False)),
        "webhook_url": acc.get("webhook_url"),
        "webhook_headers": list(acc.get("webhook_headers", [])),
        "filter": {"mode": flt.get("mode", "block"), "list": list(flt.get("list", []))},
    }


def set_listen_enabled(name, enabled):
    cfg = load_config()
    _account(cfg, name)["listen_enabled"] = bool(enabled)
    save_config(cfg)


def set_webhook(name, url, headers=None):
    cfg = load_config()
    acc = _account(cfg, name)
    acc["webhook_url"] = url
    acc["webhook_headers"] = list(headers or [])
    save_config(cfg)


def clear_webhook(name):
    cfg = load_config()
    acc = _account(cfg, name)
    acc.pop("webhook_url", None)
    acc.pop("webhook_headers", None)
    save_config(cfg)


def _filter_node(acc, domain):
    return acc.setdefault("filter", {}).setdefault(domain, {})


def filter_set_mode(name, domain, mode):
    if mode not in ("allow", "block"):
        raise TlgrmError(f"Filter mode must be 'allow' or 'block', got {mode!r}.")
    cfg = load_config()
    _filter_node(_account(cfg, name), domain)["mode"] = mode
    save_config(cfg)


def filter_add(name, domain, tokens):
    cfg = load_config()
    node = _filter_node(_account(cfg, name), domain)
    lst = node.setdefault("list", [])
    for t in tokens:
        if t and t not in lst:
            lst.append(t)
    save_config(cfg)


def filter_remove(name, domain, tokens):
    cfg = load_config()
    node = _filter_node(_account(cfg, name), domain)
    node["list"] = [x for x in node.get("list", []) if x not in set(tokens)]
    save_config(cfg)


def filter_clear(name, domain):
    cfg = load_config()
    _filter_node(_account(cfg, name), domain)["list"] = []
    save_config(cfg)
```

- [ ] **Step 4:** Run the test → PASS. **Commit:**

```bash
git add src/tlgrm/accounts.py tests/test_account_listen_config.py
git commit -m "feat(accounts): per-account listen config (enable, webhook, filter)"
```

---

### Task 2: Extract shared listen core; add `account` to payload

Move the reusable pieces out of `webhooks.py` into `src/tlgrm/listen_core.py` and
have `webhooks.run_listener` reuse them. The payload gains an optional `account`.

**Files:** Create `src/tlgrm/listen_core.py`; Modify `src/tlgrm/webhooks.py`; Test `tests/test_listen_core.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_listen_core.py`):

```python
import asyncio
from tlgrm import listen_core as lc


def test_split_and_matches():
    assert lc._split_tokens(["@a,@b", "c"]) == ["@a", "@b", "c"]
    assert lc._matches({1}, set(), 1, 2, None, None) is True
    assert lc._matches(set(), {"x"}, 9, 8, "X", None) is True
    assert lc._matches({1}, {"x"}, 9, 8, "y", None) is False


def test_passes_allow_and_block():
    st = lc.ListenState()
    st.ids = {5}
    st.mode = "allow"
    assert lc._passes(st, chat_id=5, sender_id=0, cu=None, su=None) is True
    assert lc._passes(st, chat_id=9, sender_id=0, cu=None, su=None) is False
    st.mode = "block"
    assert lc._passes(st, chat_id=5, sender_id=0, cu=None, su=None) is False
    assert lc._passes(st, chat_id=9, sender_id=0, cu=None, su=None) is True
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Create `src/tlgrm/listen_core.py`** by moving `forward_webhook`, `_split_tokens`, `_resolve_filters`, `_matches` out of `webhooks.py`, and adding `ListenState`, `_passes`, `build_payload`, and `process_event`:

```python
"""Shared incoming-message pipeline: filter, build payload, download+transcribe,
forward. Used by the standalone `tlgrm listen` and the server's per-account
listeners so the two never diverge."""

import os
import json
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from telethon import utils

from .config import DOWNLOADS_DIR
from .core import serialize
from .stt import transcribe_audio

logger = logging.getLogger("tlgrm-listen")


async def forward_webhook(url, payload, headers=None, retries=3):
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, headers=headers, timeout=10.0)
            if 200 <= resp.status_code < 300:
                logger.info(f"Webhook forwarded ({resp.status_code}).")
                return
            logger.error(f"Webhook failed {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"Webhook POST to {url} failed (attempt {attempt}/{retries}): {e}")
        if attempt < retries:
            await asyncio.sleep(2 ** (attempt - 1))


def _split_tokens(values):
    tokens = []
    for value in values or []:
        tokens.extend(t.strip() for t in str(value).split(",") if t.strip())
    return tokens


async def _resolve_filters(client, tokens):
    ids, names = set(), set()
    for token in tokens:
        try:
            entity = await client.get_entity(token)
            ids.add(utils.get_peer_id(entity))
            uname = getattr(entity, "username", None)
            if uname:
                names.add(uname.lower())
        except Exception as e:
            logger.warning(f"Could not resolve filter target {token!r} ({e}); "
                           "matching literally.")
            stripped = token.lstrip("@")
            if stripped.lstrip("-").isdigit():
                ids.add(int(stripped))
            else:
                names.add(stripped.lower())
    return ids, names


def _matches(ids, names, chat_id, sender_id, chat_username, sender_username):
    if chat_id in ids or sender_id in ids:
        return True
    return any(u and u.lower() in names for u in (chat_username, sender_username))


class ListenState:
    """Live, swappable listening config for one account."""
    def __init__(self):
        self.enabled = False
        self.webhook_url = None
        self.headers = {}
        self.mode = "block"      # allow | block
        self.ids = set()
        self.names = set()


def _passes(state, chat_id, sender_id, cu, su):
    matched = _matches(state.ids, state.names, chat_id, sender_id, cu, su)
    return matched if state.mode == "allow" else not matched


async def build_payload(event, account=None):
    """Build the webhook JSON payload for an incoming message (incl. media
    download + transcription). `account` is {"name","id"} or None (standalone)."""
    msg = event.message
    chat = await event.get_chat()
    sender = await event.get_sender()
    sender_info = serialize.serialize_sender(sender)
    chat_type = ("user" if event.is_private else "group" if event.is_group
                 else "channel" if event.is_channel else "unknown")
    chat_info = serialize.serialize_chat(chat, chat_type)
    chat_info["id"] = event.chat_id

    media = {"present": False, "type": None, "local_path": None,
             "transcription": None, "self_destruct": False}
    if msg.media:
        media["present"] = True
        media["type"] = serialize.media_type(msg)
        if serialize.is_self_destruct(msg):
            media["self_destruct"] = True
        else:
            try:
                path = await msg.download_media(file=DOWNLOADS_DIR)
                if path:
                    media["local_path"] = os.path.abspath(path)
                    if media["type"] in ("voice", "audio"):
                        text = transcribe_audio(media["local_path"])
                        if text:
                            media["transcription"] = text
            except Exception as ex:
                logger.error(f"Media download/transcribe failed: {ex}")

    payload = {
        "event": "new_message",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message": {"id": msg.id, "text": msg.text or "",
                    "date": msg.date.isoformat() if msg.date else "",
                    "reply_to_msg_id": msg.reply_to_msg_id},
        "chat": chat_info, "sender": sender_info, "media": media,
    }
    if account is not None:
        payload["account"] = account
    return payload


async def process_event(event, state, account=None, pending=None, emit_console=False):
    """Filter, build, and forward one incoming message according to `state`."""
    chat = await event.get_chat()
    sender = await event.get_sender()
    cu = getattr(chat, "username", None)
    su = getattr(sender, "username", None)
    if not _passes(state, event.chat_id, event.sender_id, cu, su):
        return
    payload = await build_payload(event, account)
    if emit_console or not state.webhook_url:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    if state.webhook_url:
        loop = asyncio.get_event_loop()
        task = loop.create_task(forward_webhook(state.webhook_url, payload, state.headers))
        if pending is not None:
            pending.add(task)
            task.add_done_callback(pending.discard)
```

- [ ] **Step 4: Rewrite `webhooks.run_listener` to use `listen_core`.** Replace the body so it builds a `ListenState` from the `only/ignore`/`webhook` args and registers a handler that calls `listen_core.process_event`. Keep the module's `logging.basicConfig(... stderr ...)` and `preload()` call. Concretely, `webhooks.py` becomes:

```python
import sys
import asyncio
import logging

from telethon import events

from .core.client import get_client, ensure_authorized
from .core.errors import NotAuthorizedError
from .stt import preload
from . import listen_core
from . import accounts

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stderr)])
logger = logging.getLogger("tlgrm-webhook")


def _parse_headers(header_list):
    out = {}
    for h in header_list or []:
        if ":" in h:
            k, v = h.split(":", 1)
            out[k.strip()] = v.strip()
    return out


async def run_listener(webhook_url=None, webhook_headers=None, verbose=False,
                       only=None, ignore=None):
    if verbose:
        logger.setLevel(logging.DEBUG)
    client = get_client()
    try:
        await ensure_authorized(client)
    except NotAuthorizedError as e:
        logger.error(str(e))
        await client.disconnect()
        return

    # Standalone listener: --only is an allow-list, --ignore a block-list. We
    # support both by resolving two sets and combining in a small state shim.
    only_ids, only_names = await listen_core._resolve_filters(client, listen_core._split_tokens(only))
    ignore_ids, ignore_names = await listen_core._resolve_filters(client, listen_core._split_tokens(ignore))

    state = listen_core.ListenState()
    state.webhook_url = webhook_url
    state.headers = _parse_headers(webhook_headers)

    preload()
    me = await client.get_me()
    account = {"name": accounts.load_config().get("default_account") or "default", "id": me.id}
    pending = set()

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        try:
            chat = await event.get_chat()
            sender = await event.get_sender()
            cu = getattr(chat, "username", None)
            su = getattr(sender, "username", None)
            if (only_ids or only_names) and not listen_core._matches(
                    only_ids, only_names, event.chat_id, event.sender_id, cu, su):
                return
            if listen_core._matches(ignore_ids, ignore_names,
                                    event.chat_id, event.sender_id, cu, su):
                return
            await listen_core.process_event(event, state, account=account,
                                            pending=pending, emit_console=verbose)
        except Exception as e:
            logger.error(f"Error in message handler: {e}")

    logger.info(f"Listening as {me.first_name} [ID: {me.id}].")
    await client.run_until_disconnected()
```

- [ ] **Step 5:** Run the FULL suite `uv run --extra dev --extra mcp python -m pytest -q` → PASS. The existing `tests/test_listen_filters.py` imports `webhooks._split_tokens`, `webhooks._matches`, `webhooks._resolve_filters`, `webhooks.ListenState`? — CHECK: those tests reference `webhooks._split_tokens`, `webhooks._matches`, `webhooks._resolve_filters`. Keep backward-compat re-exports in `webhooks.py` so those tests still pass: add at the end of `webhooks.py`:

```python
# Back-compat re-exports (tests and external callers used these names).
_split_tokens = listen_core._split_tokens
_resolve_filters = listen_core._resolve_filters
_matches = listen_core._matches
```

Re-run the suite → PASS. **Commit:**

```bash
git add src/tlgrm/listen_core.py src/tlgrm/webhooks.py tests/test_listen_core.py
git commit -m "refactor(listen): shared listen_core + account field in payload"
```

---

### Task 3: `AccountListener` + `ListenState` from config (server/listener.py)

**Files:** Create `src/tlgrm/server/listener.py`; Test `tests/test_account_listener.py`.

- [ ] **Step 1: Write the failing test:**

```python
import asyncio
import pytest
from tlgrm.server.listener import AccountListener


class _FakeClient:
    def __init__(self): self.handlers = []
    def on(self, _event):
        def deco(fn): self.handlers.append(fn); return fn
        return deco
    def remove_event_handler(self, fn): self.handlers.remove(fn)
    async def get_me(self):
        return type("Me", (), {"id": 777})()
    async def get_entity(self, token): raise ValueError("unresolved")


@pytest.mark.asyncio
async def test_reload_builds_state_from_config(monkeypatch):
    monkeypatch.setattr("tlgrm.accounts.listen_config", lambda name: {
        "enabled": True, "webhook_url": "https://x", "webhook_headers": ["A: b"],
        "filter": {"mode": "allow", "list": ["123", "@foo"]}})
    c = _FakeClient()
    lis = AccountListener(c, "work")
    await lis.reload()
    assert lis.state.enabled is True
    assert lis.state.webhook_url == "https://x"
    assert lis.state.headers == {"A": "b"}
    assert lis.state.mode == "allow"
    assert 123 in lis.state.ids and "foo" in lis.state.names
    assert lis.account_obj == {"name": "work", "id": 777}


@pytest.mark.asyncio
async def test_start_registers_one_handler_and_stop_removes(monkeypatch):
    monkeypatch.setattr("tlgrm.accounts.listen_config", lambda name: {
        "enabled": True, "webhook_url": None, "webhook_headers": [],
        "filter": {"mode": "block", "list": []}})
    c = _FakeClient()
    lis = AccountListener(c, "work")
    await lis.reload()
    lis.start()
    assert len(c.handlers) == 1
    lis.start()                      # idempotent
    assert len(c.handlers) == 1
    lis.stop()
    assert c.handlers == []
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Create `src/tlgrm/server/listener.py`:**

```python
"""One incoming-message listener per account, bound to the account's hot client.
State is rebuilt from persisted config on `reload()`."""

import logging

from telethon import events

from .. import listen_core

logger = logging.getLogger("tlgrm-server")


def _parse_headers(header_list):
    out = {}
    for h in header_list or []:
        if ":" in h:
            k, v = h.split(":", 1)
            out[k.strip()] = v.strip()
    return out


class AccountListener:
    def __init__(self, client, account_name):
        self.client = client
        self.account = account_name
        self.state = listen_core.ListenState()
        self.account_obj = {"name": account_name, "id": None}
        self._handler = None
        self._pending = set()

    async def reload(self):
        """Rebuild listen state (enabled, webhook, filters) from config."""
        from .. import accounts
        cfg = accounts.listen_config(self.account)
        st = listen_core.ListenState()
        st.enabled = cfg["enabled"]
        st.webhook_url = cfg["webhook_url"]
        st.headers = _parse_headers(cfg["webhook_headers"])
        st.mode = cfg["filter"]["mode"]
        st.ids, st.names = await listen_core._resolve_filters(
            self.client, cfg["filter"]["list"])
        self.state = st
        if self.account_obj["id"] is None:
            me = await self.client.get_me()
            self.account_obj = {"name": self.account, "id": me.id}

    def start(self):
        if self._handler is not None:
            return

        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event):
            if not self.state.enabled:
                return
            try:
                await listen_core.process_event(
                    event, self.state, account=self.account_obj, pending=self._pending)
            except Exception as e:
                logger.error(f"[{self.account}] listener error: {e}")

        self._handler = handler

    def stop(self):
        if self._handler is not None:
            self.client.remove_event_handler(self._handler)
            self._handler = None
```

- [ ] **Step 4:** Run → PASS. **Commit:**

```bash
git add src/tlgrm/server/listener.py tests/test_account_listener.py
git commit -m "feat(server): per-account AccountListener built from config"
```

---

### Task 4: AccountManager owns listeners

**Files:** Modify `src/tlgrm/server/manager.py`; Test append to `tests/test_manager.py`.

- [ ] **Step 1: Append the failing test:**

```python
def test_manager_starts_and_reloads_listener(monkeypatch):
    class _FakeClient:
        def on(self, _e):
            def deco(fn): return fn
            return deco
        def remove_event_handler(self, fn): pass
        async def connect(self): pass
        async def is_user_authorized(self): return True
        async def disconnect(self): pass
        async def get_me(self): return type("Me", (), {"id": 1})()
        async def get_entity(self, t): raise ValueError("x")

    import tlgrm.core.client as cc
    monkeypatch.setattr(cc, "get_client", lambda account=None, must_exist=True: _FakeClient())
    monkeypatch.setattr("tlgrm.accounts.resolve_account", lambda name=None: name or "default")
    monkeypatch.setattr("tlgrm.accounts.listen_config", lambda name: {
        "enabled": True, "webhook_url": None, "webhook_headers": [],
        "filter": {"mode": "block", "list": []}})

    async def go():
        m = AccountManager()
        await m.get("work")
        lis = await m.start_listener("work")
        assert lis is m._listeners["work"]
        await m.reload_listener("work")     # should not raise
    __import__("asyncio").run(go())
```

- [ ] **Step 2:** Run `uv run --extra dev python -m pytest tests/test_manager.py -q` → FAIL.

- [ ] **Step 3: Modify `src/tlgrm/server/manager.py`** — add a `_listeners` dict and three methods, and start listeners in `load_all`:

```python
# in __init__:
        self._listeners = {}  # account name -> AccountListener

# new methods:
    async def start_listener(self, account=None):
        from ..accounts import resolve_account
        from .listener import AccountListener
        name = resolve_account(account)
        client = await self.get(name)
        if name not in self._listeners:
            lis = AccountListener(client, name)
            await lis.reload()
            lis.start()
            self._listeners[name] = lis
        return self._listeners[name]

    async def reload_listener(self, account=None):
        from ..accounts import resolve_account
        name = resolve_account(account)
        if name in self._listeners:
            await self._listeners[name].reload()
        else:
            await self.start_listener(name)
```

And in `load_all`, after a successful `await self.get(name)`, also start the listener:

```python
            try:
                await self.get(name)
                await self.start_listener(name)
                logger.info(f"Connected account '{name}'.")
            except Exception as e:
                logger.warning(f"Skipping account '{name}': {e}")
```

In `disconnect_all`, stop listeners first:

```python
    async def disconnect_all(self):
        for lis in self._listeners.values():
            try:
                lis.stop()
            except Exception:
                pass
        self._listeners.clear()
        for c in self._clients.values():
            ...
```

- [ ] **Step 4:** Run `uv run --extra dev python -m pytest tests/test_manager.py -q` → PASS. **Commit:**

```bash
git add src/tlgrm/server/manager.py tests/test_manager.py
git commit -m "feat(server): manager owns per-account listeners (start/reload/stop)"
```

---

### Task 5: `reload` control command in the handler

**Files:** Modify `src/tlgrm/server/handler.py`, `src/tlgrm/server/tiers.py`; Test append to `tests/test_handler.py`.

- [ ] **Step 1: Append the failing test:**

```python
def test_reload_control_command():
    class _M:
        def __init__(self): self.reloaded = None
        async def reload_listener(self, account=None): self.reloaded = account
        async def get(self, account=None): raise AssertionError("not a telegram op")
    m = _M()
    out = asyncio.run(handler.handle_request(
        m, {"id": 7, "cmd": "reload", "account": "work", "tier": "read"}))
    assert out["ok"] and out["data"] == {"reloaded": "work"}
    assert m.reloaded == "work"
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3:** Add `"reload": "read"` to `COMMAND_TIERS` in `tiers.py` (it's a benign control op — the user already wrote the config). Then in `handler.py`, handle it as a control command BEFORE the `manager.get`/execute path (right after the `ping` shortcut):

```python
    if cmd == "reload":
        if not is_allowed(req.get("tier", "read"), "reload"):
            return err(rid, "PermissionError", "'reload' requires a higher tier")
        await manager.reload_listener(req.get("account"))
        return ok(rid, {"reloaded": req.get("account")})
```

(Placed before the generic tier check / execute so `reload` never reaches `execute`, which doesn't know it.)

- [ ] **Step 4:** Run `uv run --extra dev python -m pytest tests/test_handler.py tests/test_tiers.py -q` → PASS. **Commit:**

```bash
git add src/tlgrm/server/handler.py src/tlgrm/server/tiers.py tests/test_handler.py
git commit -m "feat(server): reload control command to apply config live"
```

---

### Task 6: CLI — `listen enable/disable`, `webhook`, `filter listen`

These write persisted config and, if a server is running, send `reload` so the
change applies live.

**Files:** Create `src/tlgrm/listenctl.py`; Modify `src/tlgrm/parser.py`, `src/tlgrm/cli.py`; Test `tests/test_listenctl.py`.

- [ ] **Step 1: Write the failing test:**

```python
import pytest
from tlgrm import listenctl, accounts, ipc


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)  # no live push
    return tmp_path


def test_enable_disable(tmp_home, capsys):
    listenctl.set_enabled("work", True)
    assert accounts.listen_config("work")["enabled"] is True
    assert '"enabled": true' in capsys.readouterr().out.lower()
    listenctl.set_enabled("work", False)
    assert accounts.listen_config("work")["enabled"] is False


def test_webhook_set_show_clear(tmp_home, capsys):
    listenctl.webhook_set("work", "https://x", ["A: b"])
    assert accounts.listen_config("work")["webhook_url"] == "https://x"
    listenctl.webhook_clear("work")
    assert accounts.listen_config("work")["webhook_url"] is None


def test_filter_ops_and_live_push(tmp_home, monkeypatch):
    pushed = {}
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    monkeypatch.setattr(ipc, "request_sync",
                        lambda cmd, account=None, **k: pushed.update(cmd=cmd, account=account)
                        or {"ok": True, "data": {}})
    listenctl.filter_cmd("work", "listen", "mode", value="allow")
    listenctl.filter_cmd("work", "listen", "add", tokens=["@a"])
    assert accounts.listen_config("work")["filter"] == {"mode": "allow", "list": ["@a"]}
    assert pushed == {"cmd": "reload", "account": "work"}   # pushed live
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Create `src/tlgrm/listenctl.py`:**

```python
"""CLI-side handlers for live listen configuration. Each writes persisted config
and, if a server is running, pushes a `reload` so the change applies live."""

from . import accounts, ipc
from .output import emit


def _push_reload(account):
    if ipc.is_server_running():
        ipc.request_sync("reload", account=account, args={}, tier="read")


def set_enabled(account, enabled):
    accounts.set_listen_enabled(account, enabled)
    _push_reload(account)
    emit({"success": True, "account": account, "enabled": bool(enabled)})


def webhook_set(account, url, headers=None):
    accounts.set_webhook(account, url, headers)
    _push_reload(account)
    emit({"success": True, "account": account, "webhook_url": url})


def webhook_clear(account):
    accounts.clear_webhook(account)
    _push_reload(account)
    emit({"success": True, "account": account, "webhook_url": None})


def webhook_show(account):
    cfg = accounts.listen_config(account)
    emit({"success": True, "account": account, "webhook_url": cfg["webhook_url"],
          "webhook_headers": cfg["webhook_headers"]})


def filter_cmd(account, domain, op, value=None, tokens=None):
    if op == "show":
        emit({"success": True, "account": account, "domain": domain,
              "filter": accounts.listen_config(account)["filter"]})
        return
    if op == "mode":
        accounts.filter_set_mode(account, domain, value)
    elif op == "add":
        accounts.filter_add(account, domain, tokens or [])
    elif op == "remove":
        accounts.filter_remove(account, domain, tokens or [])
    elif op == "clear":
        accounts.filter_clear(account, domain)
    _push_reload(account)
    emit({"success": True, "account": account, "domain": domain,
          "filter": accounts.listen_config(account)["filter"]})
```

- [ ] **Step 4: Parser** — add to `parser.py`:

```python
    lp = sub.add_parser("listen-config", help="(internal) reserved")  # placeholder removed below
```

Replace that placeholder: actually add the real groups. Add a `listen` management group is awkward because `listen` already exists as the foreground command. KEEP the existing `listen` command, and add SEPARATE top-level verbs: `webhook` and `filter`, plus `listen enable/disable` via subcommands on a NEW `listen` — but `listen` is already a leaf command. To avoid conflict, add the enable/disable under the existing `listen` is not possible (it has no subparsers). Instead, add a small `listening` group? Simpler and matches the spec command surface: keep `tlgrm listen` (foreground) AND add these management commands:

```python
    # listen enable/disable (account listening on/off)
    lsp = sub.add_parser("listening", help="Enable/disable listening for an account")
    lssub = lsp.add_subparsers(dest="listening_command", required=True)
    lssub.add_parser("enable", help="Enable listening for the account")
    lssub.add_parser("disable", help="Disable listening for the account")

    wp = sub.add_parser("webhook", help="Configure the account's webhook")
    wsub = wp.add_subparsers(dest="webhook_command", required=True)
    wset = wsub.add_parser("set", help="Set the webhook URL")
    wset.add_argument("url")
    wset.add_argument("--header", action="append", dest="headers")
    wsub.add_parser("show", help="Show the webhook")
    wsub.add_parser("clear", help="Clear the webhook")

    fp = sub.add_parser("filter", help="Configure listen/write filters")
    fpsub = fp.add_subparsers(dest="filter_domain", required=True)
    for _domain in ("listen",):   # "write" added in Phase 4
        dpar = fpsub.add_parser(_domain, help=f"{_domain} filter")
        dsub = dpar.add_subparsers(dest="filter_op", required=True)
        dsub.add_parser("show")
        dmode = dsub.add_parser("mode"); dmode.add_argument("mode", choices=["allow", "block"])
        dadd = dsub.add_parser("add"); dadd.add_argument("targets", nargs="+")
        drem = dsub.add_parser("remove"); drem.add_argument("targets", nargs="+")
        dsub.add_parser("clear")
```

(Remove the placeholder `listen-config` line — do not include it.)

- [ ] **Step 5: cli.py routing** — add branches (account resolved from `args.account`):

```python
        elif args.command == "listening":
            from . import listenctl
            listenctl.set_enabled(args.account or _default_account(),
                                  args.listening_command == "enable")
        elif args.command == "webhook":
            from . import listenctl
            acc = args.account or _default_account()
            if args.webhook_command == "set":
                listenctl.webhook_set(acc, args.url, args.headers)
            elif args.webhook_command == "show":
                listenctl.webhook_show(acc)
            elif args.webhook_command == "clear":
                listenctl.webhook_clear(acc)
        elif args.command == "filter":
            from . import listenctl
            acc = args.account or _default_account()
            tokens = getattr(args, "targets", None)
            value = getattr(args, "mode", None)
            from .listen_core import _split_tokens
            listenctl.filter_cmd(acc, args.filter_domain, args.filter_op,
                                 value=value, tokens=_split_tokens(tokens))
```

Add a helper near the top of `cli.py`:

```python
def _default_account():
    from .accounts import load_config
    return load_config().get("default_account") or "default"
```

- [ ] **Step 6:** Run the new test and the FULL suite → PASS. Smoke:
`uv run tlgrm account add` is interactive — instead smoke the config path:
`uv run tlgrm -a default filter listen show` should print JSON (after a default account exists; on a fresh CI box it errors cleanly with "No such account", which is fine).

**Commit:**

```bash
git add src/tlgrm/listenctl.py src/tlgrm/parser.py src/tlgrm/cli.py tests/test_listenctl.py
git commit -m "feat(cli): live listen config — listening/webhook/filter commands"
```

---

### Task 7: Docs + CHANGELOG

**Files:** Modify `docs/configuration.md` (or `docs/webhook-guide.md`), `CHANGELOG.md`.

- [ ] **Step 1:** Document per-account listening: `tlgrm listening enable/disable`,
`tlgrm webhook set/show/clear`, `tlgrm filter listen show/mode/add/remove/clear`,
that they apply live when the server is running, and that the webhook payload now
carries an `account` field. Note windows are not yet available (coming with the
scheduler).

- [ ] **Step 2:** Append to CHANGELOG `[Unreleased]` "Added":

```markdown
- **Server-side per-account listening with live config.** With the server
  running, each account can listen for incoming messages independently. Configure
  it live (no restart): `tlgrm listening enable/disable`, `tlgrm webhook
  set/show/clear`, and `tlgrm filter listen show/mode/add/remove/clear` (an
  allow/block list matched by chat or sender). The webhook payload now includes
  an `account` field identifying which account received the message.
```

- [ ] **Step 3: Commit:**

```bash
git add docs/configuration.md CHANGELOG.md
git commit -m "docs: per-account listening + live filter/webhook config"
```

---

## Self-Review Notes

- **Spec coverage:** per-account config §9 → T1; payload `account` §16 → T2; server per-account listener §6 → T3/T4; live reconfig §10 → T5/T6. Write-guard (§10 write domain) is Phase 4 — only the `listen` domain is wired (T6 leaves a clear seam for `write`). Windows (§12) deferred to Phase 6 (noted).
- **Type consistency:** `listen_config(name)` shape (`enabled/webhook_url/webhook_headers/filter{mode,list}`) is produced in T1 and consumed in T3/T6; `filter_*(name, domain, …)` signatures match across T1/T6; `AccountListener(client, name).reload()/start()/stop()` used in T3/T4; `reload` control cmd in T5 matches the `ipc.request_sync("reload", account=…)` push in T6.
- **Back-compat:** `webhooks._split_tokens/_matches/_resolve_filters` re-exported (T2) so `tests/test_listen_filters.py` stays green; `tlgrm listen` foreground unchanged in behavior.
