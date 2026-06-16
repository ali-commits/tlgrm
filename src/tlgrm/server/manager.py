"""Owns one connected Telethon client per account for the lifetime of the
server. Clients are created lazily and reused (hot connections)."""

import logging

logger = logging.getLogger("tlgrm-server")


class AccountManager:
    def __init__(self):
        self._clients = {}  # account name -> connected TelegramClient
        self._listeners = {}  # account name -> AccountListener

    async def get(self, account=None):
        """Return a connected, authorized client for `account` (or the default),
        creating and connecting it on first use."""
        from ..accounts import resolve_account
        from ..core import client as core_client

        name = resolve_account(account)
        if name not in self._clients:
            c = core_client.get_client(name)
            await core_client.ensure_authorized(c)  # connect + check
            self._clients[name] = c
        return self._clients[name]

    async def start_listener(self, account=None):
        from ..accounts import resolve_account
        from .listener import AccountListener
        name = resolve_account(account)
        client = await self.get(name)
        if name not in self._listeners:
            lis = AccountListener(client, name)
            await lis.reload()
            lis.start()
            self._listeners[name] = lis
        return self._listeners[name]

    async def reload_listener(self, account=None):
        from ..accounts import resolve_account
        name = resolve_account(account)
        if name in self._listeners:
            await self._listeners[name].reload()
        else:
            await self.start_listener(name)

    async def load_all(self):
        """Connect every configured account; skip (with a warning) any that
        aren't authorized yet, so one bad account doesn't sink startup."""
        from ..accounts import load_config
        for name in load_config().get("accounts", {}):
            try:
                await self.get(name)
                await self.start_listener(name)
                logger.info(f"Connected account '{name}'.")
            except Exception as e:
                logger.warning(f"Skipping account '{name}': {e}")

    async def disconnect_all(self):
        for lis in self._listeners.values():
            try:
                lis.stop()
            except Exception:
                pass
        self._listeners.clear()
        for c in self._clients.values():
            try:
                await c.disconnect()
            except Exception:
                pass
        self._clients.clear()
