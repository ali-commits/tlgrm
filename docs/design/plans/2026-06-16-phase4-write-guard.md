# Phase 4 — Write guard (`filter write`) (0.3.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** The second half of the per-contact permission matrix: a per-account **write filter** that decides which targets the tool may *send to*. A blocked outgoing action fails fast with a clear `PermissionError` and never touches Telegram. Enforced for both the direct CLI path and the server.

**Architecture:** Reuse Phase 3's domain-generic `filter_*` config helpers (they already accept a `domain`). Add `accounts.filter_config(name, domain)`. A small `write_guard.py` extracts the write target for a command and checks it against the account's `write` filter (allow/block). `execute(client, args, account)` calls the guard before any write op. The `filter` CLI grammar gains the `write` domain (the routing is already domain-generic).

**Scope / non-goals:** STT-hot (Phase 5), scheduler/windows (Phase 6), MCP bridge (Phase 7). The guard matches the target **as written** (normalized `@name`/id), not by network entity resolution — predictable and offline.

**Reference:** `docs/design/2026-06-16-server-architecture-multi-account.md` §10, §17.

**Standing rules:** `uv` for all commands (`uv run --extra dev --extra mcp python -m pytest ...`); never pip. Don't touch the bundled-cred code in `config.py`. TDD. Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Generic `filter_config(name, domain)` + domain-correct CLI show

**Files:** Modify `src/tlgrm/accounts.py`, `src/tlgrm/listenctl.py`; Test `tests/test_filter_config.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_filter_config.py`):

```python
import pytest
from tlgrm import accounts, listenctl, ipc


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)
    return tmp_path


def test_filter_config_defaults_and_isolation(tmp_home):
    assert accounts.filter_config("work", "write") == {"mode": "block", "list": []}
    accounts.filter_add("work", "write", ["@a"])
    accounts.filter_set_mode("work", "write", "allow")
    assert accounts.filter_config("work", "write") == {"mode": "allow", "list": ["@a"]}
    # listen domain is independent
    assert accounts.filter_config("work", "listen") == {"mode": "block", "list": []}


def test_listenctl_show_is_domain_correct(tmp_home, capsys):
    accounts.filter_add("work", "write", ["@boss"])
    listenctl.filter_cmd("work", "write", "show")
    out = capsys.readouterr().out
    assert "@boss" in out and '"domain": "write"' in out.lower()
```

- [ ] **Step 2:** Run `uv run --extra dev python -m pytest tests/test_filter_config.py -q` → FAIL.

- [ ] **Step 3: In `src/tlgrm/accounts.py`,** add `filter_config` and make `listen_config` reuse it. Add:

```python
def filter_config(name, domain):
    """Normalized {mode, list} for a filter domain ('listen' or 'write')."""
    acc = _account(load_config(), name)
    flt = (acc.get("filter") or {}).get(domain) or {}
    return {"mode": flt.get("mode", "block"), "list": list(flt.get("list", []))}
```

Then change the `filter` line inside `listen_config` to delegate:

```python
    return {
        "enabled": bool(acc.get("listen_enabled", False)),
        "webhook_url": acc.get("webhook_url"),
        "webhook_headers": list(acc.get("webhook_headers", [])),
        "filter": filter_config(name, "listen"),
    }
```

(`listen_config` already loads `acc`; keep that, just replace the inline filter dict with the `filter_config(name, "listen")` call.)

- [ ] **Step 4: In `src/tlgrm/listenctl.py`,** change `filter_cmd` to read the domain's own filter for both `show` and the final emit. Replace the two `accounts.listen_config(account)["filter"]` references with `accounts.filter_config(account, domain)`:

```python
def filter_cmd(account, domain, op, value=None, tokens=None):
    if op == "show":
        emit({"success": True, "account": account, "domain": domain,
              "filter": accounts.filter_config(account, domain)})
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
          "filter": accounts.filter_config(account, domain)})
```

- [ ] **Step 5:** Run the FULL suite `uv run --extra dev --extra mcp python -m pytest -q` → PASS (the existing `test_account_listen_config.py` still passes since `listen_config` output is unchanged). **Commit:**

```bash
git add src/tlgrm/accounts.py src/tlgrm/listenctl.py tests/test_filter_config.py
git commit -m "feat(accounts): generic filter_config(domain); domain-correct filter show"
```

---

### Task 2: Write-guard module

**Files:** Create `src/tlgrm/write_guard.py`; Test `tests/test_write_guard.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_write_guard.py`):

