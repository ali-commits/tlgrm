"""tlgrm MCP server — a thin bridge that forwards tool calls to the running
tlgrm server (which owns the one Telegram connection and enforces tiers + the
write guard). Auto-spawns a server if none is running.

Read-only by default; --allow-write / --allow-destructive expand the tool set.
"""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, cast
from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP, Context


@dataclass
class AppContext:
    pass


def _tier(allow_write: bool, allow_destructive: bool) -> str:
    if allow_destructive:
        return "destructive"
    return "write" if allow_write else "read"


async def _ensure_server() -> None:
    """Make sure a tlgrm server is accepting connections, spawning one if not.

    Degrades gracefully: if the server is slow to bind (e.g. connecting many
    accounts), we don't raise — the first tool call connects once it's up, or
    surfaces a normal connection error if it never starts."""
    import sys
    from .. import ipc, serverctl

    if ipc.is_server_running():
        return
    serverctl._spawn_detached()
    for _ in range(50):
        await asyncio.sleep(0.2)
        if ipc.is_server_running():
            return
    sys.stderr.write(
        "tlgrm-mcp: tlgrm server not up after 10s; tool calls will "
        "connect once it finishes starting.\n"
    )


async def _call(cmd: str, account: str | None, tier: str, **args: Any) -> Any:
    """Forward one command to the tlgrm server; return its data or raise."""
    from .. import ipc

    resp = await ipc.request_async(cmd, account=account, args=args, tier=tier)
    if resp and resp.get("ok"):
        return resp["data"]
    msg = (resp or {}).get("error", {}).get("message", "tlgrm server error")
    raise RuntimeError(msg)


