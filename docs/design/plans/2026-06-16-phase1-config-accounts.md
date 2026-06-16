# Phase 1 — Config store + multi-account (0.3.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted config store and a named multi-account model so users can log into several Telegram accounts and run one-shot CLI commands against any of them — all in today's direct-connection mode (no server yet).

**Architecture:** A new `tlgrm.accounts` module owns `~/.tlgrm/config.toml` (read via `tomllib`, written atomically via `tomli_w`) and the account registry. An account is a named login with its own session file at `~/.tlgrm/accounts/<name>.session`. `core.client.get_client` resolves the session from the selected account. A global `--account/-a` flag and an `account` subcommand group expose it. The legacy `~/.tlgrm/tg_session.session` is auto-migrated to account `default`.

**Tech Stack:** Python 3.10+, Telethon, `tomllib`/`tomli` (read), `tomli_w` (write), pytest.

**Reference:** `docs/design/2026-06-16-server-architecture-multi-account.md` §8, §9, §18, §19.

---

### Task 1: Add the `tomli_w` dependency

**Files:**
- Modify: `pyproject.toml` (the `[project] dependencies` array)

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add `tomli_w` to the `dependencies` array (next to `tomli`):

```toml
dependencies = [
    "telethon>=1.35.0",
    "httpx>=0.24.0",
    "tomli>=2.0; python_version < '3.11'",
    "tomli-w>=1.0",
]
```

- [ ] **Step 2: Sync the environment**

Run: `uv sync --extra dev`
Expected: resolves and installs `tomli-w` with no errors.

- [ ] **Step 3: Verify import**

Run: `uv run python -c "import tomli_w; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add tomli-w for writing config.toml"
```

---

### Task 2: Config store — atomic read/write of `~/.tlgrm/config.toml`

**Files:**
- Create: `src/tlgrm/accounts.py`
- Test: `tests/test_accounts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_accounts.py
import os
import stat
import pytest
from tlgrm import accounts


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    cfg = tmp_path / "config.toml"
    monkeypatch.setenv("TG_CONFIG_PATH", str(cfg))
    monkeypatch.setattr(accounts, "_accounts_dir",
                        lambda: str(tmp_path / "accounts"))
    monkeypatch.delenv("TG_SESSION_PATH", raising=False)
    return tmp_path


def test_load_missing_config_returns_empty(tmp_home):
    cfg = accounts.load_config()
    assert cfg == {"default_account": None, "accounts": {}}


def test_save_then_load_roundtrip(tmp_home):
    accounts.save_config({"default_account": "work",
                          "accounts": {"work": {}, "personal": {}}})
    cfg = accounts.load_config()
    assert cfg["default_account"] == "work"
    assert set(cfg["accounts"]) == {"work", "personal"}


def test_saved_config_is_owner_only(tmp_home):
    accounts.save_config({"default_account": None, "accounts": {"a": {}}})
    mode = stat.S_IMODE(os.stat(accounts._config_path()).st_mode)
    assert mode == 0o600


def test_save_strips_none_for_toml(tmp_home):
    # TOML has no null; default_account None must not crash the writer.
    accounts.save_config({"default_account": None, "accounts": {}})
    assert "default_account" not in accounts._config_path_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_accounts.py -q`
Expected: FAIL with `ModuleNotFoundError` / `AttributeError` (no `accounts` module yet).

- [ ] **Step 3: Write minimal implementation**

```python
# src/tlgrm/accounts.py
"""Account registry and the persisted config store (~/.tlgrm/config.toml).

An account is a named Telegram login with its own session file under
~/.tlgrm/accounts/<name>.session. This module owns reading/writing the config
file and resolving which account a command targets. It writes the whole config
back on every change, so it deliberately preserves unrelated sections (e.g.
[stt]) by carrying them through the in-memory dict.
"""

import os

from .core.errors import TlgrmError


def _config_path():
    return os.getenv("TG_CONFIG_PATH", os.path.expanduser("~/.tlgrm/config.toml"))


def _accounts_dir():
    return os.path.expanduser("~/.tlgrm/accounts")


def _config_path_text():
    """Raw file text (test helper; '' if the file does not exist)."""
    path = _config_path()
    return open(path).read() if os.path.exists(path) else ""


def _strip_none(value):
    """Recursively drop keys whose value is None (TOML cannot represent null)."""
    if isinstance(value, dict):
        return {k: _strip_none(v) for k, v in value.items() if v is not None}
    return value


def load_config():
    path = _config_path()
    if not os.path.exists(path):
        return {"default_account": None, "accounts": {}}
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib
    with open(path, "rb") as f:
        data = tomllib.load(f)
    data.setdefault("accounts", {})
    data.setdefault("default_account", None)
    return data


def save_config(data):
    import tomli_w
    path = _config_path()
    os.makedirs(os.path.dirname(path) or ".", mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        tomli_w.dump(_strip_none(data), f)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_accounts.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/tlgrm/accounts.py tests/test_accounts.py
git commit -m "feat(accounts): atomic config.toml read/write store"
```