```python
import types
import pytest
from tlgrm import write_guard, accounts


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    return tmp_path


def test_write_target_extraction():
    assert write_guard.write_target("send", types.SimpleNamespace(target="@x")) == "@x"
    assert write_guard.write_target("forward",
        types.SimpleNamespace(to_chat="@y")) == "@y"
    assert write_guard.write_target("chats", types.SimpleNamespace()) is None
    assert write_guard.write_target("whoami", types.SimpleNamespace()) is None


def test_block_mode_blocks_listed(tmp_home):
    accounts.filter_add("work", "write", ["@boss"])  # mode defaults to block
    with pytest.raises(PermissionError):
        write_guard.check_write("work", "send", types.SimpleNamespace(target="@boss"))
    # everyone else is allowed
    write_guard.check_write("work", "send", types.SimpleNamespace(target="@other"))


def test_allow_mode_blocks_unlisted(tmp_home):
    accounts.filter_set_mode("work", "write", "allow")
    accounts.filter_add("work", "write", ["123"])
    write_guard.check_write("work", "send", types.SimpleNamespace(target="123"))
    with pytest.raises(PermissionError):
        write_guard.check_write("work", "send", types.SimpleNamespace(target="@nope"))


def test_no_target_and_unknown_account_are_noops(tmp_home):
    write_guard.check_write("work", "chats", types.SimpleNamespace())     # no target
    write_guard.check_write(None, "send", types.SimpleNamespace(target="@x"))  # no account


def test_matching_is_normalized(tmp_home):
    accounts.filter_add("work", "write", ["@Boss"])
    with pytest.raises(PermissionError):
        write_guard.check_write("work", "send", types.SimpleNamespace(target="boss"))
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: Create `src/tlgrm/write_guard.py`:**

```python
"""Outgoing-message permission guard. Before a write op runs, check its target
against the account's `write` filter and raise PermissionError if blocked. The
target is matched as written (normalized @name/id) — no network resolution."""

from . import accounts

# Commands that send/post to a target, and which arg holds that target.
_WRITE_TARGET = {
    "send": "target", "reply": "target", "edit": "target", "react": "target",
    "pin": "target", "schedule": "target", "poll": "target",
    "forward": "to_chat",
}


def write_target(cmd, args):
    """The target a write command acts on, or None if the command isn't a
    guarded write (e.g. reads, or `saved` which always goes to yourself)."""
    field = _WRITE_TARGET.get(cmd)
    return getattr(args, field, None) if field else None


def _norm(token):
    return str(token).lstrip("@").lower()


def check_write(account, cmd, args):
    """Raise PermissionError if the account's write filter blocks this target."""
    target = write_target(cmd, args)
    if target is None:
        return
    try:
        name = accounts.resolve_account(account)
    except Exception:
        return  # no account context → nothing to scope a guard to
    flt = accounts.filter_config(name, "write")
    matched = _norm(target) in {_norm(t) for t in flt["list"]}
    blocked = matched if flt["mode"] == "block" else not matched
    if blocked:
        raise PermissionError(
            f"Writing to {target!r} is blocked by account '{name}'s write filter "
            f"(mode={flt['mode']}).")
```

- [ ] **Step 4:** Run → PASS. **Commit:**

```bash
git add src/tlgrm/write_guard.py tests/test_write_guard.py
git commit -m "feat(write-guard): per-account outgoing permission check"
```

---

### Task 3: Enforce the guard in `execute` (both paths)

**Files:** Modify `src/tlgrm/execute.py`, `src/tlgrm/dispatch.py`, `src/tlgrm/server/handler.py`; Test `tests/test_execute_guard.py`.

- [ ] **Step 1: Write the failing test** (`tests/test_execute_guard.py`):

```python
import types
import asyncio
import pytest
from tlgrm import execute as ex, accounts


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    return tmp_path


def test_execute_blocks_guarded_write(tmp_home):
    accounts.filter_add("work", "write", ["@boss"])
    args = types.SimpleNamespace(command="send", target="@boss", text="hi",
                                 file=None, caption=None, voice=False,
                                 reply_to=None, silent=False)
    with pytest.raises(PermissionError):
        asyncio.run(ex.execute(object(), args, account="work"))


def test_execute_allows_unguarded_target(tmp_home, monkeypatch):
    sent = {}
    class _Msgs:
        async def send(self, client, target, **kw): sent["target"] = target; return {"id": 1}
    monkeypatch.setattr(ex, "messages", _Msgs())
    args = types.SimpleNamespace(command="send", target="@ok", text="hi",
                                 file=None, caption=None, voice=False,
                                 reply_to=None, silent=False)
    out = asyncio.run(ex.execute(object(), args, account="work"))
    assert out["success"] and sent["target"] == "@ok"
```

- [ ] **Step 2:** Run → FAIL.

- [ ] **Step 3: In `src/tlgrm/execute.py`,** change the signature and add the guard call at the very top of `execute`:

```python
async def execute(client, args, account=None):
    """Run one command against a connected client; return its result dict."""
    from .write_guard import check_write
    check_write(account, args.command, args)
    cmd = args.command
    if cmd == "chats":
        ...
