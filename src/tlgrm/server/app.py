"""The persistent server: owns the AccountManager and serves the control
socket. One process per machine/user."""

import os
import json
import fcntl
import asyncio
import logging
import signal
from typing import Any

from .protocol import read_message, write_message, err
from .handler import handle_request
from .manager import AccountManager

logger = logging.getLogger("tlgrm-server")


class ServerAlreadyRunning(RuntimeError):
    """Raised by start_server when another tlgrm server already holds the
    single-instance lock. The caller should stand down without binding —
    exactly one process may own the socket and the Telegram session."""


def _dir() -> str:
    return os.path.expanduser("~/.tlgrm")


def socket_path() -> str:
    return os.getenv("TG_SERVER_SOCK", os.path.join(_dir(), "server.sock"))


def _sibling(suffix: str) -> str:
    """A path next to the socket so a TG_SERVER_SOCK override moves it too."""
    sock = socket_path()
    base = sock[:-5] if sock.endswith(".sock") else sock
    return base + suffix


def pid_path() -> str:
    return _sibling(".pid")


def lock_path() -> str:
    return _sibling(".lock")


def _acquire_singleton_lock() -> int:
    """Atomically become THE server. Returns an open fd holding an exclusive
    advisory lock, which must stay open for the process's lifetime (the OS
    releases it automatically on exit, so a crashed server never leaves a stale
    lock). Raises ServerAlreadyRunning if another process already holds it.

    This is what makes startup race-free: two servers spawned at once (e.g. one
    by systemd and one auto-spawned by the MCP bridge) can't both bind — the
    loser fails here and stands down instead of stealing the socket/session."""
    path = lock_path()
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        raise ServerAlreadyRunning("another tlgrm server already owns the socket")
    return fd


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
    """Bind the socket and begin serving. Returns the asyncio server object.

    Raises ServerAlreadyRunning if another server already holds the
    single-instance lock — the caller should stand down."""
    lock_fd = _acquire_singleton_lock()  # must win this before touching anything
    try:
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
            os.remove(sock)  # stale socket from a previous run (we hold the lock)
        # active connection writers, so shutdown can abort them
        conns: set[asyncio.StreamWriter] = set()
        server: Any = await asyncio.start_unix_server(
            lambda r, w: _handle_conn(r, w, manager, conns), path=sock
        )
        os.chmod(sock, 0o600)
        server._tlgrm_manager = manager  # stash for shutdown
        server._tlgrm_conns = conns
        server._tlgrm_lock_fd = lock_fd  # keep the lock alive for the server's life
        with open(pid_path(), "w") as f:
            f.write(str(os.getpid()))
        logger.info(f"tlgrm server listening on {sock}")
        return server
    except BaseException:
        os.close(lock_fd)  # release the lock if we never came up
        raise


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
    # Release the single-instance lock so a fresh server can take over. Close
    # the fd (which releases the flock) but leave the lock file in place —
    # unlinking it would race a new server that already opened the same path.
    lock_fd = getattr(server, "_tlgrm_lock_fd", None)
    if lock_fd is not None:
        try:
            os.close(lock_fd)
        except OSError:
            pass


async def serve_forever(manager: AccountManager | None = None) -> None:
    """Run the server until SIGTERM/SIGINT (used by `tlgrm server start`)."""
    try:
        server = await start_server(manager)
    except ServerAlreadyRunning:
        # A duplicate start (the startup race): another server already owns the
        # socket. Stand down silently so we don't fight over the session.
        logger.info("another tlgrm server already owns the socket; exiting")
        return
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    try:
        await stop.wait()
    finally:
        await stop_server(server)
