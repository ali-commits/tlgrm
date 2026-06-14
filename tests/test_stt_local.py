import sys

import pytest

from tlgrm.stt import local


def test_faster_whisper_missing_returns_none(monkeypatch):
    # Simulate the optional dependency being absent -> graceful None
    # (robust whether or not faster-whisper is actually installed).
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    assert local.faster_whisper_transcribe("/nonexistent.ogg", None) is None


def test_vosk_without_model_path_returns_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "vosk", None)
    monkeypatch.delenv("VOSK_MODEL_PATH", raising=False)
    assert local.vosk_transcribe("/nonexistent.ogg", None) is None


def test_fw_device_env_override(monkeypatch):
    monkeypatch.setenv("TG_STT_DEVICE", "cuda")
    assert local._fw_device() == "cuda"


def test_fw_device_cpu_when_ctranslate2_absent(monkeypatch):
    monkeypatch.delenv("TG_STT_DEVICE", raising=False)
    monkeypatch.setitem(sys.modules, "ctranslate2", None)  # import fails -> cpu
    assert local._fw_device() == "cpu"


def test_fw_device_cuda_when_gpu_detected(monkeypatch):
    monkeypatch.delenv("TG_STT_DEVICE", raising=False)
    ct = pytest.importorskip("ctranslate2")
    monkeypatch.setattr(ct, "get_cuda_device_count", lambda: 1)
    assert local._fw_device() == "cuda"


def test_parakeet_missing_returns_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "nemo", None)
    monkeypatch.setitem(sys.modules, "nemo.collections", None)
    monkeypatch.setitem(sys.modules, "nemo.collections.asr", None)
    assert local.parakeet_transcribe("/nonexistent.ogg", None) is None
