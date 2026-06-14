"""Maps parsed CLI args to core operations and emits their JSON results."""

import datetime

from .core.client import get_client, open_client
from .core import messages, chats, users
from .output import emit


def _parse_when(value):
    """Parse a schedule time: integer seconds-from-now, or ISO-8601 datetime."""
    if value.isdigit():
        return datetime.timedelta(seconds=int(value))
    return datetime.datetime.fromisoformat(value)


async def _login():
    client = get_client()
    print("Connecting to Telegram and starting interactive authorization...")
    await client.start()
    me = await client.get_me()
    print(f"\nSuccessfully logged in as: {me.first_name} "
          f"(@{me.username or 'No Username'}) [ID: {me.id}]")
    await client.disconnect()


async def run_command(args):
    """Run an authenticated command and emit its result."""
    if args.command == "login":
        await _login()
        return
    async with open_client() as client:
        if args.command == "chats":
            emit(await chats.list_chats(client, args.limit))
        elif args.command == "send":
            emit({"success": True, **await messages.send(
                client, args.target, text=args.text, file_path=args.file,
                caption=args.caption, voice=args.voice,
                reply_to=args.reply_to, silent=args.silent)})
        elif args.command == "reply":
            emit({"success": True, **await messages.send(
                client, args.target, text=args.text, file_path=args.file,
                caption=args.caption, voice=args.voice,
                reply_to=args.message_id, silent=args.silent)})
        elif args.command == "edit":
            emit({"success": True, **await messages.edit(
                client, args.target, args.message_id, args.text)})
        elif args.command == "delete":
            emit({"success": True, **await messages.delete(
                client, args.target, args.message_ids)})
        elif args.command == "history":
            emit(await messages.get_history(client, args.target, args.limit, args.offset_id))
        elif args.command == "search":
            emit(await messages.search(client, args.query, args.target, args.limit))
        elif args.command == "read":
            emit({"success": True, **await messages.mark_read(client, args.target, args.max_id)})
        elif args.command == "download":
            emit({"success": True, **await messages.download(
                client, args.target, args.message_id, args.output)})
        elif args.command == "whoami":
            emit(await users.whoami(client))
        elif args.command == "user-info":
            emit(await users.user_info(client, args.target))
        elif args.command == "chat-info":
            emit(await chats.chat_info(client, args.target))
        elif args.command == "members":
            emit(await users.get_members(client, args.target))
        elif args.command == "forward":
            emit({"success": True, **await messages.forward(
                client, args.from_chat, args.to_chat, args.message_ids)})
        elif args.command == "react":
            emit({"success": True, **await messages.react(
                client, args.target, args.message_id, args.emoji, args.big)})
        elif args.command == "pin":
            emit({"success": True, **await chats.pin(
                client, args.target, args.message_id, args.notify)})
        elif args.command == "unpin":
            emit({"success": True, **await chats.unpin(
                client, args.target, args.message_id)})
        elif args.command == "mute":
            emit({"success": True, **await chats.mute(client, args.target, args.duration)})
        elif args.command == "unmute":
            emit({"success": True, **await chats.unmute(client, args.target)})
        elif args.command == "saved":
            emit({"success": True, **await messages.send(
                client, "me", text=args.text, file_path=args.file,
                caption=args.caption, voice=args.voice)})
        elif args.command == "create-group":
            emit({"success": True, **await chats.create_group(
                client, args.title, args.members, args.channel)})
        elif args.command == "add-members":
            emit({"success": True, **await users.add_members(
                client, args.target, args.members)})
        elif args.command == "remove-members":
            emit({"success": True, **await users.remove_members(
                client, args.target, args.members)})
        elif args.command == "leave":
            emit({"success": True, **await chats.leave(client, args.target)})
        elif args.command == "schedule":
            emit({"success": True, **await messages.schedule_message(
                client, args.target, _parse_when(args.at), args.text)})
        elif args.command == "poll":
            emit({"success": True, **await messages.send_poll(
                client, args.target, args.question, args.options,
                args.multiple, args.quiz, args.correct)})
