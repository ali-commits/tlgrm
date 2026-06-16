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


def account_session_path(name):
    return os.path.join(_accounts_dir(), f"{name}.session")


def add_account(name):
    cfg = load_config()
    cfg["accounts"].setdefault(name, {})
    if not cfg.get("default_account"):
        cfg["default_account"] = name
    save_config(cfg)
    os.makedirs(_accounts_dir(), mode=0o700, exist_ok=True)


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
