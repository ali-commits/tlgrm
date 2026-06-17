import asyncio
import pytest
from tlgrm.server import app, protocol, handler


class _StubManager:
    async def load_all(self):
        pass

    async def get(self, account=None):
        return object()

    async def disconnect_all(self):
        pass


async def _aval(v):
    return v


@pytest.mark.asyncio
async def test_server_roundtrip(tmp_path, monkeypatch):
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(app, "socket_path", lambda: sock)
    monkeypatch.setattr(app, "pid_path", lambda: str(tmp_path / "s.pid"))
    monkeypatch.setattr(
        handler,
        "execute",
        lambda client, args, account=None: _aval(
            {"success": True, "echo": args.command}
        ),
    )

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
async def test_stop_server_does_not_hang_with_open_connection(tmp_path, monkeypatch):
    # Regression: stop_server must abort still-open client connections, or
    # wait_closed() blocks forever (and so would `tlgrm server stop`).
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(app, "socket_path", lambda: sock)
    monkeypatch.setattr(app, "pid_path", lambda: str(tmp_path / "s.pid"))

    srv = await app.start_server(_StubManager())
    reader, writer = await asyncio.open_unix_connection(sock)  # left open on purpose
    await protocol.write_message(writer, protocol.request(1, "ping"))
    await protocol.read_message(reader)
    # Do NOT close the client. stop_server must still return promptly.
    await asyncio.wait_for(app.stop_server(srv), timeout=5)
    writer.close()


@pytest.mark.asyncio
async def test_second_server_backs_off_and_first_keeps_socket(tmp_path, monkeypatch):
    # Race fix: a second server must NOT steal the running server's socket.
    # It fails to acquire the single-instance lock and backs off instead.
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(app, "socket_path", lambda: sock)
    monkeypatch.setattr(app, "pid_path", lambda: str(tmp_path / "s.pid"))

    srv = await app.start_server(_StubManager())
    try:
        with pytest.raises(app.ServerAlreadyRunning):
            await app.start_server(_StubManager())
        # The first server's socket is untouched and still serving.
        reader, writer = await asyncio.open_unix_connection(sock)
        await protocol.write_message(writer, protocol.request(1, "ping"))
        assert (await protocol.read_message(reader))["data"] == {"pong": True}
        writer.close()
    finally:
        await app.stop_server(srv)


@pytest.mark.asyncio
async def test_lock_released_after_stop_allows_restart(tmp_path, monkeypatch):
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(app, "socket_path", lambda: sock)
    monkeypatch.setattr(app, "pid_path", lambda: str(tmp_path / "s.pid"))

    srv = await app.start_server(_StubManager())
    await app.stop_server(srv)
    # The lock is released on stop, so a fresh server can take over.
    srv2 = await app.start_server(_StubManager())
    await app.stop_server(srv2)


@pytest.mark.asyncio
async def test_serve_forever_exits_when_another_server_owns_lock(tmp_path, monkeypatch):
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(app, "socket_path", lambda: sock)
    monkeypatch.setattr(app, "pid_path", lambda: str(tmp_path / "s.pid"))

    srv = await app.start_server(_StubManager())
    try:
        # The loser's serve_forever() must return promptly (not bind/raise).
        await asyncio.wait_for(app.serve_forever(_StubManager()), timeout=5)
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
        writer.write(b"this is not json\n")  # malformed line
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