def build_server(
    allow_write: bool = False,
    allow_destructive: bool = False,
    account: str | None = None,
) -> FastMCP:
    """Build the FastMCP bridge, registering tools according to the permission tier."""
    tier = _tier(allow_write, allow_destructive)

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
        await _ensure_server()
        yield AppContext()

    mcp = FastMCP("tlgrm", lifespan=lifespan)

    @mcp.tool()
    async def whoami(ctx: Context[Any, Any, Any]) -> dict[str, Any]:
        """Show the logged-in Telegram account."""
        return cast(dict[str, Any], await _call("whoami", account, tier))

    @mcp.tool()
    async def list_chats(ctx: Context[Any, Any, Any], limit: int = 20) -> list[Any]:
        """List recent chats/dialogs with unread counts."""
        return cast(list[Any], await _call("chats", account, tier, limit=limit))

    @mcp.tool()
    async def search_messages(
        ctx: Context[Any, Any, Any],
        query: str,
        target: str | None = None,
        limit: int = 20,
    ) -> list[Any]:
        """Search messages globally, or within a chat if `target` is given."""
        return cast(
            list[Any],
            await _call(
                "search", account, tier, query=query, target=target, limit=limit
            ),
        )

    @mcp.tool()
    async def get_history(
        ctx: Context[Any, Any, Any], target: str, limit: int = 10, offset_id: int = 0
    ) -> list[Any]:
        """Get recent messages from a chat (newest first)."""
        return cast(
            list[Any],
            await _call(
                "history",
                account,
                tier,
                target=target,
                limit=limit,
                offset_id=offset_id,
            ),
        )

    @mcp.tool()
    async def get_members(ctx: Context[Any, Any, Any], target: str) -> list[Any]:
        """List participants of a group or channel."""
        return cast(list[Any], await _call("members", account, tier, target=target))

    @mcp.tool()
    async def user_info(ctx: Context[Any, Any, Any], target: str) -> dict[str, Any]:
        """Get info about a user (by @username, id, or phone)."""
        return cast(
            dict[str, Any], await _call("user-info", account, tier, target=target)
        )

    @mcp.tool()
    async def chat_info(ctx: Context[Any, Any, Any], target: str) -> dict[str, Any]:
        """Get info about a chat (type, name, participant count)."""
        return cast(
            dict[str, Any], await _call("chat-info", account, tier, target=target)
        )

    @mcp.tool()
    async def download_media(
        ctx: Context[Any, Any, Any], target: str, message_id: int
    ) -> dict[str, Any]:
        """Download media from a message into the server's downloads directory."""
        return cast(
            dict[str, Any],
            await _call(
                "download", account, tier, target=target, message_id=message_id
            ),
        )

    if allow_write:

        @mcp.tool()
        async def send_message(
            ctx: Context[Any, Any, Any],
            target: str,
            text: str,
            reply_to: int | None = None,
            silent: bool = False,
        ) -> dict[str, Any]:
            """Send a text message to a chat."""
            return cast(
                dict[str, Any],
                await _call(
                    "send",
                    account,
                    tier,
                    target=target,
                    text=text,
                    reply_to=reply_to,
                    silent=silent,
                ),
            )

        @mcp.tool()
        async def edit_message(
            ctx: Context[Any, Any, Any], target: str, message_id: int, text: str
        ) -> dict[str, Any]:
            """Edit one of your messages."""
            return cast(
                dict[str, Any],
                await _call(
                    "edit",
                    account,
                    tier,
                    target=target,
                    message_id=message_id,
                    text=text,
                ),
            )

        @mcp.tool()
        async def mark_read(
            ctx: Context[Any, Any, Any], target: str, max_id: int | None = None
        ) -> dict[str, Any]:
            """Mark a chat (or up to max_id) as read."""
            return cast(
                dict[str, Any],
                await _call("read", account, tier, target=target, max_id=max_id),
            )

        @mcp.tool()
        async def react(
            ctx: Context[Any, Any, Any],
            target: str,
            message_id: int,
            emoji: str,
            big: bool = False,
        ) -> dict[str, Any]:
            """React to a message with an emoji (empty emoji clears it)."""
            return cast(
                dict[str, Any],
                await _call(
                    "react",
                    account,
                    tier,
                    target=target,
                    message_id=message_id,
                    emoji=emoji,
                    big=big,
                ),
            )

        @mcp.tool()
        async def forward_messages(
            ctx: Context[Any, Any, Any],
            from_chat: str,
            to_chat: str,
            message_ids: list[int],
        ) -> dict[str, Any]:
            """Forward messages from one chat to another."""
            return cast(
                dict[str, Any],
                await _call(
                    "forward",
                    account,
                    tier,
                    from_chat=from_chat,
                    to_chat=to_chat,
                    message_ids=message_ids,
                ),
            )

        @mcp.tool()
        async def pin(
            ctx: Context[Any, Any, Any],
            target: str,
            message_id: int,
            notify: bool = False,
        ) -> dict[str, Any]:
            """Pin a message in a chat."""
            return cast(
                dict[str, Any],
                await _call(
                    "pin",
                    account,
                    tier,
                    target=target,
                    message_id=message_id,
                    notify=notify,
                ),
            )

        @mcp.tool()
        async def unpin(
            ctx: Context[Any, Any, Any], target: str, message_id: int | None = None
        ) -> dict[str, Any]:
            """Unpin a message (or all pinned messages if message_id is omitted)."""
            return cast(
                dict[str, Any],
                await _call(
                    "unpin", account, tier, target=target, message_id=message_id
                ),
            )

        @mcp.tool()
        async def mute(
            ctx: Context[Any, Any, Any], target: str, duration: int | None = None
        ) -> dict[str, Any]:
            """Mute a chat (duration seconds; omit for forever)."""
            return cast(
                dict[str, Any],
                await _call("mute", account, tier, target=target, duration=duration),
            )

        @mcp.tool()
        async def unmute(ctx: Context[Any, Any, Any], target: str) -> dict[str, Any]:
            """Unmute a chat."""
            return cast(
                dict[str, Any], await _call("unmute", account, tier, target=target)
            )

        @mcp.tool()
        async def create_group(
            ctx: Context[Any, Any, Any],
            title: str,
            members: list[str] | None = None,
            channel: bool = False,
        ) -> dict[str, Any]:
            """Create a group (or broadcast channel) and optionally add members."""
            return cast(
                dict[str, Any],
                await _call(
                    "create-group",
                    account,
                    tier,
                    title=title,
                    members=members or [],
                    channel=channel,
                ),
            )

        @mcp.tool()
        async def add_members(
            ctx: Context[Any, Any, Any], target: str, members: list[str]
        ) -> dict[str, Any]:
            """Add members to a group/channel."""
            return cast(
                dict[str, Any],
                await _call(
                    "add-members", account, tier, target=target, members=members
                ),
            )

        @mcp.tool()
        async def schedule_message(
            ctx: Context[Any, Any, Any], target: str, text: str, when_seconds: int
        ) -> dict[str, Any]:
            """Schedule a text message to send `when_seconds` from now."""
            return cast(
                dict[str, Any],
                await _call(
                    "schedule",
                    account,
                    tier,
                    schedule_command="send",
                    target=target,
                    text=text,
                    at=str(when_seconds),
                ),
            )

        @mcp.tool()
        async def send_poll(
            ctx: Context[Any, Any, Any],
            target: str,
            question: str,
            options: list[str],
            multiple: bool = False,
        ) -> dict[str, Any]:
            """Send a poll to a chat."""
            return cast(
                dict[str, Any],
                await _call(
                    "poll",
                    account,
                    tier,
                    target=target,
                    question=question,
                    options=options,
                    multiple=multiple,
                ),
            )

    if allow_destructive:

        @mcp.tool()
        async def delete_messages(
            ctx: Context[Any, Any, Any], target: str, message_ids: list[int]
        ) -> dict[str, Any]:
            """Delete messages from a chat (irreversible)."""
            return cast(
                dict[str, Any],
                await _call(
                    "delete", account, tier, target=target, message_ids=message_ids
                ),
            )

        @mcp.tool()
        async def leave_chat(
            ctx: Context[Any, Any, Any], target: str
        ) -> dict[str, Any]:
            """Leave a group or channel."""
            return cast(
                dict[str, Any], await _call("leave", account, tier, target=target)
            )

        @mcp.tool()
        async def remove_members(
            ctx: Context[Any, Any, Any], target: str, members: list[str]
        ) -> dict[str, Any]:
            """Remove (kick) members from a group/channel (irreversible)."""
            return cast(
                dict[str, Any],
                await _call(
                    "remove-members", account, tier, target=target, members=members
                ),
            )

    return mcp
