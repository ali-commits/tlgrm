"""Entry point for the tlgrm MCP server (`tlgrm-mcp`)."""

import argparse
import os
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="tlgrm-mcp",
        description="tlgrm MCP server — exposes your Telegram account to MCP "
                    "clients over stdio (read-only by default).")
    parser.add_argument("--allow-write", action="store_true",
                        help="Expose write tools (send, react, ...).")
    parser.add_argument("--allow-destructive", action="store_true",
                        help="Expose destructive tools (delete, leave, remove-members).")
    parser.add_argument("--session", metavar="PATH",
                        help="Use a dedicated Telethon session for this server "
                             "(its own login). Give the daemon and the MCP server "
                             "separate sessions so they can run at the same time.")
    args = parser.parse_args()

    # Set the session path before importing the server (which reads config), so
    # the MCP server uses its own session and never fights the CLI/daemon for the
    # single-process Telethon SQLite session.
    if args.session:
        os.environ["TG_SESSION_PATH"] = os.path.expanduser(args.session)

    try:
        from .server import build_server
    except ImportError:
        sys.stderr.write(
            "The tlgrm MCP server requires extra dependencies. Install with:\n"
            "  pip install 'tlgrm[mcp]'\n")
        sys.exit(1)

    server = build_server(args.allow_write, args.allow_destructive)
    server.run()


if __name__ == "__main__":
    main()
