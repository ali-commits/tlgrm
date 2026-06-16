"""Turn one decoded request into a response dict: tier check, run the command
against the account's hot client, map exceptions to error responses."""

from types import SimpleNamespace

from ..execute import execute
from .protocol import ok, err
from .tiers import is_allowed


async def handle_request(manager, req):
    rid = req.get("id")
    cmd = req.get("cmd")
    if cmd == "ping":
        return ok(rid, {"pong": True})
    if not is_allowed(req.get("tier", "read"), cmd):
        return err(rid, "PermissionError",
                   f"'{cmd}' requires a higher permission tier")
    try:
        client = await manager.get(req.get("account"))
        args = SimpleNamespace(command=cmd, **(req.get("args") or {}))
        data = await execute(client, args)
        return ok(rid, data)
    except Exception as e:  # noqa: BLE001 — every failure becomes a response
        return err(rid, type(e).__name__, str(e))
