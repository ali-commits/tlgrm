import sys
import json
import asyncio

from .core.client import get_client, open_client
from .core.errors import TlgrmError, CredentialsError, NotAuthorizedError
from .core import messages, chats, users
from .webhooks import run_listener
from .daemon import daemon_install, daemon_uninstall, daemon_status, daemon_logs


def emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _parse_when(value):
    """Parse a schedule time: integer seconds-from-now, or ISO-8601 datetime."""
    import datetime
    if value.isdigit():
        return datetime.timedelta(seconds=int(value))
    return datetime.datetime.fromisoformat(value)


def build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="tlgrm",
        description="tlgrm - unofficial command-line client & webhook daemon for Telegram")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("login", help="Interactively log in to Telegram")

    p = sub.add_parser("chats", help="List recent chats/dialogs")
    p.add_argument("--limit", type=int, default=20, help="Max chats (default: 20)")

    p = sub.add_parser("send", help="Send a message or file/media")
    p.add_argument("--target", required=True, help="Username, chat ID, or phone number")
    p.add_argument("--text", help="Text message content")
    p.add_argument("--file", help="Path to a file/media to send")
    p.add_argument("--caption", help="Caption for the file (overrides --text)")
    p.add_argument("--voice", action="store_true", help="Send the file as a voice note")
    p.add_argument("--reply-to", type=int, help="Reply to this message ID")
    p.add_argument("--silent", action="store_true", help="Send without notification")

    p = sub.add_parser("edit", help="Edit an existing sent message")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument("--text", required=True)

    p = sub.add_parser("delete", help="Delete messages")
    p.add_argument("--target", required=True)
    p.add_argument("--message-ids", required=True, nargs="+")

    p = sub.add_parser("history", help="Retrieve message history")
    p.add_argument("--target", required=True)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--offset-id", type=int, default=0, help="Start before this message ID")

    p = sub.add_parser("members", help="Retrieve chat members/participants")
    p.add_argument("--target", required=True)

    p = sub.add_parser("search", help="Search messages (global, or within --target)")
    p.add_argument("--query", required=True)
    p.add_argument("--target", help="Limit search to this chat (omit for global)")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("reply", help="Reply to a specific message")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--caption")
    p.add_argument("--voice", action="store_true")
    p.add_argument("--silent", action="store_true", help="Send without notification")

    p = sub.add_parser("read", help="Mark a chat/messages as read")
    p.add_argument("--target", required=True)
    p.add_argument("--max-id", type=int, help="Mark up to this message ID")

    p = sub.add_parser("download", help="Download media from a message")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument("--output", help="Output file or directory")

    sub.add_parser("whoami", help="Show the logged-in account")

    p = sub.add_parser("user-info", help="Show info about a user")
    p.add_argument("--target", required=True)

    p = sub.add_parser("chat-info", help="Show info about a chat")
    p.add_argument("--target", required=True)

    p = sub.add_parser("forward", help="Forward messages between chats")
    p.add_argument("--from", dest="from_chat", required=True)
    p.add_argument("--to", dest="to_chat", required=True)
    p.add_argument("--message-ids", required=True, nargs="+")

    p = sub.add_parser("react", help="React to a message with an emoji")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument("--emoji", required=True, help="Emoji (empty string clears the reaction)")
    p.add_argument("--big", action="store_true")

    p = sub.add_parser("pin", help="Pin a message")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", required=True, type=int)
    p.add_argument("--notify", action="store_true")

    p = sub.add_parser("unpin", help="Unpin a message (or all if --message-id omitted)")
    p.add_argument("--target", required=True)
    p.add_argument("--message-id", type=int)

    p = sub.add_parser("mute", help="Mute a chat")
    p.add_argument("--target", required=True)
    p.add_argument("--duration", type=int, help="Seconds to mute (default: forever)")

    p = sub.add_parser("unmute", help="Unmute a chat")
    p.add_argument("--target", required=True)

    p = sub.add_parser("saved", help="Send to your Saved Messages")
    p.add_argument("--text")
    p.add_argument("--file")
    p.add_argument("--caption")
    p.add_argument("--voice", action="store_true")

    p = sub.add_parser("create-group", help="Create a group or channel")
    p.add_argument("--title", required=True)
    p.add_argument("--members", nargs="*", default=[])
    p.add_argument("--channel", action="store_true", help="Create a broadcast channel")

    p = sub.add_parser("add-members", help="Add members to a group/channel")
    p.add_argument("--target", required=True)
    p.add_argument("--members", required=True, nargs="+")

    p = sub.add_parser("remove-members", help="Remove members from a group/channel")
    p.add_argument("--target", required=True)
    p.add_argument("--members", required=True, nargs="+")

    p = sub.add_parser("leave", help="Leave a group/channel")
    p.add_argument("--target", required=True)

    p = sub.add_parser("schedule", help="Schedule a text message")
    p.add_argument("--target", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--at", required=True, help="Seconds from now, or ISO-8601 datetime")

    p = sub.add_parser("poll", help="Send a poll or quiz")
    p.add_argument("--target", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--option", action="append", required=True, dest="options")
    p.add_argument("--multiple", action="store_true")
    p.add_argument("--quiz", action="store_true")
    p.add_argument("--correct", type=int, help="Index of the correct answer (quiz)")

    p = sub.add_parser("listen", help="Run webhook listener for new messages")
    p.add_argument("--webhook-url")
    p.add_argument("--webhook-header", action="append")
    p.add_argument("--verbose", action="store_true")

    dp = sub.add_parser("daemon", help="Manage tlgrm systemd background daemon")
    dsub = dp.add_subparsers(dest="daemon_command", required=True)
    ip = dsub.add_parser("install", help="Install & start systemd user daemon")
    ip.add_argument("--webhook-url", required=True)
    ip.add_argument("--webhook-header", action="append")
    ip.add_argument("--verbose", action="store_true")
    dsub.add_parser("uninstall", help="Stop & remove systemd user daemon")
    dsub.add_parser("status", help="Show daemon systemd status")
    dsub.add_parser("logs", help="Show recent daemon logs")

    return parser


async def _login():
    client = get_client()
    print("Connecting to Telegram and starting interactive authorization...")
    await client.start()
    me = await client.get_me()
    print(f"\nSuccessfully logged in as: {me.first_name} "
          f"(@{me.username or 'No Username'}) [ID: {me.id}]")
    await client.disconnect()


async def _run_command(args):
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


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command in ("send", "reply", "saved") and not getattr(args, "text", None) and not getattr(args, "file", None):
            parser.error(f"At least one of --text or --file is required for {args.command}.")

        if args.command == "listen":
            asyncio.run(run_listener(args.webhook_url, args.webhook_header, args.verbose))
        elif args.command == "daemon":
            if args.daemon_command == "install":
                daemon_install(args.webhook_url, args.webhook_header, args.verbose)
            elif args.daemon_command == "uninstall":
                daemon_uninstall()
            elif args.daemon_command == "status":
                daemon_status()
            elif args.daemon_command == "logs":
                daemon_logs()
        else:
            asyncio.run(_run_command(args))
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)
    except (CredentialsError, NotAuthorizedError) as e:
        emit({"success": False, "error": str(e)})
        sys.exit(1)
    except TlgrmError as e:
        emit({"success": False, "error": str(e)})
    except Exception as e:  # operation-level failures (e.g. Telethon errors)
        emit({"success": False, "error": str(e)})


if __name__ == "__main__":
    main()
