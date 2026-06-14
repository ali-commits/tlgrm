import sys

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
