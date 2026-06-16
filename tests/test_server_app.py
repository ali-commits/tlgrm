import asyncio
import pytest
from tlgrm.server import app, protocol, handler


class _StubManager:
    async def load_all(self): pass
    async def get(self, account=None): return object()
    async def disconnect_all(self): pass


async def _aval(v):
    return v


@pytest.mark.asyncio
async def test_server_roundtrip(tmp_path, monkeypatch):
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(app, "socket_path", lambda: sock)
    monkeypatch.setattr(app, "pid_path", lambda: str(tmp_path / "s.pid"))
    monkeypatch.setattr(handler, "execute",
                        lambda client, args: _aval({"success": True, "echo": args.command}))

    srv = await app.start_server(_StubManager())
    try:
        reader, writer = await asyncio.open_unix_connection(sock)
        await protocol.write_message(writer, protocol.request(1, "ping"))
        assert (await protocol.read_message(reader))["data"] == {"pong": True}
        await protocol.write_message(writer, protocol.request(2, "whoami", tier="read"))
        resp = await protocol.read_message(reader)
        assert resp["ok"] and resp["data"]["echo"] == "whoami"
        writer.close()
    finally:
        await app.stop_server(srv)


@pytest.mark.asyncio
async def test_malformed_line_returns_error_and_keeps_connection(tmp_path, monkeypatch):
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(app, "socket_path", lambda: sock)
    monkeypatch.setattr(app, "pid_path", lambda: str(tmp_path / "s.pid"))

    srv = await app.start_server(_StubManager())
    try:
        reader, writer = await asyncio.open_unix_connection(sock)
        writer.write(b"this is not json\n")          # malformed line
        await writer.drain()
        resp = await protocol.read_message(reader)
        assert resp["ok"] is False
        assert resp["error"]["type"] == "ProtocolError"
        # connection survives — a valid request still works afterward
        await protocol.write_message(writer, protocol.request(9, "ping"))
        assert (await protocol.read_message(reader))["data"] == {"pong": True}
        writer.close()
    finally:
        await app.stop_server(srv)
