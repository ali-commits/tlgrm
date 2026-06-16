"""Newline-delimited JSON framing for the local control socket."""

import asyncio
import json
from typing import Any


async def read_message(reader: asyncio.StreamReader) -> dict[str, Any] | None:
    """Read one NDJSON message, or None at EOF."""
    line = await reader.readline()
    if not line:
        return None
    body: dict[str, Any] = json.loads(line.decode())
    return body


async def write_message(writer: asyncio.StreamWriter, obj: dict[str, Any]) -> None:
    writer.write((json.dumps(obj) + "\n").encode())
    await writer.drain()


def request(
    rid: Any,
    cmd: str,
    account: str | None = None,
    args: dict[str, Any] | None = None,
    tier: str = "destructive",
) -> dict[str, Any]:
    return {"id": rid, "cmd": cmd, "account": account, "args": args or {}, "tier": tier}


def ok(rid: Any, data: Any) -> dict[str, Any]:
    return {"id": rid, "ok": True, "data": data}


def err(rid: Any, etype: str, message: str) -> dict[str, Any]:
    return {"id": rid, "ok": False, "error": {"type": etype, "message": message}}
