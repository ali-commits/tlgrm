"""One incoming-message listener per account, bound to the account's hot client.
State is rebuilt from persisted config on `reload()`."""

import logging

from telethon import events

from .. import listen_core

logger = logging.getLogger("tlgrm-server")


class AccountListener:
    def __init__(self, client, account_name):
        self.client = client
        self.account = account_name
        self.state = listen_core.ListenState()
        self.account_obj = {"name": account_name, "id": None}
        self._handler = None
        self._pending = set()

    async def reload(self):
        """Rebuild listen state (enabled, webhook, filters) from config."""
        from .. import accounts
        cfg = accounts.listen_config(self.account)
        st = listen_core.ListenState()
        st.enabled = cfg["enabled"]
        st.webhook_url = cfg["webhook_url"]
        st.headers = listen_core.parse_headers(cfg["webhook_headers"])
        st.mode = cfg["filter"]["mode"]
        st.ids, st.names = await listen_core._resolve_filters(
            self.client, cfg["filter"]["list"])
        win = cfg.get("window")
        st.window = listen_core._parse_window(win) if win else None
        self.state = st
        if self.account_obj["id"] is None:
            me = await self.client.get_me()
            self.account_obj = {"name": self.account, "id": me.id}

    def start(self):
        if self._handler is not None:
            return

        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event):
            if not self.state.enabled:
                return
            try:
                await listen_core.process_event(
                    event, self.state, account=self.account_obj, pending=self._pending)
            except Exception as e:
                logger.error(f"[{self.account}] listener error: {e}")

        self._handler = handler

    def stop(self):
        if self._handler is not None:
            self.client.remove_event_handler(self._handler)
            self._handler = None
