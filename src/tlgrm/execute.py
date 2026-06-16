"""Pure command dispatch: map parsed args to a core operation against a
connected client and RETURN the result dict. Shared by the direct CLI path and
the server, so it never prints or connects — callers own I/O."""

import datetime

from .core import messages, chats, users
from .core.errors import TlgrmError


def _parse_when(value):
    """Parse a schedule time: integer seconds-from-now, or ISO-8601 datetime."""
    if value.isdigit():
        return datetime.timedelta(seconds=int(value))
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        raise TlgrmError(
            f"Invalid --at time: {value!r} (use an ISO-8601 datetime or seconds-from-now).")


def _parse_duration(value):
    """Parse a relative delay like '90s', '30m', '2h', '1d' into a timedelta."""
    units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    v = value.strip().lower()
    if v and v[-1] in units and v[:-1].isdigit():
        return datetime.timedelta(**{units[v[-1]]: int(v[:-1])})
    if v.isdigit():
        return datetime.timedelta(seconds=int(v))
    raise TlgrmError(f"Invalid duration: {value!r} (use 90s, 30m, 2h, 1d).")


async def execute(client, args, account=None):
    """Run one command against a connected client; return its result dict."""
    from .write_guard import check_write
    check_write(account, args.command, args)
    cmd = args.command
    if cmd == "chats":
        return await chats.list_chats(client, args.limit)
    elif cmd == "send":
        return {"success": True, **await messages.send(
            client, args.target, text=args.text, file_path=args.file,
            caption=args.caption, voice=args.voice,
            reply_to=args.reply_to, silent=args.silent)}
    elif cmd == "reply":
        return {"success": True, **await messages.send(
            client, args.target, text=args.text, file_path=args.file,
            caption=args.caption, voice=args.voice,
            reply_to=args.message_id, silent=args.silent)}
    elif cmd == "edit":
        return {"success": True, **await messages.edit(
            client, args.target, args.message_id, args.text)}
    elif cmd == "delete":
        return {"success": True, **await messages.delete(
            client, args.target, args.message_ids)}
    elif cmd == "history":
        return await messages.get_history(client, args.target, args.limit, args.offset_id)
    elif cmd == "search":
        return await messages.search(client, args.query, args.target, args.limit)
    elif cmd == "read":
        return {"success": True, **await messages.mark_read(client, args.target, args.max_id)}
    elif cmd == "download":
        return {"success": True, **await messages.download(
            client, args.target, args.message_id, args.output)}
    elif cmd == "whoami":
        return await users.whoami(client)
    elif cmd == "user-info":
        return await users.user_info(client, args.target)
    elif cmd == "chat-info":
        return await chats.chat_info(client, args.target)
    elif cmd == "members":
        return await users.get_members(client, args.target)
    elif cmd == "forward":
        return {"success": True, **await messages.forward(
            client, args.from_chat, args.to_chat, args.message_ids)}
    elif cmd == "react":
        return {"success": True, **await messages.react(
            client, args.target, args.message_id, args.emoji, args.big)}
    elif cmd == "pin":
        return {"success": True, **await chats.pin(
            client, args.target, args.message_id, args.notify)}
    elif cmd == "unpin":
        return {"success": True, **await chats.unpin(client, args.target, args.message_id)}
    elif cmd == "mute":
        return {"success": True, **await chats.mute(client, args.target, args.duration)}
    elif cmd == "unmute":
        return {"success": True, **await chats.unmute(client, args.target)}
    elif cmd == "saved":
        return {"success": True, **await messages.send(
            client, "me", text=args.text, file_path=args.file,
            caption=args.caption, voice=args.voice)}
    elif cmd == "create-group":
        return {"success": True, **await chats.create_group(
            client, args.title, args.members, args.channel)}
    elif cmd == "add-members":
        return {"success": True, **await users.add_members(client, args.target, args.members)}
    elif cmd == "remove-members":
        return {"success": True, **await users.remove_members(client, args.target, args.members)}
    elif cmd == "leave":
        return {"success": True, **await chats.leave(client, args.target)}
    elif cmd == "schedule":
        sub = args.schedule_command
        if sub == "send":
            when = _parse_when(args.at) if args.at else _parse_duration(args.in_)
            return {"success": True, **await messages.schedule_message(
                client, args.target, when, args.text)}
        elif sub == "list":
            return await messages.list_scheduled(client, args.target)
        elif sub == "cancel":
            return {"success": True, **await messages.cancel_scheduled(
                client, args.target, args.ids)}
        raise TlgrmError(f"Unknown schedule subcommand: {sub!r}")
    elif cmd == "poll":
        return {"success": True, **await messages.send_poll(
            client, args.target, args.question, args.options,
            args.multiple, args.quiz, args.correct)}
    raise TlgrmError(f"Unknown command: {cmd!r}")
