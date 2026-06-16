"""The persistent server: owns the AccountManager and serves the control
socket. One process per machine/user."""

import os
import json
import asyncio
import logging
import signal

from .protocol import read_message, write_message, err
from .handler import handle_request
from .manager import AccountManager

logger = logging.getLogger("tlgrm-server")


def _dir():
    return os.path.expanduser("~/.tlgrm")


def socket_path():
    return os.getenv("TG_SERVER_SOCK", os.path.join(_dir(), "server.sock"))


def pid_path():
    """Sibling of the socket so a TG_SERVER_SOCK override moves both together."""
    sock = socket_path()
    base = sock[:-5] if sock.endswith(".sock") else sock
    return base + ".pid"


async def _handle_conn(reader, writer, manager):
    try:
        while True:
            try:
                req = await read_message(reader)
            except (json.JSONDecodeError, ValueError):
                # A malformed line must not silently drop the connection — reply
                # with an error and keep serving.
                await write_message(writer, err(
                    None, "ProtocolError",
                    "malformed request (expected one JSON object per line)"))
                continue
            if req is None:
                break
            resp = await handle_request(manager, req)
            await write_message(writer, resp)
    except (ConnectionError, asyncio.IncompleteReadError):
        pass
    except Exception:  # never let one connection take down the server task
        logger.exception("connection handler error")
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def start_server(manager=None):
    """Bind the socket and begin serving. Returns the asyncio server object."""
    manager = manager or AccountManager()
    await manager.load_all()
    sock = socket_path()
    os.makedirs(os.path.dirname(sock), mode=0o700, exist_ok=True)
    if os.path.exists(sock):
        os.remove(sock)  # stale socket from a previous run
    server = await asyncio.start_unix_server(
        lambda r, w: _handle_conn(r, w, manager), path=sock)
    os.chmod(sock, 0o600)
    server._tlgrm_manager = manager  # stash for shutdown
    with open(pid_path(), "w") as f:
        f.write(str(os.getpid()))
    logger.info(f"tlgrm server listening on {sock}")
    return server


async def stop_server(server):
    server.close()
    await server.wait_closed()
    mgr = getattr(server, "_tlgrm_manager", None)
    if mgr:
        await mgr.disconnect_all()
    for path in (socket_path(), pid_path()):
        if os.path.exists(path):
            os.remove(path)


async def serve_forever(manager=None):
    """Run the server until SIGTERM/SIGINT (used by `tlgrm server start`)."""
    server = await start_server(manager)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        await stop_server(server)
