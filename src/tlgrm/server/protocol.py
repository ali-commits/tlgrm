"""Newline-delimited JSON framing for the local control socket."""

import json


async def read_message(reader):
    """Read one NDJSON message, or None at EOF."""
    line = await reader.readline()
    if not line:
        return None
    return json.loads(line.decode())


async def write_message(writer, obj):
    writer.write((json.dumps(obj) + "\n").encode())
    await writer.drain()


def request(rid, cmd, account=None, args=None, tier="destructive"):
    return {"id": rid, "cmd": cmd, "account": account,
            "args": args or {}, "tier": tier}


def ok(rid, data):
    return {"id": rid, "ok": True, "data": data}


def err(rid, etype, message):
    return {"id": rid, "ok": False, "error": {"type": etype, "message": message}}
