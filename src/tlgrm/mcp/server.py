"""tlgrm MCP server — exposes Telegram operations as MCP tools.

Read-only by default; --allow-write / --allow-destructive expand the tool set.
The server opens one persistent, authorized Telethon client for its lifetime.
"""

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from mcp.server.fastmcp import FastMCP, Context

from ..core.client import get_client, ensure_authorized
from ..core import messages, chats, users


@dataclass
class AppContext:
    client: object


def _client(ctx: Context):
    return ctx.request_context.lifespan_context.client


def build_server(allow_write: bool = False, allow_destructive: bool = False) -> FastMCP:
    """Build the FastMCP server, registering tools according to the permission tier."""

    @asynccontextmanager
    async def lifespan(server: FastMCP):
        client = get_client()
        await ensure_authorized(client)  # raises NotAuthorizedError if no session
        try:
            yield AppContext(client=client)
        finally:
            await client.disconnect()

    mcp = FastMCP("tlgrm", lifespan=lifespan)

    # ---- Read tools (always available) ----

    @mcp.tool()
    async def whoami(ctx: Context) -> dict:
        """Show the logged-in Telegram account."""
        return await users.whoami(_client(ctx))

    @mcp.tool()
    async def list_chats(ctx: Context, limit: int = 20) -> list:
        """List recent chats/dialogs with unread counts."""
        return await chats.list_chats(_client(ctx), limit)

    @mcp.tool()
    async def search_messages(ctx: Context, query: str,
                              target: Optional[str] = None, limit: int = 20) -> list:
        """Search messages globally, or within a chat if `target` is given."""
        return await messages.search(_client(ctx), query, target, limit)

    @mcp.tool()
    async def get_history(ctx: Context, target: str, limit: int = 10,
                          offset_id: int = 0) -> list:
        """Get recent messages from a chat (newest first)."""
        return await messages.get_history(_client(ctx), target, limit, offset_id)

    @mcp.tool()
    async def get_members(ctx: Context, target: str) -> list:
        """List participants of a group or channel."""
        return await users.get_members(_client(ctx), target)

    @mcp.tool()
    async def user_info(ctx: Context, target: str) -> dict:
        """Get info about a user (by @username, id, or phone)."""
        return await users.user_info(_client(ctx), target)

    @mcp.tool()
    async def chat_info(ctx: Context, target: str) -> dict:
        """Get info about a chat (type, name, participant count)."""
        return await chats.chat_info(_client(ctx), target)

    @mcp.tool()
    async def download_media(ctx: Context, target: str, message_id: int) -> dict:
        """Download media from a message into the server's downloads directory.

        The destination is server-controlled (not caller-specified) to prevent
        an agent from writing files to arbitrary paths.
        """
        return await messages.download(_client(ctx), target, message_id)

    # ---- Write tools (behind --allow-write) ----
    if allow_write:
        @mcp.tool()
        async def send_message(ctx: Context, target: str, text: str,
                               reply_to: Optional[int] = None,
                               silent: bool = False) -> dict:
            """Send a text message to a chat."""
            return await messages.send(_client(ctx), target, text=text,
                                       reply_to=reply_to, silent=silent)

        @mcp.tool()
        async def edit_message(ctx: Context, target: str, message_id: int,
                               text: str) -> dict:
            """Edit one of your messages."""
            return await messages.edit(_client(ctx), target, message_id, text)

        @mcp.tool()
        async def mark_read(ctx: Context, target: str,
                            max_id: Optional[int] = None) -> dict:
            """Mark a chat (or up to max_id) as read."""
            return await messages.mark_read(_client(ctx), target, max_id)

        @mcp.tool()
        async def react(ctx: Context, target: str, message_id: int,
                        emoji: str, big: bool = False) -> dict:
            """React to a message with an emoji (empty emoji clears it)."""
            return await messages.react(_client(ctx), target, message_id, emoji, big)

        @mcp.tool()
        async def forward_messages(ctx: Context, from_chat: str, to_chat: str,
                                   message_ids: list[int]) -> dict:
            """Forward messages from one chat to another."""
            return await messages.forward(_client(ctx), from_chat, to_chat, message_ids)

        @mcp.tool()
        async def pin(ctx: Context, target: str, message_id: int,
                      notify: bool = False) -> dict:
            """Pin a message in a chat."""
            return await chats.pin(_client(ctx), target, message_id, notify)

        @mcp.tool()
        async def unpin(ctx: Context, target: str,
                        message_id: Optional[int] = None) -> dict:
            """Unpin a message (or all pinned messages if message_id is omitted)."""
            return await chats.unpin(_client(ctx), target, message_id)

        @mcp.tool()
        async def mute(ctx: Context, target: str,
                       duration: Optional[int] = None) -> dict:
            """Mute a chat (duration seconds; omit for forever)."""
            return await chats.mute(_client(ctx), target, duration)

        @mcp.tool()
        async def unmute(ctx: Context, target: str) -> dict:
            """Unmute a chat."""
            return await chats.unmute(_client(ctx), target)

        @mcp.tool()
        async def create_group(ctx: Context, title: str,
                               members: Optional[list[str]] = None,
                               channel: bool = False) -> dict:
            """Create a group (or broadcast channel) and optionally add members."""
            return await chats.create_group(_client(ctx), title, members, channel)

        @mcp.tool()
        async def add_members(ctx: Context, target: str, members: list[str]) -> dict:
            """Add members to a group/channel."""
            return await users.add_members(_client(ctx), target, members)

        @mcp.tool()
        async def schedule_message(ctx: Context, target: str, text: str,
                                   when_seconds: int) -> dict:
            """Schedule a text message to send `when_seconds` from now."""
            import datetime
            return await messages.schedule_message(
                _client(ctx), target, datetime.timedelta(seconds=when_seconds), text)

        @mcp.tool()
        async def send_poll(ctx: Context, target: str, question: str,
                            options: list[str], multiple: bool = False) -> dict:
            """Send a poll to a chat."""
            return await messages.send_poll(_client(ctx), target, question,
                                            options, multiple)

    # ---- Destructive tools (behind --allow-destructive) ----
    if allow_destructive:
        @mcp.tool()
        async def delete_messages(ctx: Context, target: str,
                                  message_ids: list[int]) -> dict:
            """Delete messages from a chat (irreversible)."""
            return await messages.delete(_client(ctx), target, message_ids)

        @mcp.tool()
        async def leave_chat(ctx: Context, target: str) -> dict:
            """Leave a group or channel."""
            return await chats.leave(_client(ctx), target)

        @mcp.tool()
        async def remove_members(ctx: Context, target: str,
                                 members: list[str]) -> dict:
            """Remove (kick) members from a group/channel (irreversible)."""
            return await users.remove_members(_client(ctx), target, members)

    return mcp
