"""Turn one decoded request into a response dict: tier check, run the command
against the account's hot client, map exceptions to error responses."""

from ..execute import execute
from .protocol import ok, err
from .tiers import is_allowed


class _Args:
    """Namespace whose unset attributes read as None, so a client may send only
    the fields a command needs (the rest default to None)."""
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        return None


async def handle_request(manager, req):
    rid = req.get("id")
    cmd = req.get("cmd")
    if cmd == "ping":
        return ok(rid, {"pong": True})
    if cmd == "reload":
        if not is_allowed(req.get("tier", "read"), "reload"):
            return err(rid, "PermissionError", "'reload' requires a higher tier")
        await manager.reload_listener(req.get("account"))
        return ok(rid, {"reloaded": req.get("account")})
    if cmd == "stt_reload":
        if not is_allowed(req.get("tier", "read"), "stt_reload"):
            return err(rid, "PermissionError", "'stt_reload' requires a higher tier")
        from .. import stt
        stt.reset_models()
        return ok(rid, {"stt_reloaded": True})
    if cmd == "stt_status":
        from ..stt import local
        loaded = ["/".join(str(p) for p in k) for k in sorted(local._models)]
        return ok(rid, {"loaded": loaded})
    if not is_allowed(req.get("tier", "read"), cmd):
        return err(rid, "PermissionError",
                   f"'{cmd}' requires a higher permission tier")
    try:
        client = await manager.get(req.get("account"))
        args = _Args(command=cmd, **(req.get("args") or {}))
        data = await execute(client, args, account=req.get("account"))
        return ok(rid, data)
    except Exception as e:  # noqa: BLE001 — every failure becomes a response
        return err(rid, type(e).__name__, str(e))