---

### Task 3: Account registry operations

**Files:**
- Modify: `src/tlgrm/accounts.py`
- Test: `tests/test_accounts.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_accounts.py
def test_add_account_sets_first_as_default(tmp_home):
    accounts.add_account("personal")
    cfg = accounts.load_config()
    assert cfg["default_account"] == "personal"
    assert "personal" in cfg["accounts"]


def test_add_second_account_keeps_default(tmp_home):
    accounts.add_account("personal")
    accounts.add_account("work")
    assert accounts.load_config()["default_account"] == "personal"


def test_set_default_unknown_raises(tmp_home):
    with pytest.raises(accounts.TlgrmError):
        accounts.set_default("ghost")


def test_rename_moves_session_and_default(tmp_home):
    accounts.add_account("a")
    open(accounts.account_session_path("a"), "w").close()
    accounts.rename_account("a", "b")
    cfg = accounts.load_config()
    assert "b" in cfg["accounts"] and "a" not in cfg["accounts"]
    assert cfg["default_account"] == "b"
    assert os.path.exists(accounts.account_session_path("b"))


def test_remove_account_drops_session_and_repoints_default(tmp_home):
    accounts.add_account("a")
    accounts.add_account("b")
    open(accounts.account_session_path("a"), "w").close()
    accounts.set_default("a")
    accounts.remove_account("a")
    cfg = accounts.load_config()
    assert "a" not in cfg["accounts"]
    assert cfg["default_account"] == "b"
    assert not os.path.exists(accounts.account_session_path("a"))


def test_resolve_account_uses_default_then_explicit(tmp_home):
    accounts.add_account("personal")
    accounts.add_account("work")
    assert accounts.resolve_account() == "personal"        # default
    assert accounts.resolve_account("work") == "work"      # explicit
    with pytest.raises(accounts.TlgrmError):
        accounts.resolve_account("ghost")


def test_resolve_account_none_configured_raises(tmp_home):
    with pytest.raises(accounts.TlgrmError):
        accounts.resolve_account()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_accounts.py -q`
Expected: FAIL with `AttributeError` (functions not defined).

- [ ] **Step 3: Write minimal implementation**

Append to `src/tlgrm/accounts.py` (and re-export `TlgrmError` so tests can use `accounts.TlgrmError`):

```python
# near the top, after the import:
__all__ = ["TlgrmError"]  # noqa: F822  (re-export for callers/tests)


def account_session_path(name):
    return os.path.join(_accounts_dir(), f"{name}.session")


def add_account(name):
    cfg = load_config()
    cfg["accounts"].setdefault(name, {})
    if not cfg.get("default_account"):
        cfg["default_account"] = name
    save_config(cfg)


def set_default(name):
    cfg = load_config()
    if name not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {name!r}. See 'tlgrm account list'.")
    cfg["default_account"] = name
    save_config(cfg)


def rename_account(old, new):
    cfg = load_config()
    if old not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {old!r}.")
    if new in cfg["accounts"]:
        raise TlgrmError(f"Account already exists: {new!r}.")
    cfg["accounts"][new] = cfg["accounts"].pop(old)
    if cfg.get("default_account") == old:
        cfg["default_account"] = new
    save_config(cfg)
    src, dst = account_session_path(old), account_session_path(new)
    if os.path.exists(src):
        os.replace(src, dst)


def remove_account(name):
    cfg = load_config()
    if name not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {name!r}.")
    del cfg["accounts"][name]
    if cfg.get("default_account") == name:
        cfg["default_account"] = next(iter(cfg["accounts"]), None)
    save_config(cfg)
    sess = account_session_path(name)
    if os.path.exists(sess):
        os.remove(sess)


def resolve_account(name=None):
    cfg = load_config()
    chosen = name or cfg.get("default_account")
    if not chosen:
        raise TlgrmError("No account configured. Run 'tlgrm account add' to log in.")
    if chosen not in cfg["accounts"]:
        raise TlgrmError(f"No such account: {chosen!r}. See 'tlgrm account list'.")
    return chosen


def session_path_for(account=None, must_exist=True):
    """Resolve the session base path for a command.

    A TG_SESSION_PATH / --session override still wins (deprecated). Otherwise the
    selected account's session is used. During login (`must_exist=False`) the name
    need not be registered yet.
    """
    override = os.getenv("TG_SESSION_PATH")
    if override:
        return override
    if must_exist:
        account = resolve_account(account)
    else:
        account = account or "default"
    return account_session_path(account)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_accounts.py -q`
