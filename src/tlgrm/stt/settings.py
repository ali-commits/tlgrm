"""STT backend selection from environment and ~/.tlgrm/config.toml.

Precedence: TG_STT_BACKEND env > config file [stt].backend >
auto-detect from a cloud API key > faster-whisper (default).
"""

import os
import logging
from typing import Any

logger = logging.getLogger("tlgrm-stt")

# Cloud backends in auto-detect precedence order: (backend_name, key_env_var)
CLOUD_KEY_ENV = [
    ("openai", "OPENAI_API_KEY"),
    ("groq", "GROQ_API_KEY"),
    ("deepgram", "DEEPGRAM_API_KEY"),
    ("elevenlabs", "ELEVENLABS_API_KEY"),
    ("google", "GOOGLE_API_KEY"),
]


def _config_path() -> str:
    return os.getenv("TG_CONFIG_PATH", os.path.expanduser("~/.tlgrm/config.toml"))


def _load_config() -> dict[str, Any]:
    """Return the [stt] table from the config file, or {} if absent/unparseable."""
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib
        except ModuleNotFoundError:
            return {}
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            stt: dict[str, Any] = tomllib.load(f).get("stt", {})
            return stt
    except Exception as e:
        logger.warning(f"Could not read STT config from {path}: {e}")
        return {}


def resolve_backend() -> str:
    """Resolve the active STT backend name."""
    env = os.getenv("TG_STT_BACKEND")
    if env:
        return env.strip().lower()
    cfg = _load_config()
    if cfg.get("backend"):
        return str(cfg["backend"]).strip().lower()
    for name, key_env in CLOUD_KEY_ENV:
        if os.getenv(key_env):
            return name
    return "faster-whisper"


def resolve_model() -> str | None:
    """Resolve the configured model name, or None to use the backend default."""
    model: str | None = os.getenv("TG_STT_MODEL") or _load_config().get("model")
    return model


def resolve_device() -> str | None:
    """Explicit STT device ('cpu'/'cuda'/'auto'), or None to auto-detect.
    Precedence: TG_STT_DEVICE env > [stt].device > None (auto)."""
    device: str | None = os.getenv("TG_STT_DEVICE") or _load_config().get("device")
    return device


def is_enabled() -> bool:
    """Whether incoming-voice auto-transcription is on (default True)."""
    return bool(_load_config().get("enabled", True))


def stt_settings() -> dict[str, Any]:
    """Status snapshot for `tlgrm stt status`."""
    return {
        "enabled": is_enabled(),
        "backend": resolve_backend(),
        "model": resolve_model(),
        "device": resolve_device() or "auto",
    }
