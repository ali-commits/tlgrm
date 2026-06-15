"""Client factory and connection lifecycle for the core layer."""

from contextlib import asynccontextmanager

from telethon import TelegramClient

from ..config import get_api_credentials, ensure_dirs, session_path
from .errors import NotAuthorizedError


def get_client():
    """Build a TelegramClient using the configured session and credentials.

    The session path is resolved at call time (config.session_path), so a
    `--session` flag or TG_SESSION_PATH set just before this call is honored.
    Raises CredentialsError (from get_api_credentials) if creds are unset.
    """
    ensure_dirs()
    api_id, api_hash = get_api_credentials()
    return TelegramClient(session_path(), api_id, api_hash)


def resolve_target(target):
    """Treat a numeric target as a chat ID; otherwise pass it through as-is."""
    try:
        return int(target)
    except (ValueError, TypeError):
        return target


async def ensure_authorized(client):
    """Connect the client and raise NotAuthorizedError if there's no session."""
    await client.connect()
    if not await client.is_user_authorized():
        raise NotAuthorizedError("Not authorized. Run 'tlgrm login' first.")


@asynccontextmanager
async def open_client():
    """Yield a connected, authorized client and always disconnect afterwards."""
    client = get_client()
    try:
        await ensure_authorized(client)
        yield client
    finally:
        await client.disconnect()
