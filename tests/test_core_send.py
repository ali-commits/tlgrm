# tests/test_core_send.py
from types import SimpleNamespace
from unittest.mock import AsyncMock
from tlgrm.core import messages


async def test_send_text_calls_client_and_returns_dict():
    client = SimpleNamespace(
        send_message=AsyncMock(return_value=SimpleNamespace(id=99))
    )
    result = await messages.send(client, "738667936", text="hi")
    client.send_message.assert_awaited_once_with(
        738667936, "hi", reply_to=None, silent=False
    )
    assert result == {
        "message_id": 99,
        "to": "738667936",
        "text": "hi",
        "media_type": None,
    }


async def test_send_file_marks_voice():
    client = SimpleNamespace(send_file=AsyncMock(return_value=SimpleNamespace(id=7)))
    result = await messages.send(client, "@u", file_path="a.ogg", voice=True)
    client.send_file.assert_awaited_once_with(
        "@u", "a.ogg", caption=None, voice_note=True, reply_to=None, silent=False
    )
    assert result["media_type"] == "voice" and result["message_id"] == 7