```

(Everything below the `cmd = args.command` line is unchanged.)

- [ ] **Step 4: Update the two callers** to pass the account:
  - `src/tlgrm/dispatch.py` — in `run_command`, change `emit(await execute(client, args))` to `emit(await execute(client, args, account=account))` (the `account` local already exists at the top of `run_command`).
  - `src/tlgrm/server/handler.py` — change `data = await execute(client, args)` to `data = await execute(client, args, account=req.get("account"))`.

- [ ] **Step 5:** Run the new test then the FULL suite → PASS. (Existing `test_handler.py::test_executes_command` monkeypatches `handler.execute`, so it's unaffected; `test_execute.py` calls `execute(object(), args)` with no account → guard is a no-op for `chats`.) **Commit:**

```bash
git add src/tlgrm/execute.py src/tlgrm/dispatch.py src/tlgrm/server/handler.py tests/test_execute_guard.py
git commit -m "feat(execute): enforce write guard before outgoing ops"
```

---

### Task 4: `filter write` CLI surface

**Files:** Modify `src/tlgrm/parser.py`; Test append to `tests/test_cli_parser.py`.

- [ ] **Step 1: Append the failing test** to `tests/test_cli_parser.py`:

```python
def test_filter_write_subcommands():
    parser = build_parser()
    args = parser.parse_args(["filter", "write", "add", "@boss"])
    assert args.filter_domain == "write" and args.filter_op == "add"
    assert args.targets == ["@boss"]
    args = parser.parse_args(["filter", "write", "mode", "allow"])
    assert args.mode == "allow"
```

- [ ] **Step 2:** Run `uv run --extra dev python -m pytest tests/test_cli_parser.py -q -k filter_write` → FAIL.

- [ ] **Step 3: In `src/tlgrm/parser.py`,** the `filter` group currently builds only the `listen` domain. Generalize it to build both `listen` and `write` with identical grammar. Replace the single-domain block:

```python
    fp = sub.add_parser("filter", help="Configure listen/write filters")
    fpsub = fp.add_subparsers(dest="filter_domain", required=True)
    for _domain in ("listen", "write"):
        dpar = fpsub.add_parser(_domain, help=f"{_domain} filter (allow/block list)")
        dsub = dpar.add_subparsers(dest="filter_op", required=True)
        dsub.add_parser("show")
        dmode = dsub.add_parser("mode")
        dmode.add_argument("mode", choices=["allow", "block"])
        dadd = dsub.add_parser("add")
        dadd.add_argument("targets", nargs="+")
        drem = dsub.add_parser("remove")
        drem.add_argument("targets", nargs="+")
        dsub.add_parser("clear")
```

(The `cli.py` `filter` branch is already domain-generic — it passes `args.filter_domain` straight through — so no cli.py change is needed.)

- [ ] **Step 4:** Run the test + full suite → PASS. Smoke: `uv run tlgrm filter write --help` lists `{show,mode,add,remove,clear}`. **Commit:**

```bash
git add src/tlgrm/parser.py tests/test_cli_parser.py
git commit -m "feat(cli): filter write subcommands (write guard config)"
```

---

### Task 5: Docs + CHANGELOG

**Files:** Modify `docs/configuration.md`, `CHANGELOG.md`.

- [ ] **Step 1:** In `configuration.md`, next to the listen-filter docs, document the write filter: `tlgrm -a work filter write mode allow|block`, `add/remove/clear/show`, that a blocked target makes write commands (send/reply/edit/forward/react/pin/schedule/poll) fail with a permission error before contacting Telegram, and that together with `filter listen` it forms a per-contact listen×write permission matrix. Note it applies in both direct and server mode and takes effect immediately (read fresh per command).

- [ ] **Step 2:** Append to CHANGELOG `[Unreleased]` "Added":

```markdown
- **Per-account write guard (`filter write`).** Restrict which chats/users an
  account may message: `tlgrm filter write mode allow|block` + `add/remove/clear`.
  Blocked targets make outgoing commands (send, reply, edit, forward, react, pin,
  schedule, poll) fail fast — before anything is sent. Combined with `filter
  listen`, this gives a full per-contact listen×write permission matrix.
```

- [ ] **Step 3: Commit:**

```bash
git add docs/configuration.md CHANGELOG.md
git commit -m "docs: write guard (filter write) + permission matrix"
```

---

## Self-Review Notes

- **Spec coverage:** write filter §10 → T2/T3/T4; config reuse §9 → T1; server-side + direct enforcement §17 → T3. STT/scheduler/MCP are later phases — absent.
- **Type consistency:** `filter_config(name, domain)` (T1) is consumed by `write_guard.check_write` (T2) and `listenctl.filter_cmd` (T1); `execute(client, args, account)` (T3) matches both call sites; `write_target`/`check_write(account, cmd, args)` signatures consistent T2↔T3.
- **No-op safety:** guard is skipped for non-write commands, `saved` (→ self), and when no account resolves — so reads and the existing test suite are unaffected.
