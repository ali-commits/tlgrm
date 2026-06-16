import os
from tlgrm.stt import settings, local
import tlgrm.stt as stt


def _write_cfg(tmp_path, body):
    p = tmp_path / "config.toml"
    p.write_text(body)
    return str(p)


def test_is_enabled_default_true(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "missing.toml"))
    assert settings.is_enabled() is True


def test_is_enabled_reads_config(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", _write_cfg(tmp_path, "[stt]\nenabled = false\n"))
    assert settings.is_enabled() is False


def test_resolve_device_precedence(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", _write_cfg(tmp_path, '[stt]\ndevice = "cuda"\n'))
    monkeypatch.delenv("TG_STT_DEVICE", raising=False)
    assert settings.resolve_device() == "cuda"
    monkeypatch.setenv("TG_STT_DEVICE", "cpu")
    assert settings.resolve_device() == "cpu"


def test_stt_settings_dict(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH",
                       _write_cfg(tmp_path, '[stt]\nbackend = "whisper"\nmodel = "base"\n'))
    monkeypatch.delenv("TG_STT_BACKEND", raising=False)
    monkeypatch.delenv("TG_STT_MODEL", raising=False)
    s = settings.stt_settings()
    assert s["backend"] == "whisper" and s["model"] == "base" and s["enabled"] is True


def test_reset_models_clears_cache():
    local._models[("x",)] = object()
    stt.reset_models()
    assert local._models == {}
