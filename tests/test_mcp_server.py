import pytest
from tlgrm.mcp.server import build_server

READ_TOOLS = {"whoami", "list_chats", "search_messages", "get_history",
              "get_members", "user_info", "chat_info", "download_media"}
WRITE_TOOLS = {"send_message", "edit_message", "mark_read", "react",
               "forward_messages", "pin", "unpin", "mute", "unmute",
               "create_group", "add_members", "schedule_message", "send_poll"}
DESTRUCTIVE_TOOLS = {"delete_messages", "leave_chat", "remove_members"}


async def _tool_names(mcp):
    return {t.name for t in await mcp.list_tools()}


async def test_readonly_excludes_write_and_destructive():
    names = await _tool_names(build_server())
    assert READ_TOOLS <= names
    assert not (WRITE_TOOLS & names) and not (DESTRUCTIVE_TOOLS & names)


async def test_allow_write_adds_write_not_destructive():
    names = await _tool_names(build_server(allow_write=True))
    assert WRITE_TOOLS <= names
    assert not (DESTRUCTIVE_TOOLS & names)


async def test_allow_destructive_adds_destructive():
    names = await _tool_names(build_server(allow_write=True, allow_destructive=True))
    assert READ_TOOLS <= names and WRITE_TOOLS <= names and DESTRUCTIVE_TOOLS <= names


def test_build_server_accepts_all_flag_combos():
    build_server()
    build_server(allow_write=True)
    build_server(allow_write=True, allow_destructive=True)
