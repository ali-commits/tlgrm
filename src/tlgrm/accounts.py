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
