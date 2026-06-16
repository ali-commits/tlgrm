import types
import pytest
from tlgrm import dispatch, ipc


def test_run_command_routes_to_server(monkeypatch, capsys):
    monkeypatch.setattr(ipc, "is_server_running", lambda: True)

    sent = {}
    def fake_request_sync(cmd, account=None, args=None, tier="destructive"):
        sent.update(cmd=cmd, account=account, args=args)
        return {"id": 1, "ok": True, "data": {"success": True, "routed": True}}
    monkeypatch.setattr(ipc, "request_sync", fake_request_sync)

    # If it tried to connect directly this would explode:
    def boom(*a, **k): raise AssertionError("should not open a direct client")
    monkeypatch.setattr(dispatch, "open_client", boom)

    args = types.SimpleNamespace(command="whoami", account="work")
    dispatch.run_command_routed(args)
    assert sent["cmd"] == "whoami" and sent["account"] == "work"
    assert '"routed": true' in capsys.readouterr().out.lower()


def test_run_command_routed_falls_back_when_no_server(monkeypatch):
    monkeypatch.setattr(ipc, "is_server_running", lambda: False)
    called = {}
    async def fake_run_command(args): called["direct"] = True
    monkeypatch.setattr(dispatch, "run_command", fake_run_command)
    args = types.SimpleNamespace(command="whoami", account=None)
    dispatch.run_command_routed(args)
    assert called.get("direct") is True
