"""Message operations: send, reply, edit, delete, history, search, read, download."""

import os

from .client import resolve_target
from .errors import MessageNotFoundError, TlgrmError
from .serialize import serialize_history_message, serialize_search_message


async def send(client, target, *, text=None, file_path=None, caption=None,
               voice=False, reply_to=None, silent=False):
    """Send a text message or a file/voice note. Returns a result dict."""
    resolved = resolve_target(target)
    if file_path:
        msg = await client.send_file(resolved, file_path, caption=caption or text,
                                     voice_note=voice, reply_to=reply_to, silent=silent)
        media_type = "voice" if voice else "file"
    else:
        msg = await client.send_message(resolved, text, reply_to=reply_to, silent=silent)
        media_type = None
    return {"message_id": msg.id, "to": target,
            "text": text or caption, "media_type": media_type}


async def edit(client, target, message_id, text):
    """Edit a previously sent message. Returns a result dict."""
    msg = await client.edit_message(resolve_target(target), int(message_id), text)
    return {"message_id": msg.id, "to": target, "text": text}


async def delete(client, target, message_ids):
    """Delete one or more messages. Returns a result dict."""
    ids = [int(x) for x in message_ids]
    await client.delete_messages(resolve_target(target), ids)
    return {"deleted_ids": ids, "from": target}


async def get_history(client, target, limit=10, offset_id=0):
    """Return a list of serialized recent messages (newest first)."""
    resolved = resolve_target(target)
    out = []
    async for msg in client.iter_messages(resolved, limit=limit, offset_id=offset_id):
        sender = await msg.get_sender()
        out.append(serialize_history_message(msg, sender))
    return out


async def search(client, query, target=None, limit=20):
    """Search messages. With a target, searches that chat; otherwise global."""
    entity = resolve_target(target) if target is not None else None
    out = []
    async for msg in client.iter_messages(entity, search=query, limit=limit):
        sender = await msg.get_sender()
        out.append(serialize_search_message(msg, sender))
    return out


async def mark_read(client, target, max_id=None):
    """Mark a chat (or up to max_id) as read."""
    entity = resolve_target(target)
    if max_id is not None:
        await client.send_read_acknowledge(entity, max_id=int(max_id))
    else:
        await client.send_read_acknowledge(entity)
    return {"read": True, "target": target,
            "max_id": int(max_id) if max_id is not None else None}


async def download(client, target, message_id, output=None):
    """Download media from a specific message. Returns the saved local path."""
    from ..config import DOWNLOADS_DIR
    msg = await client.get_messages(resolve_target(target), ids=int(message_id))
    if msg is None:
        raise MessageNotFoundError(f"Message {message_id} not found in {target}.")
    path = await client.download_media(msg, file=output or DOWNLOADS_DIR)
    if path is None:
        raise TlgrmError(f"Message {message_id} in {target} has no downloadable media.")
    return {"message_id": int(message_id), "from": target,
            "local_path": os.path.abspath(path)}


async def forward(client, from_chat, to_chat, message_ids):
    """Forward messages from one chat to another. Returns new message IDs."""
    ids = [int(x) for x in message_ids]
    result = await client.forward_messages(resolve_target(to_chat), ids,
                                           resolve_target(from_chat))
    sent = result if isinstance(result, list) else [result]
    return {"forwarded_ids": ids, "from": from_chat, "to": to_chat,
            "new_message_ids": [m.id for m in sent if m is not None]}


async def react(client, target, message_id, emoji, big=False):
    """Send (or, with empty emoji, clear) an emoji reaction on a message."""
    from telethon.tl.functions.messages import SendReactionRequest
    from telethon.tl import types
    reaction = [types.ReactionEmoji(emoticon=emoji)] if emoji else []
    peer = await client.get_input_entity(resolve_target(target))
    await client(SendReactionRequest(peer=peer, msg_id=int(message_id),
                                     reaction=reaction, big=big))
    return {"reacted": bool(emoji), "target": target,
            "message_id": int(message_id), "emoji": emoji}


async def schedule_message(client, target, when, text=None):
    """Schedule a text message to send at `when` (datetime or timedelta)."""
    msg = await client.send_message(resolve_target(target), text, schedule=when)
    return {"scheduled": True, "message_id": msg.id, "to": target}


async def send_poll(client, target, question, options, multiple=False,
                    quiz=False, correct=None):
    """Send a poll or quiz to a chat."""
    from telethon.tl import types
    answers = [types.PollAnswer(text=types.TextWithEntities(text=opt, entities=[]),
                                option=bytes([i])) for i, opt in enumerate(options)]
    poll = types.Poll(id=0, question=types.TextWithEntities(text=question, entities=[]),
                      answers=answers, hash=0, multiple_choice=multiple, quiz=quiz)
    correct_answers = [bytes([int(correct)])] if (quiz and correct is not None) else None
    media = types.InputMediaPoll(poll=poll, correct_answers=correct_answers)
    msg = await client.send_message(resolve_target(target), file=media)
    return {"message_id": msg.id, "to": target,
            "question": question, "options": list(options)}
