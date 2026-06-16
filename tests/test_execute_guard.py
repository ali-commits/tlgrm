import types
import asyncio
import pytest
from tlgrm import execute as ex, accounts


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    return tmp_path


def test_execute_blocks_guarded_write(tmp_home):
    accounts.filter_add("work", "write", ["@boss"])
    args = types.SimpleNamespace(
        command="send",
        target="@boss",
        text="hi",
        file=None,
        caption=None,
        voice=False,
        reply_to=None,
        silent=False,
    )
    with pytest.raises(PermissionError):
        asyncio.run(ex.execute(object(), args, account="work"))


def test_execute_allows_unguarded_target(tmp_home, monkeypatch):
    sent = {}

    class _Msgs:
        async def send(self, client, target, **kw):
            sent["target"] = target
            return {"id": 1}

    monkeypatch.setattr(ex, "messages", _Msgs())
    args = types.SimpleNamespace(
        command="send",
        target="@ok",
        text="hi",
        file=None,
        caption=None,
        voice=False,
        reply_to=None,
        silent=False,
    )
    out = asyncio.run(ex.execute(object(), args, account="work"))
    assert out["success"] and sent["target"] == "@ok"
