# tests/test_config.py
import base64

import pytest
from tlgrm import config
from tlgrm.core.errors import CredentialsError


def _make_blob(api_id, api_hash):
    """Build an obfuscated blob the same way the runtime decoder expects."""
    payload = f"{api_id}:{api_hash}".encode()
    xored = bytes(b ^ config._s[i % len(config._s)] for i, b in enumerate(payload))
    return base64.b64encode(xored).decode()


def test_missing_credentials_raises(monkeypatch):
    monkeypatch.delenv("TG_API_ID", raising=False)
    monkeypatch.delenv("TG_API_HASH", raising=False)
    monkeypatch.setattr(config, "_q", "")  # no bundled fallback present
    with pytest.raises(CredentialsError):
        config.get_api_credentials()


def test_non_integer_api_id_raises(monkeypatch):
    monkeypatch.setenv("TG_API_ID", "abc")
    monkeypatch.setenv("TG_API_HASH", "hash")
    with pytest.raises(CredentialsError):
        config.get_api_credentials()


def test_valid_credentials_returned(monkeypatch):
    monkeypatch.setenv("TG_API_ID", "1234567")
    monkeypatch.setenv("TG_API_HASH", "hash")
    assert config.get_api_credentials() == (1234567, "hash")


def test_bundled_fallback_used_when_env_absent(monkeypatch):
    monkeypatch.delenv("TG_API_ID", raising=False)
    monkeypatch.delenv("TG_API_HASH", raising=False)
    monkeypatch.setattr(config, "_q", _make_blob("999", "deadbeefcafe"))
    assert config.get_api_credentials() == (999, "deadbeefcafe")


def test_env_overrides_bundled(monkeypatch):
    monkeypatch.setattr(config, "_q", _make_blob("999", "deadbeefcafe"))
    monkeypatch.setenv("TG_API_ID", "111")
    monkeypatch.setenv("TG_API_HASH", "envhash")
    assert config.get_api_credentials() == (111, "envhash")


def test_session_path_default(monkeypatch):
    monkeypatch.delenv("TG_SESSION_PATH", raising=False)
    assert config.session_path().endswith("/.tlgrm/tg_session")


def test_session_path_honors_env_set_after_import(monkeypatch):
    # Resolved at call time, so a path set after import (e.g. by --session) wins.
    monkeypatch.setenv("TG_SESSION_PATH", "/tmp/custom/mcp")
    assert config.session_path() == "/tmp/custom/mcp"


def test_get_client_uses_resolved_session(monkeypatch):
    from tlgrm.core import client

    captured = {}

    class _FakeClient:
        def __init__(self, session, api_id, api_hash):
            captured["session"] = session

    monkeypatch.setattr(client, "TelegramClient", _FakeClient)
    monkeypatch.setattr(client, "ensure_dirs", lambda: None)
    monkeypatch.setattr(client, "get_api_credentials", lambda: (1, "h"))
    monkeypatch.setenv("TG_SESSION_PATH", "/tmp/sessions/daemon")

    client.get_client()
    assert captured["session"] == "/tmp/sessions/daemon"
