import types
import pytest
from tlgrm import execute as ex


class _Chats:
    async def list_chats(self, client, limit):
        return {"success": True, "chats": [], "limit": limit}


def test_execute_routes_read_command(monkeypatch):
    monkeypatch.setattr(ex, "chats", _Chats())
    args = types.SimpleNamespace(command="chats", limit=7)
    out = __import__("asyncio").run(ex.execute(object(), args))
    assert out == {"success": True, "chats": [], "limit": 7}


def test_execute_unknown_command_raises():
    args = types.SimpleNamespace(command="nope")
    with pytest.raises(ex.TlgrmError):
        __import__("asyncio").run(ex.execute(object(), args))
