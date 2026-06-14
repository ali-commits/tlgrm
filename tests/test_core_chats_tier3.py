from types import SimpleNamespace
from unittest.mock import AsyncMock
from tlgrm.core import chats


async def test_create_group_returns_id():
    client = AsyncMock(return_value=SimpleNamespace(chats=[SimpleNamespace(id=555)]))
    out = await chats.create_group(client, "My Group")
    assert out["created"] is True and out["id"] == 555 and out["type"] == "group"


async def test_leave_calls_delete_dialog():
    client = AsyncMock()
    out = await chats.leave(client, "123")
    client.delete_dialog.assert_awaited_once_with(123)
    assert out == {"left": True, "target": "123"}
