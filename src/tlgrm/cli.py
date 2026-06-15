import sys
import asyncio

from .parser import build_parser
from .dispatch import run_command
from .output import emit
from .core.errors import TlgrmError, CredentialsError, NotAuthorizedError
from .webhooks import run_listener
from .daemon import daemon_install, daemon_uninstall, daemon_status, daemon_logs

__all__ = ["main", "build_parser", "emit"]


def _friendly_error(e):
    """Turn common Telethon errors into clear, user-facing messages."""
    try:
        from telethon import errors as tg
    except Exception:
        return str(e)
    if isinstance(e, tg.FloodWaitError):
        return f"Rate limited by Telegram; retry in {e.seconds}s."
    if isinstance(e, getattr(tg, "ApiIdInvalidError", ())):
        return "Invalid API credentials (api_id / api_hash)."
    if isinstance(e, (getattr(tg, "UsernameNotOccupiedError", ()),
                      getattr(tg, "UsernameInvalidError", ()),
                      getattr(tg, "PeerIdInvalidError", ()))):
        return "Could not resolve the target — check the @username, id, or phone."
    if isinstance(e, getattr(tg, "ChatAdminRequiredError", ())):
        return "This action requires admin rights in that chat."
    if isinstance(e, getattr(tg, "MessageIdInvalidError", ())):
        return "No message with that ID."
    if isinstance(e, getattr(tg, "ChatWriteForbiddenError", ())):
        return "You don't have permission to write in that chat."
    return str(e)


def main():
    parser = build_parser()
    args = parser.parse_args()

    # A --session flag points this process at its own Telethon session (resolved
    # at client-build time via config.session_path), so it never collides with a
    # running daemon/MCP server on the single-process SQLite session.
    if getattr(args, "session", None):
        import os
        os.environ["TG_SESSION_PATH"] = os.path.expanduser(args.session)

    try:
        if args.command in ("send", "reply", "saved") and not getattr(args, "text", None) and not getattr(args, "file", None):
            parser.error(f"At least one of --text or --file is required for {args.command}.")

        if args.command == "transcribe":
            import os
            from .stt import transcribe_audio
            from .stt.settings import resolve_backend
            if not os.path.exists(args.file):
                emit({"success": False, "error": f"File not found: {args.file}"})
                sys.exit(1)
            backend = args.backend or resolve_backend()
            text = transcribe_audio(args.file, backend=args.backend, model=args.model)
            emit({"success": text is not None, "backend": backend, "text": text})
        elif args.command == "listen":
            asyncio.run(run_listener(args.webhook_url, args.webhook_header,
                                     args.verbose, args.only, args.ignore))
        elif args.command == "daemon":
            if args.daemon_command == "install":
                daemon_install(args.webhook_url, args.webhook_header, args.verbose,
                               only=args.only, ignore=args.ignore)
            elif args.daemon_command == "uninstall":
                daemon_uninstall()
            elif args.daemon_command == "status":
                daemon_status()
            elif args.daemon_command == "logs":
                daemon_logs()
        else:
            asyncio.run(run_command(args))
    except KeyboardInterrupt:
        print("\nExiting...", file=sys.stderr)
        sys.exit(0)
    except (CredentialsError, NotAuthorizedError) as e:
        emit({"success": False, "error": str(e)})
        sys.exit(1)
    except TlgrmError as e:
        emit({"success": False, "error": str(e)})
    except Exception as e:  # operation-level failures (e.g. Telethon errors)
        emit({"success": False, "error": _friendly_error(e)})


if __name__ == "__main__":
    main()
