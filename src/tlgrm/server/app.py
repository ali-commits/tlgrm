"""The persistent server: owns the AccountManager and serves the control
socket. One process per machine/user."""

import os
import json
import asyncio
import logging
import signal
from typing import Any

from .protocol import read_message, write_message, err
from .handler import handle_request
from .manager import AccountManager

logger = logging.getLogger("tlgrm-server")


def _dir() -> str:
    return os.path.expanduser("~/.tlgrm")


def socket_path() -> str:
    return os.getenv("TG_SERVER_SOCK", os.path.join(_dir(), "server.sock"))


def pid_path() -> str:
    """Sibling of the socket so a TG_SERVER_SOCK override moves both together."""
    sock = socket_path()
    base = sock[:-5] if sock.endswith(".sock") else sock
    return base + ".pid"


async def _handle_conn(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    manager: AccountManager,
    conns: set[asyncio.StreamWriter],
) -> None:
    conns.add(writer)
    try:
        while True:
            try:
                req = await read_message(reader)
            except (json.JSONDecodeError, ValueError):
                # A malformed line must not silently drop the connection — reply
                # with an error and keep serving.
                await write_message(
                    writer,
                    err(
                        None,
                        "ProtocolError",
                        "malformed request (expected one JSON object per line)",
                    ),
                )
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
        conns.discard(writer)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def start_server(manager: AccountManager | None = None) -> Any:
    """Bind the socket and begin serving. Returns the asyncio server object."""
    manager = manager or AccountManager()
    await manager.load_all()
    try:
        from ..stt import preload
        from ..stt.settings import is_enabled

        if is_enabled():
            asyncio.get_running_loop().run_in_executor(None, preload)
    except Exception:
        pass
    sock = socket_path()
    os.makedirs(os.path.dirname(sock), mode=0o700, exist_ok=True)
    if os.path.exists(sock):
        os.remove(sock)  # stale socket from a previous run
    # active connection writers, so shutdown can abort them
    conns: set[asyncio.StreamWriter] = set()
    server: Any = await asyncio.start_unix_server(
        lambda r, w: _handle_conn(r, w, manager, conns), path=sock
    )
    os.chmod(sock, 0o600)
    server._tlgrm_manager = manager  # stash for shutdown
    server._tlgrm_conns = conns
    with open(pid_path(), "w") as f:
        f.write(str(os.getpid()))
    logger.info(f"tlgrm server listening on {sock}")
    return server


async def stop_server(server: Any) -> None:
    server.close()
    # Abort any still-open client connections so wait_closed() can't block
    # forever (Python 3.13+ waits for active connections to finish).
    for w in list(getattr(server, "_tlgrm_conns", ())):
        try:
            w.close()
        except Exception:
            pass
    try:
        await asyncio.wait_for(server.wait_closed(), timeout=5)
    except Exception:
        pass
    mgr = getattr(server, "_tlgrm_manager", None)
    if mgr:
        await mgr.disconnect_all()
    for path in (socket_path(), pid_path()):
        if os.path.exists(path):
            os.remove(path)


async def serve_forever(manager: AccountManager | None = None) -> None:
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
