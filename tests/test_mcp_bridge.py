import asyncio
import pytest
from tlgrm.mcp import server as mcpsrv


def test_tier_from_flags():
    assert mcpsrv._tier(False, False) == "read"
    assert mcpsrv._tier(True, False) == "write"
    assert mcpsrv._tier(True, True) == "destructive"


@pytest.mark.asyncio
async def test_call_forwards_via_ipc(monkeypatch):
    sent = {}
    async def fake_req(cmd, account=None, args=None, tier="destructive"):
        sent.update(cmd=cmd, account=account, args=args, tier=tier)
        return {"ok": True, "data": {"success": True, "echo": cmd}}
    monkeypatch.setattr("tlgrm.ipc.request_async", fake_req)

    out = await mcpsrv._call("send", "work", "write", target="@x", text="hi")
    assert out["echo"] == "send"
    assert sent == {"cmd": "send", "account": "work", "tier": "write",
                    "args": {"target": "@x", "text": "hi"}}


@pytest.mark.asyncio
async def test_call_raises_on_error(monkeypatch):
    async def fake_req(cmd, account=None, args=None, tier="destructive"):
        return {"ok": False, "error": {"type": "PermissionError", "message": "nope"}}
    monkeypatch.setattr("tlgrm.ipc.request_async", fake_req)
    with pytest.raises(RuntimeError, match="nope"):
        await mcpsrv._call("delete", None, "read", target="@x", message_ids=[1])


@pytest.mark.asyncio
async def test_ensure_server_no_spawn_when_running(monkeypatch):
    spawned = {"v": False}
    monkeypatch.setattr("tlgrm.ipc.is_server_running", lambda: True)
    monkeypatch.setattr("tlgrm.serverctl._spawn_detached", lambda: spawned.__setitem__("v", True))
    await mcpsrv._ensure_server()
    assert spawned["v"] is False
