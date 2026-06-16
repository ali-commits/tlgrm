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
