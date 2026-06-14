from types import SimpleNamespace
from unittest.mock import AsyncMock
from tlgrm.core import users, chats


async def test_whoami_serializes_me():
    me = SimpleNamespace(id=1, first_name="Me", last_name=None, username="me",
                         phone="123", bot=False)
    client = SimpleNamespace(get_me=AsyncMock(return_value=me))
    out = await users.whoami(client)
    assert out["id"] == 1 and out["username"] == "me"


async def test_user_info_resolves_and_serializes():
    u = SimpleNamespace(id=9, first_name="U", last_name=None, username=None,
                        phone=None, bot=False)
    client = SimpleNamespace(get_entity=AsyncMock(return_value=u))
    out = await users.user_info(client, "@u")
    client.get_entity.assert_awaited_once_with("@u")
    assert out["id"] == 9


async def test_chat_info_skips_count_for_user():
    from telethon.tl.types import User
    u = User(id=3, first_name="A", access_hash=0)
    client = SimpleNamespace(get_entity=AsyncMock(return_value=u))
    out = await chats.chat_info(client, "123")
    assert out["type"] == "user" and out["participants_count"] is None
