"""User/participant operations."""

from .client import resolve_target
from .serialize import serialize_member, serialize_user


async def get_members(client, target):
    """Return a list of serialized participants for a group/channel."""
    out = []
    async for user in client.iter_participants(resolve_target(target)):
        out.append(serialize_member(user))
    return out


async def whoami(client):
    """Return the logged-in account, serialized."""
    return serialize_user(await client.get_me())


async def user_info(client, target):
    """Resolve and serialize a user (or other entity) by target."""
    entity = await client.get_entity(resolve_target(target))
    return serialize_user(entity)


async def add_members(client, target, members):
    """Add users to a group/channel."""
    from telethon.tl.functions.channels import InviteToChannelRequest
    entity = await client.get_entity(resolve_target(target))
    await client(InviteToChannelRequest(entity, [resolve_target(m) for m in members]))
    return {"added": [str(m) for m in members], "target": target}


async def remove_members(client, target, members):
    """Remove (kick) users from a group/channel."""
    entity = await client.get_entity(resolve_target(target))
    removed = []
    for m in members:
        await client.kick_participant(entity, resolve_target(m))
        removed.append(str(m))
    return {"removed": removed, "target": target}
