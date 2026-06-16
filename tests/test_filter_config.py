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
    assert accounts.filter_config("work", "listen") == {"mode": "block", "list": []}


def test_listenctl_show_is_domain_correct(tmp_home, capsys):
    accounts.filter_add("work", "write", ["@boss"])
    listenctl.filter_cmd("work", "write", "show")
    out = capsys.readouterr().out
    assert "@boss" in out and '"domain": "write"' in out.lower()
