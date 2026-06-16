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
    async def fake_execute(client, args):
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
