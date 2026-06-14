from types import SimpleNamespace
from unittest.mock import AsyncMock
from tlgrm.core import messages


async def test_forward_returns_new_ids():
    client = AsyncMock()
    client.forward_messages = AsyncMock(return_value=[SimpleNamespace(id=11), SimpleNamespace(id=12)])
    out = await messages.forward(client, "src", "dst", ["1", "2"])
    client.forward_messages.assert_awaited_once_with("dst", [1, 2], "src")
    assert out == {"forwarded_ids": [1, 2], "from": "src", "to": "dst",
                   "new_message_ids": [11, 12]}


async def test_react_sends_reaction_request():
    client = AsyncMock()
    client.get_input_entity = AsyncMock(return_value="INPUT")
    out = await messages.react(client, "123", 5, "👍")
    assert client.await_count == 1  # the SendReactionRequest invocation
    assert out["reacted"] is True and out["emoji"] == "👍" and out["message_id"] == 5
