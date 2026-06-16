from tlgrm import serverctl, ipc


def test_status_reports_not_running(monkeypatch, capsys):
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)
    serverctl.status()
    out = capsys.readouterr().out
    assert '"running": false' in out.lower()


def test_status_reports_running(monkeypatch, capsys):
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    serverctl.status()
    assert '"running": true' in capsys.readouterr().out.lower()


def test_start_when_already_running_is_noop(monkeypatch, capsys):
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)
    spawned = {"v": False}
    monkeypatch.setattr(serverctl, "_spawn_detached", lambda: spawned.update(v=True))
    serverctl.start()
    assert spawned["v"] is False  # did not spawn a second server
