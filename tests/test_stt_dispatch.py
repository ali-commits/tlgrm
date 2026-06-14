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


def test_local_backends_are_whisper_family():
    assert set(stt._LOCAL) == {"faster-whisper", "whisper"}


def test_preload_noop_for_cloud_backend(monkeypatch):
    # Cloud backends have no local model -> preload returns immediately.
    monkeypatch.setattr(stt, "resolve_backend", lambda: "openai")
    stt.preload()  # must not raise or attempt a model load


def test_transcribe_audio_backend_failure_returns_none(monkeypatch):
    def boom(path, model):
        raise RuntimeError("backend exploded")

    monkeypatch.setitem(stt._CLOUD, "openai", boom)
    assert stt.transcribe_audio("/x.ogg", backend="openai") is None
