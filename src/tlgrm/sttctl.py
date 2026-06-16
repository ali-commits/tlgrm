"""CLI-side handlers for live STT config. Writes the server-global [stt] section
and, if a server is running, asks it to drop cached models so the change applies."""

from typing import Any

from . import accounts, ipc
from .output import emit
from .stt import settings


def _set_stt(**fields: Any) -> None:
    cfg = accounts.load_config()
    stt = cfg.setdefault("stt", {})
    for k, v in fields.items():
        if v is not None:
            stt[k] = v
    accounts.save_config(cfg)
    if ipc.is_server_running():
        ipc.request_sync("stt_reload", args={}, tier="read")


def set_enabled(enabled: bool) -> None:
    _set_stt(enabled=bool(enabled))
    emit({"success": True, **settings.stt_settings()})


def set_config(
    backend: str | None = None,
    model: str | None = None,
    device: str | None = None,
) -> None:
    _set_stt(backend=backend, model=model, device=device)
    emit({"success": True, **settings.stt_settings()})


def status() -> None:
    out: dict[str, Any] = {"success": True, **settings.stt_settings()}
    # The warm models live in the server process, so report them only when it's up.
    if ipc.is_server_running():
        resp = ipc.request_sync("stt_status", args={}, tier="read")
        if isinstance(resp, dict) and resp.get("ok"):
            out["loaded"] = resp["data"].get("loaded", [])
    emit(out)
