"""Chat/dialog operations."""

from telethon.tl.types import User

from .client import resolve_target
from .serialize import serialize_dialog, serialize_chat_info


async def list_chats(client, limit=20):
    """Return a list of serialized recent dialogs."""
    out = []
    async for dialog in client.iter_dialogs(limit=limit):
        out.append(serialize_dialog(dialog))
    return out


async def chat_info(client, target):
    """Describe a chat: type, name, username, and participant count when applicable."""
    entity = await client.get_entity(resolve_target(target))
    count = None
    if not isinstance(entity, User):
        try:
            count = (await client.get_participants(entity, limit=0)).total
        except Exception:
            count = None
    return serialize_chat_info(entity, count)


async def pin(client, target, message_id, notify=False):
    """Pin a message in a chat."""
    await client.pin_message(resolve_target(target), int(message_id), notify=notify)
    return {"pinned": True, "target": target, "message_id": int(message_id)}


async def unpin(client, target, message_id=None):
    """Unpin a specific message, or all pinned messages when message_id is None."""
    mid = int(message_id) if message_id is not None else None
    await client.unpin_message(resolve_target(target), mid)
    return {"unpinned": True, "target": target, "message_id": mid}


async def mute(client, target, duration=None):
    """Mute a chat. duration is seconds from now; None mutes effectively forever."""
    import time
    from telethon.tl import functions, types
    peer = await client.get_input_entity(resolve_target(target))
    mute_until = (2 ** 31 - 1) if duration is None else int(time.time()) + int(duration)
    await client(functions.account.UpdateNotifySettingsRequest(
        peer=types.InputNotifyPeer(peer),
        settings=types.InputPeerNotifySettings(mute_until=mute_until)))
    return {"muted": True, "target": target, "mute_until": mute_until}


async def unmute(client, target):
    """Unmute a chat."""
    from telethon.tl import functions, types
    peer = await client.get_input_entity(resolve_target(target))
    await client(functions.account.UpdateNotifySettingsRequest(
        peer=types.InputNotifyPeer(peer),
        settings=types.InputPeerNotifySettings(mute_until=0)))
    return {"muted": False, "target": target}


async def create_group(client, title, members=None, channel=False):
    """Create a supergroup (default) or broadcast channel; optionally add members."""
    from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest
    result = await client(CreateChannelRequest(
        title=title, about="", megagroup=not channel, broadcast=channel))
    new = result.chats[0]
    added = []
    if members:
        await client(InviteToChannelRequest(new, [resolve_target(m) for m in members]))
        added = [str(m) for m in members]
    return {"created": True, "id": new.id, "title": title,
            "type": "channel" if channel else "group", "added": added}


async def leave(client, target):
    """Leave a group/channel (removes the dialog)."""
    await client.delete_dialog(resolve_target(target))
    return {"left": True, "target": target}
