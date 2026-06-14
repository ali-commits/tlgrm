from unittest.mock import AsyncMock
from tlgrm.core import users


async def test_add_members_invites():
    client = AsyncMock()
    client.get_entity = AsyncMock(return_value="ENT")
    out = await users.add_members(client, "123", ["@a", "@b"])
    assert out == {"added": ["@a", "@b"], "target": "123"}


async def test_remove_members_kicks_each():
    client = AsyncMock()
    client.get_entity = AsyncMock(return_value="ENT")
    out = await users.remove_members(client, "123", ["@a", "@b"])
    assert client.kick_participant.await_count == 2
    assert out == {"removed": ["@a", "@b"], "target": "123"}
