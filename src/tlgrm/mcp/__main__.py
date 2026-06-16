"""Entry point for the tlgrm MCP server (`tlgrm-mcp`)."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="tlgrm-mcp",
        description="tlgrm MCP server — exposes your Telegram account to MCP "
        "clients over stdio (read-only by default).",
    )
    parser.add_argument(
        "--allow-write",
        action="store_true",
        help="Expose write tools (send, react, ...).",
    )
    parser.add_argument(
        "--allow-destructive",
        action="store_true",
        help="Expose destructive tools (delete, leave, remove-members).",
    )
    parser.add_argument(
        "--session",
        metavar="PATH",
        help="(Ignored — the bridge delegates to the tlgrm server.)",
    )
    parser.add_argument(
        "--account",
        help="Account the bridge acts as (default: the server's default account).",
    )
    args = parser.parse_args()

    try:
        from .server import build_server
    except ImportError:
        sys.stderr.write(
            "The tlgrm MCP server requires extra dependencies. Install with:\n"
            "  pip install 'tlgrm[mcp]'\n"
        )
        sys.exit(1)

    server = build_server(
        args.allow_write, args.allow_destructive, account=args.account
    )
    server.run()


if __name__ == "__main__":
    main()
