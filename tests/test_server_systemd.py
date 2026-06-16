from tlgrm import daemon


def test_server_install_writes_unit(monkeypatch):
    monkeypatch.setattr(daemon, "check_systemctl", lambda: True)
    monkeypatch.setattr(daemon, "_write_env_file", lambda: [])
    monkeypatch.setattr(daemon, "run_systemctl_cmd", lambda args: (True, "", ""))
    monkeypatch.setattr(daemon.shutil, "which", lambda x: "/usr/bin/tlgrm")
    monkeypatch.setattr(daemon.os, "chmod", lambda *a, **k: None)
    monkeypatch.setattr(daemon.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(daemon.os, "open", lambda *a, **k: 0)

    captured = {"text": ""}

    class _Sink:
        def write(self, s): captured["text"] += s
        def __enter__(self): return self
        def __exit__(self, *a): return False

    monkeypatch.setattr(daemon.os, "fdopen", lambda *a, **k: _Sink())

    daemon.server_install()
    unit = captured["text"]
    assert "ExecStart=/usr/bin/tlgrm server start --foreground" in unit
    assert "tlgrm server" in unit  # description mentions the server
