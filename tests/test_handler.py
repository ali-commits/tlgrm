import asyncio
from tlgrm.server import handler


class _Manager:
    def __init__(self, client=None, exc=None): self._c = client; self._exc = exc
    async def get(self, account=None):
        if self._exc:
            raise self._exc
        return self._c


def test_ping_returns_pong():
    out = asyncio.run(handler.handle_request(_Manager(), {"id": 1, "cmd": "ping"}))
    assert out["ok"] and out["data"] == {"pong": True}


def test_tier_rejection():
    req = {"id": 2, "cmd": "delete", "tier": "read", "args": {}}
    out = asyncio.run(handler.handle_request(_Manager(), req))
    assert out["ok"] is False
    assert out["error"]["type"] == "PermissionError"


def test_executes_command(monkeypatch):
    async def fake_execute(client, args, account=None):
        assert args.command == "chats" and args.limit == 3
        return {"success": True, "chats": []}
    monkeypatch.setattr(handler, "execute", fake_execute)
    req = {"id": 3, "cmd": "chats", "tier": "read", "args": {"limit": 3}}
    out = asyncio.run(handler.handle_request(_Manager(client=object()), req))
    assert out["ok"] and out["data"]["success"]


def test_error_is_mapped(monkeypatch):
    from tlgrm.core.errors import NotAuthorizedError
    out = asyncio.run(handler.handle_request(
        _Manager(exc=NotAuthorizedError("nope")),
        {"id": 4, "cmd": "chats", "tier": "read", "args": {}}))
    assert out["ok"] is False
    assert out["error"]["type"] == "NotAuthorizedError"
    assert "nope" in out["error"]["message"]


def test_reload_control_command():
    class _M:
        def __init__(self): self.reloaded = None
        async def reload_listener(self, account=None): self.reloaded = account
        async def get(self, account=None): raise AssertionError("not a telegram op")
    m = _M()
    out = asyncio.run(handler.handle_request(
        m, {"id": 7, "cmd": "reload", "account": "work", "tier": "read"}))
    assert out["ok"] and out["data"] == {"reloaded": "work"}
    assert m.reloaded == "work"


def test_stt_reload_control_command(monkeypatch):
    calls = {"reset": 0}
    import tlgrm.stt as stt
    monkeypatch.setattr(stt, "reset_models", lambda: calls.__setitem__("reset", calls["reset"] + 1))

    class _M:
        async def get(self, account=None): raise AssertionError("not a telegram op")
    out = asyncio.run(handler.handle_request(_M(), {"id": 5, "cmd": "stt_reload", "tier": "read"}))
    assert out["ok"] and out["data"] == {"stt_reloaded": True}
    assert calls["reset"] == 1


def test_stt_status_control_command(monkeypatch):
    from tlgrm.stt import local
    monkeypatch.setattr(local, "_models", {("faster-whisper", "tiny", "cpu", "int8"): object()})

    class _M:
        async def get(self, account=None): raise AssertionError("not a telegram op")
    out = asyncio.run(handler.handle_request(_M(), {"id": 6, "cmd": "stt_status", "tier": "read"}))
    assert out["ok"]
    assert out["data"]["loaded"] == ["faster-whisper/tiny/cpu/int8"]
