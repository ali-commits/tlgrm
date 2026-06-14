from tlgrm import stt


def test_transcribe_audio_backend_and_model_override(monkeypatch):
    captured = {}

    def fake(path, model):
        captured["path"] = path
        captured["model"] = model
        return "  hello  "

    monkeypatch.setitem(stt._LOCAL, "faster-whisper", fake)
    out = stt.transcribe_audio("/x.ogg", backend="faster-whisper", model="base")
    assert out == "  hello  "  # dispatcher returns backend text as-is
    assert captured == {"path": "/x.ogg", "model": "base"}


def test_transcribe_audio_unknown_backend_returns_none():
    assert stt.transcribe_audio("/x.ogg", backend="does-not-exist") is None


def test_parakeet_is_registered():
    assert "parakeet" in stt._LOCAL


def test_transcribe_audio_backend_failure_returns_none(monkeypatch):
    def boom(path, model):
        raise RuntimeError("backend exploded")

    monkeypatch.setitem(stt._CLOUD, "openai", boom)
    assert stt.transcribe_audio("/x.ogg", backend="openai") is None