Expected: PASS (all account-registry tests).

- [ ] **Step 5: Commit**

```bash
git add src/tlgrm/accounts.py tests/test_accounts.py
git commit -m "feat(accounts): registry ops (add/use/rename/remove/resolve)"
```

---

### Task 4: Legacy session migration

**Files:**
- Modify: `src/tlgrm/accounts.py`
- Test: `tests/test_accounts.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_accounts.py
def test_migrate_legacy_session(tmp_home, monkeypatch):
    legacy = tmp_home / "tg_session.session"
    legacy.write_text("session-data")
    monkeypatch.setattr(accounts, "_legacy_session_path", lambda: str(legacy))

    assert accounts.migrate_legacy_session() is True
    cfg = accounts.load_config()
    assert cfg["default_account"] == "default"
    assert os.path.exists(accounts.account_session_path("default"))
    assert not legacy.exists()
    # Idempotent: second call is a no-op.
    assert accounts.migrate_legacy_session() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_accounts.py::test_migrate_legacy_session -q`
Expected: FAIL with `AttributeError` (`_legacy_session_path` / `migrate_legacy_session`).

- [ ] **Step 3: Write minimal implementation**

Append to `src/tlgrm/accounts.py`:

```python
def _legacy_session_path():
    return os.path.expanduser("~/.tlgrm/tg_session.session")


def migrate_legacy_session():
    """Move a pre-0.3.0 single session to account 'default'. Returns True if it
    migrated, False if there was nothing to do."""
    legacy = _legacy_session_path()
    cfg = load_config()
    if not os.path.exists(legacy) or "default" in cfg["accounts"]:
        return False
    os.makedirs(_accounts_dir(), mode=0o700, exist_ok=True)
    os.replace(legacy, account_session_path("default"))
    cfg["accounts"].setdefault("default", {})
    if not cfg.get("default_account"):
        cfg["default_account"] = "default"
    save_config(cfg)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_accounts.py::test_migrate_legacy_session -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tlgrm/accounts.py tests/test_accounts.py
git commit -m "feat(accounts): migrate legacy session to account 'default'"
```

---

### Task 5: Resolve the session per account in `get_client`

**Files:**
- Modify: `src/tlgrm/core/client.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_config.py
def test_get_client_uses_account_session(monkeypatch, tmp_path):
    from tlgrm.core import client
    from tlgrm import accounts

    captured = {}

    class _FakeClient:
        def __init__(self, session, api_id, api_hash):
            captured["session"] = session

    monkeypatch.setattr(client, "TelegramClient", _FakeClient)
    monkeypatch.setattr(client, "ensure_dirs", lambda: None)
    monkeypatch.setattr(client, "get_api_credentials", lambda: (1, "h"))
    monkeypatch.delenv("TG_SESSION_PATH", raising=False)
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    monkeypatch.setattr(accounts, "resolve_account", lambda name=None: "work")

    client.get_client()
    assert captured["session"].endswith("/acc/work.session")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_config.py::test_get_client_uses_account_session -q`
Expected: FAIL — `get_client` still uses `config.session_path()`, so the session won't end with `/acc/work.session`.

- [ ] **Step 3: Write minimal implementation**

Edit `src/tlgrm/core/client.py`:

```python
from ..config import get_api_credentials, ensure_dirs
from .errors import NotAuthorizedError


def get_client(account=None, must_exist=True):
    """Build a TelegramClient for the given account (or the default).

    The session path is resolved at call time from the account registry; a
    TG_SESSION_PATH / --session override still wins. `must_exist=False` is used
    during login, when the account is not registered yet.
    Raises CredentialsError if creds are unset.
    """
    from ..accounts import session_path_for
    ensure_dirs()
    api_id, api_hash = get_api_credentials()
    return TelegramClient(session_path_for(account, must_exist), api_id, api_hash)
```

Also update `open_client` to pass the account through:

```python
@asynccontextmanager
async def open_client(account=None):
    """Yield a connected, authorized client and always disconnect afterwards."""
    client = get_client(account)
    try:
        await ensure_authorized(client)
        yield client
    finally:
        await client.disconnect()
```

