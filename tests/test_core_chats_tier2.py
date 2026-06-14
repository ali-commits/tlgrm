from unittest.mock import AsyncMock
from tlgrm.core import chats


async def test_pin_calls_client():
    client = AsyncMock()
    out = await chats.pin(client, "123", 5)
    client.pin_message.assert_awaited_once_with(123, 5, notify=False)
    assert out == {"pinned": True, "target": "123", "message_id": 5}


async def test_unpin_specific():
    client = AsyncMock()
    out = await chats.unpin(client, "123", 5)
    client.unpin_message.assert_awaited_once_with(123, 5)
    assert out["unpinned"] is True and out["message_id"] == 5


async def test_mute_forever_sends_request():
    client = AsyncMock()
    client.get_input_entity = AsyncMock(return_value="INPUT")
    out = await chats.mute(client, "123")
    assert client.await_count == 1  # the UpdateNotifySettingsRequest
    assert out["muted"] is True and out["mute_until"] == 2**31 - 1


async def test_unmute_sends_request():
    client = AsyncMock()
    client.get_input_entity = AsyncMock(return_value="INPUT")
    out = await chats.unmute(client, "123")
    assert out == {"muted": False, "target": "123"}
