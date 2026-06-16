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
