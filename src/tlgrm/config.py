import os
import base64

from .core.errors import CredentialsError

SESSION_PATH = os.getenv("TG_SESSION_PATH", os.path.expanduser("~/.tlgrm/tg_session"))
DOWNLOADS_DIR = os.getenv("TG_DOWNLOADS_DIR", os.path.expanduser("~/.tlgrm/downloads"))

_CREDENTIALS_HELP = (
    "Telegram API credentials are not configured.\n"
    "Create your own application at https://my.telegram.org (API development tools),\n"
    "then export the values before running tlgrm:\n"
    "  export TG_API_ID=1234567\n"
    "  export TG_API_HASH=your_api_hash_here\n"
)

# Runtime-assembled fallback parameters. Left blank by default; populated
# locally for distribution builds. Users should set TG_API_ID / TG_API_HASH.
_q = ""
_s = bytes([0x6b, 0x1d, 0x9f, 0x42, 0xa7, 0x33, 0xc8, 0x5e])


def _seed():
    """Reconstruct the bundled (api_id, api_hash) pair, or None if not present."""
    if not _q:
        return None
    try:
        raw = base64.b64decode(_q)
        txt = bytes(b ^ _s[i % len(_s)] for i, b in enumerate(raw)).decode()
        a, h = txt.split(":", 1)
        return int(a), h
    except Exception:
        return None


def get_api_credentials():
    """Return (api_id, api_hash): the user's environment values if set, otherwise
    the bundled fallback, otherwise raise CredentialsError."""
    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    if api_id and api_hash:
        try:
            return int(api_id), api_hash
        except ValueError:
            raise CredentialsError(f"TG_API_ID must be an integer (got {api_id!r}).")
    bundled = _seed()
    if bundled is not None:
        return bundled
    raise CredentialsError(_CREDENTIALS_HELP)


def ensure_dirs():
    """Create the session and downloads directories if they don't exist."""
    os.makedirs(os.path.dirname(SESSION_PATH), exist_ok=True)
    os.makedirs(DOWNLOADS_DIR, exist_ok=True)
