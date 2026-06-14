from tlgrm.stt import local


def test_faster_whisper_missing_returns_none():
    # faster-whisper is not installed in the test env -> graceful None
    assert local.faster_whisper_transcribe("/nonexistent.ogg", None) is None


def test_vosk_without_model_path_returns_none(monkeypatch):
    monkeypatch.delenv("VOSK_MODEL_PATH", raising=False)
    assert local.vosk_transcribe("/nonexistent.ogg", None) is None
