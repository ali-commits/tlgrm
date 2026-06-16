"""Pure command dispatch: map parsed args to a core operation against a
connected client and RETURN the result dict. Shared by the direct CLI path and
the server, so it never prints or connects — callers own I/O."""

import argparse
import datetime
from typing import Any

from telethon import TelegramClient

from .core import messages, chats, users
from .core.errors import TlgrmError


def _parse_when(value: str) -> datetime.datetime | datetime.timedelta:
    """Parse a schedule time: integer seconds-from-now, or ISO-8601 datetime."""
    if value.isdigit():
        return datetime.timedelta(seconds=int(value))
    try:
        return datetime.datetime.fromisoformat(value)
    except ValueError:
        raise TlgrmError(
            f"Invalid --at time: {value!r} (use an ISO-8601 datetime or seconds-from-now)."
        )


def _parse_duration(value: str) -> datetime.timedelta:
    """Parse a relative delay like '90s', '30m', '2h', '1d' into a timedelta."""
    units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    v = value.strip().lower()
    if v and v[-1] in units and v[:-1].isdigit():
        return datetime.timedelta(**{units[v[-1]]: int(v[:-1])})
    if v.isdigit():
        return datetime.timedelta(seconds=int(v))
    raise TlgrmError(f"Invalid duration: {value!r} (use 90s, 30m, 2h, 1d).")


async def execute(
    client: TelegramClient, args: argparse.Namespace, account: str | None = None
) -> dict[str, Any] | list[dict[str, Any]]:
    """Run one command against a connected client; return its result dict."""
    from .write_guard import check_write

    check_write(account, args.command, args)
    cmd = args.command
    match cmd:
        case "chats":
            return await chats.list_chats(client, args.limit)
        case "send":
            return {
                "success": True,
                **await messages.send(
                    client,
                    args.target,
                    text=args.text,
                    file_path=args.file,
                    caption=args.caption,
                    voice=args.voice,
                    reply_to=args.reply_to,
                    silent=args.silent,
                ),
            }
        case "reply":
            return {
                "success": True,
                **await messages.send(
                    client,
                    args.target,
                    text=args.text,
                    file_path=args.file,
                    caption=args.caption,
                    voice=args.voice,
                    reply_to=args.message_id,
                    silent=args.silent,
                ),
            }
        case "edit":
            return {
                "success": True,
                **await messages.edit(client, args.target, args.message_id, args.text),
            }
        case "delete":
            return {
                "success": True,
                **await messages.delete(client, args.target, args.message_ids),
            }
        case "history":
            return await messages.get_history(
                client, args.target, args.limit, args.offset_id
            )
        case "search":
            return await messages.search(client, args.query, args.target, args.limit)
        case "read":
            return {
                "success": True,
                **await messages.mark_read(client, args.target, args.max_id),
            }
        case "download":
            return {
                "success": True,
                **await messages.download(
                    client, args.target, args.message_id, args.output
                ),
            }
        case "whoami":
            return await users.whoami(client)
        case "user-info":
            return await users.user_info(client, args.target)
        case "chat-info":
            return await chats.chat_info(client, args.target)
        case "members":
            return await users.get_members(client, args.target)
        case "forward":
            return {
                "success": True,
                **await messages.forward(
                    client, args.from_chat, args.to_chat, args.message_ids
                ),
            }
        case "react":
            return {
                "success": True,
                **await messages.react(
                    client, args.target, args.message_id, args.emoji, args.big
                ),
            }
        case "pin":
            return {
                "success": True,
                **await chats.pin(client, args.target, args.message_id, args.notify),
            }
        case "unpin":
            return {
                "success": True,
                **await chats.unpin(client, args.target, args.message_id),
            }
        case "mute":
            return {
                "success": True,
                **await chats.mute(client, args.target, args.duration),
            }
        case "unmute":
            return {"success": True, **await chats.unmute(client, args.target)}
        case "saved":
            return {
                "success": True,
                **await messages.send(
                    client,
                    "me",
                    text=args.text,
                    file_path=args.file,
                    caption=args.caption,
                    voice=args.voice,
                ),
            }
        case "create-group":
            return {
                "success": True,
                **await chats.create_group(
                    client, args.title, args.members, args.channel
                ),
            }
        case "add-members":
            return {
                "success": True,
                **await users.add_members(client, args.target, args.members),
            }
        case "remove-members":
            return {
                "success": True,
                **await users.remove_members(client, args.target, args.members),
            }
        case "leave":
            return {"success": True, **await chats.leave(client, args.target)}
        case "schedule":
            sub = args.schedule_command
            match sub:
                case "send":
                    when = (
                        _parse_when(args.at) if args.at else _parse_duration(args.in_)
                    )
                    return {
                        "success": True,
                        **await messages.schedule_message(
                            client, args.target, when, args.text
                        ),
                    }
                case "list":
                    return await messages.list_scheduled(client, args.target)
                case "cancel":
                    return {
                        "success": True,
                        **await messages.cancel_scheduled(
                            client, args.target, args.ids
                        ),
                    }
                case _:
                    raise TlgrmError(f"Unknown schedule subcommand: {sub!r}")
        case "poll":
            return {
                "success": True,
                **await messages.send_poll(
                    client,
                    args.target,
                    args.question,
                    args.options,
                    args.multiple,
                    args.quiz,
                    args.correct,
                ),
            }
        case _:
            raise TlgrmError(f"Unknown command: {cmd!r}")
