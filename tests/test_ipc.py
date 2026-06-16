import asyncio
import pytest
from tlgrm import ipc
from tlgrm.server import protocol


def test_is_server_running_false_without_socket(tmp_path, monkeypatch):
    monkeypatch.setattr(ipc, "socket_path", lambda: str(tmp_path / "nope.sock"))
    assert ipc.is_server_running() is False


@pytest.mark.asyncio
async def test_request_roundtrip(tmp_path, monkeypatch):
    sock = str(tmp_path / "s.sock")
    monkeypatch.setattr(ipc, "socket_path", lambda: sock)

    async def echo(reader, writer):
        req = await protocol.read_message(reader)
        await protocol.write_message(writer, protocol.ok(req["id"], {"echo": req["cmd"]}))
        writer.close()

    server = await asyncio.start_unix_server(echo, path=sock)
    try:
        assert ipc.is_server_running() is True
        resp = await ipc.request_async("whoami", account="work", args={}, tier="read")
        assert resp["data"]["echo"] == "whoami"
    finally:
        server.close()
        await server.wait_closed()
