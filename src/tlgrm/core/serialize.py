"""Pure object -> dict serializers shared by the CLI, MCP server, and webhooks.
All functions are synchronous and take already-fetched Telethon objects."""

from telethon import utils


def media_type(msg):
    """Return a coarse media type string, or None if the message has no media."""
    if not getattr(msg, "media", None):
        return None
    if getattr(msg, "photo", None):
        return "photo"
    if getattr(msg, "voice", None):
        return "voice"
    if getattr(msg, "video", None):
        return "video"
    if getattr(msg, "audio", None):
        return "audio"
    if getattr(msg, "document", None):
        return "document"
    return "other"


def is_self_destruct(msg):
    """True if the message's media is self-destructing (has a TTL).

    Per the Telegram API ToS (§1.4), self-destructing content must not be
    preserved, so callers should skip persisting it.
    """
    media = getattr(msg, "media", None)
    return bool(getattr(media, "ttl_seconds", None)) if media else False


def serialize_dialog(dialog):
    """Serialize a Telethon Dialog for `chats`."""
    entity = dialog.entity
    if dialog.is_user:
        entity_type = "user"
    elif dialog.is_group:
        entity_type = "group"
    elif dialog.is_channel:
        entity_type = "channel"
    else:
        entity_type = "unknown"
    return {
        "id": dialog.id,
        "name": dialog.name,
        "username": getattr(entity, "username", None),
        "type": entity_type,
        "unread_count": dialog.unread_count,
    }


def serialize_history_message(msg, sender):
    """Serialize one message for `history` (sender flattened in)."""
    return {
        "id": msg.id,
        "date": msg.date.isoformat() if msg.date else "",
        "sender_id": msg.sender_id,
        "sender_name": utils.get_display_name(sender) if sender else "Unknown",
        "text": msg.text or "",
        "media_type": media_type(msg),
    }


def serialize_member(user):
    """Serialize a participant for `members`."""
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name or "",
        "username": user.username or "",
        "phone": user.phone or "",
        "is_bot": user.bot,
    }


def serialize_sender(sender):
    """Serialize a message sender for webhook payloads."""
    return {
        "id": getattr(sender, "id", None),
        "first_name": getattr(sender, "first_name", ""),
        "last_name": getattr(sender, "last_name", ""),
        "username": getattr(sender, "username", ""),
        "phone": getattr(sender, "phone", ""),
        "display_name": utils.get_display_name(sender) if sender else "Unknown",
    }


def serialize_chat(chat, chat_type):
    """Serialize a chat for webhook payloads."""
    return {
        "id": getattr(chat, "id", None),
        "name": utils.get_display_name(chat) if chat else "Unknown",
        "username": getattr(chat, "username", ""),
        "type": chat_type,
    }


def serialize_user(user):
    """Serialize a User for whoami / user-info."""
    return {
        "id": user.id,
        "first_name": getattr(user, "first_name", None) or "",
        "last_name": getattr(user, "last_name", None) or "",
        "username": getattr(user, "username", None) or "",
        "phone": getattr(user, "phone", None) or "",
        "is_bot": getattr(user, "bot", False),
        "display_name": utils.get_display_name(user),
    }


def serialize_chat_info(entity, participants_count=None):
    """Serialize any entity (user/group/channel) for chat-info."""
    from telethon.tl.types import User
    if isinstance(entity, User):
        etype = "user"
    elif getattr(entity, "broadcast", False):
        etype = "channel"
    elif getattr(entity, "megagroup", False) or entity.__class__.__name__ == "Chat":
        etype = "group"
    else:
        etype = "unknown"
    return {
        "id": entity.id,
        "name": utils.get_display_name(entity),
        "username": getattr(entity, "username", None) or "",
        "type": etype,
        "participants_count": participants_count,
    }


def serialize_search_message(msg, sender):
    """Serialize a search hit (includes chat_id since results can span chats)."""
    return {
        "id": msg.id,
        "chat_id": msg.chat_id,
        "date": msg.date.isoformat() if msg.date else "",
        "sender_id": msg.sender_id,
        "sender_name": utils.get_display_name(sender) if sender else "Unknown",
        "text": msg.text or "",
        "media_type": media_type(msg),
    }
