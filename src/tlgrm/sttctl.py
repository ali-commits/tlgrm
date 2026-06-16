"""CLI-side handlers for live STT config. Writes the server-global [stt] section
and, if a server is running, asks it to drop cached models so the change applies."""

from . import accounts, ipc
from .output import emit
from .stt import settings


def _set_stt(**fields):
    cfg = accounts.load_config()
    stt = cfg.setdefault("stt", {})
    for k, v in fields.items():
        if v is not None:
            stt[k] = v
    accounts.save_config(cfg)
    if ipc.is_server_running():
        ipc.request_sync("stt_reload", args={}, tier="read")


def set_enabled(enabled):
    _set_stt(enabled=bool(enabled))
    emit({"success": True, **settings.stt_settings()})


def set_config(backend=None, model=None, device=None):
    _set_stt(backend=backend, model=model, device=device)
    emit({"success": True, **settings.stt_settings()})


def status():
    emit({"success": True, **settings.stt_settings()})
