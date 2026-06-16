import pytest
from tlgrm import accounts, listen_core as lc, listenctl, ipc


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)
    accounts.add_account("work")
    return tmp_path


def test_parse_and_within_window():
    assert lc._parse_window("09:00-17:00") == (540, 1020)
    assert lc._within_window(600, (540, 1020)) is True
    assert lc._within_window(1100, (540, 1020)) is False
    assert lc._within_window(1380, (1320, 360)) is True  # overnight 22:00-06:00
    assert lc._within_window(720, (1320, 360)) is False
    assert lc._parse_window("bad") is None


def test_window_config_roundtrip(tmp_home):
    accounts.set_listen_window("work", "09:00-17:00")
    assert accounts.listen_config("work")["window"] == "09:00-17:00"
    accounts.clear_listen_window("work")
    assert accounts.listen_config("work")["window"] is None


def test_listenctl_window(tmp_home, capsys):
    listenctl.window_set("work", "09:00-17:00")
    assert accounts.listen_config("work")["window"] == "09:00-17:00"
    listenctl.window_clear("work")
    assert accounts.listen_config("work")["window"] is None


def test_window_set_rejects_invalid(tmp_home, capsys):
    listenctl.window_set("work", "25:99-9")  # invalid
    out = capsys.readouterr().out
    assert '"success": false' in out.lower()
    assert accounts.listen_config("work")["window"] is None  # not stored
