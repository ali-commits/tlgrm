import pytest
from tlgrm import sttctl, accounts, ipc
from tlgrm.stt import settings


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)
    for v in ("TG_STT_BACKEND", "TG_STT_MODEL", "TG_STT_DEVICE"):
        monkeypatch.delenv(v, raising=False)
    return tmp_path


def test_enable_disable(tmp_home):
    sttctl.set_enabled(False)
    assert settings.is_enabled() is False
    sttctl.set_enabled(True)
    assert settings.is_enabled() is True


def test_set_fields(tmp_home, capsys):
    sttctl.set_config(backend="whisper", model="large-v3", device="cpu")
    assert settings.resolve_backend() == "whisper"
    assert settings.resolve_model() == "large-v3"
    assert settings.resolve_device() == "cpu"


def test_set_pushes_reload_when_server_running(tmp_home, monkeypatch):
    pushed = {}
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    monkeypatch.setattr(
        ipc,
        "request_sync",
        lambda cmd, **k: pushed.setdefault("cmd", cmd) or {"ok": True, "data": {}},
    )
    sttctl.set_config(model="base")
    assert pushed["cmd"] == "stt_reload"


def test_status(tmp_home, capsys):
    sttctl.status()
    out = capsys.readouterr().out
    assert '"backend"' in out and '"enabled"' in out
