from types import SimpleNamespace
from unittest.mock import AsyncMock
import pytest
from tlgrm.core import messages
from tlgrm.core.errors import MessageNotFoundError


class _AsyncIter:
    def __init__(self, items):
        self._items = items

    def __aiter__(self):
        async def gen():
            for it in self._items:
                yield it

        return gen()


def _msg(**kw):
    base = {
        "id": 1,
        "chat_id": 10,
        "date": None,
        "sender_id": 2,
        "text": "x",
        "media": None,
        "photo": None,
        "voice": None,
        "video": None,
        "audio": None,
        "document": None,
    }
    base.update(kw)
    m = SimpleNamespace(**base)
    m.get_sender = AsyncMock(return_value=None)
    return m


async def test_search_global_uses_none_entity():
    captured = {}

    def iter_messages(entity, search=None, limit=None):
        captured["entity"] = entity
        captured["search"] = search
        return _AsyncIter([_msg(id=5)])

    client = SimpleNamespace(iter_messages=iter_messages)
    out = await messages.search(client, "hello", target=None, limit=20)
    assert captured["entity"] is None and captured["search"] == "hello"
    assert out[0]["id"] == 5


async def test_search_in_chat_resolves_target():
    captured = {}

    def iter_messages(entity, search=None, limit=None):
        captured["entity"] = entity
        return _AsyncIter([])

    client = SimpleNamespace(iter_messages=iter_messages)
    await messages.search(client, "q", target="123", limit=5)
    assert captured["entity"] == 123


async def test_mark_read_all():
    client = SimpleNamespace(send_read_acknowledge=AsyncMock())
    out = await messages.mark_read(client, "123")
    client.send_read_acknowledge.assert_awaited_once_with(123)
    assert out == {"read": True, "target": "123", "max_id": None}


async def test_download_missing_message_raises():
    client = SimpleNamespace(get_messages=AsyncMock(return_value=None))
    with pytest.raises(MessageNotFoundError):
        await messages.download(client, "123", 7)


async def test_download_no_media_raises():
    from tlgrm.core.errors import TlgrmError

    client = SimpleNamespace(
        get_messages=AsyncMock(return_value=SimpleNamespace(id=7)),
        download_media=AsyncMock(return_value=None),
    )
    with pytest.raises(TlgrmError):
        await messages.download(client, "123", 7)


async def test_history_passes_offset_id():
    captured = {}

    def iter_messages(entity, limit=None, offset_id=None):
        captured["offset_id"] = offset_id
        return _AsyncIter([])

    client = SimpleNamespace(iter_messages=iter_messages)
    await messages.get_history(client, "123", limit=10, offset_id=50)
    assert captured["offset_id"] == 50