(The `accounts` import is function-local to avoid an import cycle, since
`accounts` imports `core.errors`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_config.py -q`
Expected: PASS. (The older `test_get_client_uses_resolved_session` test sets `TG_SESSION_PATH`, which still wins — it stays green.)

- [ ] **Step 5: Commit**

```bash
git add src/tlgrm/core/client.py tests/test_config.py
git commit -m "feat(client): resolve session from the selected account"
```

---

### Task 6: Parser — global `--account` and the `account` command group

**Files:**
- Modify: `src/tlgrm/parser.py`
- Test: `tests/test_cli_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_cli_parser.py
def test_global_account_flag():
    parser = build_parser()
    args = parser.parse_args(["-a", "work", "chats"])
    assert args.account == "work"
    assert args.command == "chats"


def test_account_subcommands_present():
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    assert "account" in sub.choices
    args = parser.parse_args(["account", "add", "personal"])
    assert args.account_command == "add"
    assert args.name == "personal"


def test_account_add_name_optional():
    parser = build_parser()
    args = parser.parse_args(["account", "add"])
    assert args.name is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_cli_parser.py -q -k account`
Expected: FAIL (`-a` unrecognized / no `account` subcommand).

- [ ] **Step 3: Write minimal implementation**

In `src/tlgrm/parser.py`, add the global flag next to `--session`:

```python
    parser.add_argument(
        "-a", "--account", metavar="NAME",
        help="Account to act as (defaults to the configured default account). "
             "Manage accounts with `tlgrm account`.")
```

Then add the `account` subcommand group (place it near the other `sub.add_parser` calls):

```python
    ap = sub.add_parser("account", help="Manage Telegram accounts (multi-login)")
    asub = ap.add_subparsers(dest="account_command", required=True)
    aadd = asub.add_parser("add", help="Log in a new account")
    aadd.add_argument("name", nargs="?", default=None,
                      help="Account name (default: 'default')")
    asub.add_parser("list", help="List accounts and the default")
    ause = asub.add_parser("use", help="Set the default account")
    ause.add_argument("name")
    aren = asub.add_parser("rename", help="Rename an account")
    aren.add_argument("old")
    aren.add_argument("new")
    arem = asub.add_parser("remove", help="Log out and delete an account")
    arem.add_argument("name")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_cli_parser.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/tlgrm/parser.py tests/test_cli_parser.py
git commit -m "feat(cli): --account flag and account subcommands"
```

---

### Task 7: Dispatch — account-aware login and `account` command handlers

**Files:**
- Modify: `src/tlgrm/dispatch.py`
- Modify: `src/tlgrm/cli.py`
- Test: `tests/test_dispatch_accounts.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch_accounts.py
import os
import pytest
from tlgrm import dispatch, accounts


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    monkeypatch.delenv("TG_SESSION_PATH", raising=False)
    return tmp_path


def test_account_list_emits_accounts(tmp_home, capsys):
    accounts.add_account("personal")
    accounts.add_account("work")
    dispatch.run_account_command(type("A", (), {"account_command": "list"}))
    out = capsys.readouterr().out
    assert "personal" in out and "work" in out
    assert "default" in out  # marks the default account


def test_account_use_sets_default(tmp_home, capsys):
    accounts.add_account("personal")
    accounts.add_account("work")
    dispatch.run_account_command(
        type("A", (), {"account_command": "use", "name": "work"}))
    assert accounts.load_config()["default_account"] == "work"


def test_account_remove(tmp_home):
    accounts.add_account("a")
    accounts.add_account("b")
    dispatch.run_account_command(
        type("A", (), {"account_command": "remove", "name": "a"}))
    assert "a" not in accounts.load_config()["accounts"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run --extra dev python -m pytest tests/test_dispatch_accounts.py -q`
Expected: FAIL with `AttributeError` (`run_account_command` not defined).

- [ ] **Step 3: Write minimal implementation**

In `src/tlgrm/dispatch.py`, make `_login` and `run_command` account-aware and add the account-command handler:

```python
async def _login(name=None):
    from . import accounts
    account = name or "default"
    client = get_client(account=account, must_exist=False)
    print(f"Connecting to Telegram to log in account '{account}'...")
    await client.start()
    me = await client.get_me()
    accounts.add_account(account)  # register on success
    print(f"\nLogged in account '{account}' as: {me.first_name} "
          f"(@{me.username or 'No Username'}) [ID: {me.id}]")
    await client.disconnect()


def run_account_command(args):
    """Handle `tlgrm account <list|use|rename|remove>` (sync, no Telegram I/O)."""
    from . import accounts
    cmd = args.account_command
    if cmd == "list":
        cfg = accounts.load_config()
        default = cfg.get("default_account")
        emit({"success": True, "default": default,
              "accounts": [{"name": n, "default": n == default}
                           for n in cfg["accounts"]]})
    elif cmd == "use":
        accounts.set_default(args.name)
        emit({"success": True, "default": args.name})
    elif cmd == "rename":
        accounts.rename_account(args.old, args.new)
        emit({"success": True, "renamed": [args.old, args.new]})
    elif cmd == "remove":
        accounts.remove_account(args.name)
        emit({"success": True, "removed": args.name})
```

Update `run_command` so authenticated commands use the selected account:

```python
async def run_command(args):
    """Run an authenticated command and emit its result."""
    account = getattr(args, "account", None)
    if args.command == "login":
        await _login(account)
        return
    if args.command == "account" and args.account_command == "add":
        await _login(args.name)
        return
    async with open_client(account) as client:
        ...  # existing dispatch body unchanged
```

In `src/tlgrm/cli.py`, route the synchronous `account` subcommands (everything
except `add`, which needs Telegram login) to the new handler. Add this branch
alongside the existing `transcribe`/`listen`/`daemon` branches:

```python
        elif args.command == "account" and args.account_command != "add":
            from .dispatch import run_account_command
            run_account_command(args)
```

Also run the legacy-session migration once at startup, right after `args =
parser.parse_args()` in `main()`:

```python
    from .accounts import migrate_legacy_session
    migrate_legacy_session()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run --extra dev python -m pytest tests/test_dispatch_accounts.py -q`
Expected: PASS.

- [ ] **Step 5: Run the full suite + a CLI smoke test**

Run: `uv run --extra dev python -m pytest -q`
Expected: PASS (all prior tests still green).

Run: `uv run tlgrm account list`
Expected: clean JSON (`"accounts": []` on a fresh machine, or your migrated `default`).

- [ ] **Step 6: Commit**

```bash
git add src/tlgrm/dispatch.py src/tlgrm/cli.py tests/test_dispatch_accounts.py
git commit -m "feat(cli): account-aware login + account command handlers"
```

---

### Task 8: Docs + CHANGELOG

**Files:**
- Modify: `docs/configuration.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Document accounts in `configuration.md`**

Add a section after the environment-variables table:

```markdown
## Accounts (multi-login)

tlgrm supports multiple Telegram accounts, each a named login with its own
session under `~/.tlgrm/accounts/<name>.session`.

```bash
tlgrm account add personal     # interactive login
tlgrm account add work
tlgrm account list             # shows accounts and which is default
tlgrm account use work         # set the default account
tlgrm -a personal chats        # run a command as a specific account
tlgrm account rename work job
tlgrm account remove personal  # log out + delete the session
```

Commands without `-a/--account` use the default account. An existing pre-0.3.0
login (`~/.tlgrm/tg_session.session`) is migrated to account `default`
automatically on first run.

> `--session PATH` / `TG_SESSION_PATH` still work as a low-level override but are
> deprecated in favor of named accounts.
```

- [ ] **Step 2: Add a CHANGELOG entry**

Under a new `## [Unreleased]` heading in `CHANGELOG.md`:

```markdown
## [Unreleased]

### Added

- **Multi-account support.** Log into multiple Telegram accounts, each a named
  profile (`tlgrm account add/list/use/rename/remove`) with its own session.
  Select one per command with `-a/--account`. A pre-0.3.0 single session is
  migrated to account `default` automatically.
```

- [ ] **Step 3: Commit**

```bash
git add docs/configuration.md CHANGELOG.md
git commit -m "docs: document multi-account (account commands, --account)"
```

---

## Self-Review Notes

- **Spec coverage (Phase 1 scope):** config store §18 → Task 2; account model
  §8 + per-account config skeleton §9 → Tasks 3, 6, 7; migration §19 → Task 4;
  session resolution → Task 5; `--account` deprecation of `--session` §19 →
  Task 6 + Task 8. Listener/server/filters/STT/scheduler are later phases.
- **No placeholders:** every step has runnable code/commands.
- **Type consistency:** `session_path_for(account, must_exist)`,
  `get_client(account, must_exist)`, `resolve_account(name)`, and
  `account_session_path(name)` are used identically across Tasks 3, 5, 7.
