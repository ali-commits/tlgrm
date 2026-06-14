from tlgrm.stt import settings


def _clear(monkeypatch):
    monkeypatch.delenv("TG_STT_BACKEND", raising=False)
    for _, env in settings.CLOUD_KEY_ENV:
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(settings, "_load_config", lambda: {})


def test_default_is_faster_whisper(monkeypatch):
    _clear(monkeypatch)
    assert settings.resolve_backend() == "faster-whisper"


def test_api_key_autoselects_cloud(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    assert settings.resolve_backend() == "groq"


def test_openai_takes_precedence_over_groq(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert settings.resolve_backend() == "openai"


def test_explicit_env_backend_wins(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("TG_STT_BACKEND", "vosk")
    assert settings.resolve_backend() == "vosk"


def test_config_file_backend_used_when_no_env(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setattr(settings, "_load_config", lambda: {"backend": "whisper"})
    assert settings.resolve_backend() == "whisper"
