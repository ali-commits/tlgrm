import os
import stat

from tlgrm import daemon


def test_write_env_file_captures_set_vars(monkeypatch, tmp_path):
    envfile = tmp_path / "daemon.env"
    monkeypatch.setattr(daemon, "ENV_FILE_PATH", str(envfile))
    monkeypatch.setenv("TG_STT_MODEL", "large-v3-turbo")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    captured = daemon._write_env_file()
    content = envfile.read_text()

    assert "TG_STT_MODEL=large-v3-turbo" in content
    assert "OPENAI_API_KEY=sk-test" in content
    assert "GROQ_API_KEY" not in content
    assert {"TG_STT_MODEL", "OPENAI_API_KEY"} <= set(captured)
    assert stat.S_IMODE(os.stat(envfile).st_mode) == 0o600  # owner-only


def test_write_env_file_rejects_multiline_values(monkeypatch, tmp_path):
    envfile = tmp_path / "daemon.env"
    monkeypatch.setattr(daemon, "ENV_FILE_PATH", str(envfile))
    monkeypatch.setenv("TG_STT_MODEL", "base\nINJECTED=1")  # injection attempt

    captured = daemon._write_env_file()
    assert "TG_STT_MODEL" not in captured
    assert "INJECTED" not in envfile.read_text()
