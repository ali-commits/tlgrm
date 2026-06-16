"""CLI-side control of the background server: start (spawn detached), stop, status."""

import os
import sys
import shutil
import signal
import subprocess

from . import ipc
from .output import emit
from .server.app import pid_path, socket_path, serve_forever


def _spawn_detached() -> None:
    """Launch `tlgrm server start --foreground` in its own session. Resolve the
    `tlgrm` executable (sys.argv[0] may be `tlgrm-mcp` when called from the bridge)."""
    exe = shutil.which("tlgrm")
    if not exe:
        cand = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "tlgrm")
        exe = cand if os.path.exists(cand) else sys.argv[0]
    subprocess.Popen(
        [exe, "server", "start", "--foreground"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def start(foreground: bool = False) -> None:
    if foreground:
        import asyncio

        asyncio.run(serve_forever())
        return
    if ipc.is_server_running():
        emit({"success": True, "running": True, "message": "server already running"})
        return
    _spawn_detached()
    emit({"success": True, "running": True, "message": "server started"})


def stop() -> None:
    path = pid_path()
    if not os.path.exists(path):
        emit({"success": True, "running": False, "message": "server not running"})
        return
    with open(path) as f:
        pid = int(f.read().strip() or "0")
    try:
        os.kill(pid, signal.SIGTERM)
        emit({"success": True, "message": f"sent SIGTERM to {pid}"})
    except ProcessLookupError:
        os.remove(path)
        sock = socket_path()
        if os.path.exists(sock):
            os.remove(sock)  # clear the orphaned socket too
        emit({"success": True, "message": "server not running (stale pid removed)"})


def status() -> None:
    emit({"success": True, "running": ipc.is_server_running()})


def restart() -> None:
    import time

    stop()
    # Wait for the old process to release the socket before respawning, so the
    # new start() doesn't see the dying server as "already running".
    for _ in range(50):
        if not ipc.is_server_running():
            break
        time.sleep(0.1)
    start()
