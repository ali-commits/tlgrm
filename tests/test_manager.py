import asyncio
import pytest
from tlgrm.server.manager import AccountManager


def test_manager_connects_once_and_caches(monkeypatch):
    built = []

    class _FakeClient:
        def __init__(self, name): self.name = name; self.connected = False
        async def connect(self): self.connected = True
        async def is_user_authorized(self): return True
        async def disconnect(self): self.connected = False

    def fake_get_client(account=None, must_exist=True):
        built.append(account)
        return _FakeClient(account)

    import tlgrm.core.client as cc
    monkeypatch.setattr(cc, "get_client", fake_get_client)
    monkeypatch.setattr("tlgrm.accounts.resolve_account", lambda name=None: name or "default")

    async def go():
        m = AccountManager()
        c1 = await m.get("work")
        c2 = await m.get("work")
        assert c1 is c2           # cached, built once
        assert built == ["work"]
        assert c1.connected
        await m.disconnect_all()
        assert not c1.connected
    asyncio.run(go())


def test_manager_get_unauthorized_raises(monkeypatch):
    class _Unauth:
        async def connect(self): pass
        async def is_user_authorized(self): return False
        async def disconnect(self): pass

    import tlgrm.core.client as cc
    monkeypatch.setattr(cc, "get_client", lambda account=None, must_exist=True: _Unauth())
    monkeypatch.setattr("tlgrm.accounts.resolve_account", lambda name=None: name or "default")

    async def go():
        from tlgrm.core.errors import NotAuthorizedError
        m = AccountManager()
        with pytest.raises(NotAuthorizedError):
            await m.get("work")
    asyncio.run(go())


def test_manager_starts_and_reloads_listener(monkeypatch):
    class _FakeClient:
        def on(self, _e):
            def deco(fn): return fn
            return deco
        def remove_event_handler(self, fn): pass
        async def connect(self): pass
        async def is_user_authorized(self): return True
        async def disconnect(self): pass
        async def get_me(self): return type("Me", (), {"id": 1})()
        async def get_entity(self, t): raise ValueError("x")

    import tlgrm.core.client as cc
    monkeypatch.setattr(cc, "get_client", lambda account=None, must_exist=True: _FakeClient())
    monkeypatch.setattr("tlgrm.accounts.resolve_account", lambda name=None: name or "default")
    monkeypatch.setattr("tlgrm.accounts.listen_config", lambda name: {
        "enabled": True, "webhook_url": None, "webhook_headers": [],
        "filter": {"mode": "block", "list": []}})

    async def go():
        m = AccountManager()
        await m.get("work")
        lis = await m.start_listener("work")
        assert lis is m._listeners["work"]
        await m.reload_listener("work")     # should not raise
    __import__("asyncio").run(go())
