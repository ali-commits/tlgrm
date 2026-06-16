"""CLI-side control of the background server: start (spawn detached), stop, status."""

import os
import sys
import signal
import subprocess

from . import ipc
from .output import emit
from .server.app import pid_path, serve_forever


def _spawn_detached():
    """Launch `tlgrm server start --foreground` in its own session."""
    exe = sys.argv[0]
    subprocess.Popen([exe, "server", "start", "--foreground"],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)


def start(foreground=False):
    if foreground:
        import asyncio
        asyncio.run(serve_forever())
        return
    if ipc.is_server_running():
        emit({"success": True, "running": True, "message": "server already running"})
        return
    _spawn_detached()
    emit({"success": True, "running": True, "message": "server started"})


def stop():
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
        emit({"success": True, "message": "server not running (stale pid removed)"})


def status():
    emit({"success": True, "running": ipc.is_server_running()})


def restart():
    stop()
    start()
