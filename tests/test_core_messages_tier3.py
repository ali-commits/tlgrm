import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from tlgrm.core import messages


async def test_schedule_message_passes_schedule():
    client = AsyncMock()
    client.send_message = AsyncMock(return_value=SimpleNamespace(id=42))
    when = datetime.timedelta(minutes=10)
    out = await messages.schedule_message(client, "123", when, text="later")
    client.send_message.assert_awaited_once_with(123, "later", schedule=when)
    assert out == {"scheduled": True, "message_id": 42, "to": "123"}


async def test_send_poll_builds_and_sends():
    client = AsyncMock()
    client.send_message = AsyncMock(return_value=SimpleNamespace(id=7))
    out = await messages.send_poll(client, "123", "Fav color?", ["Red", "Blue"])
    # Sent via file= media kwarg
    assert client.send_message.await_args.kwargs.get("file") is not None
    assert out["message_id"] == 7 and out["options"] == ["Red", "Blue"]
