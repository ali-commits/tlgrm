"""Client side of the control socket: detect a running server and send requests.
Used by the CLI's dual-mode resolver and (later) the MCP bridge."""

import os
import socket
import asyncio
import itertools

from .server.protocol import read_message, write_message, request

_ids = itertools.count(1)


def socket_path():
    return os.getenv("TG_SERVER_SOCK", os.path.expanduser("~/.tlgrm/server.sock"))


def is_server_running():
    """True if a server is accepting connections on the socket."""
    path = socket_path()
    if not os.path.exists(path):
        return False
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(path)
        return True
    except OSError:
        return False
    finally:
        s.close()


async def request_async(cmd, account=None, args=None, tier="destructive"):
    reader, writer = await asyncio.open_unix_connection(socket_path())
    try:
        await write_message(writer, request(next(_ids), cmd, account, args, tier))
        return await read_message(reader)
    finally:
        writer.close()


def request_sync(cmd, account=None, args=None, tier="destructive"):
    return asyncio.run(request_async(cmd, account, args, tier))
