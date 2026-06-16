from datetime import datetime, timezone
from types import SimpleNamespace
from tlgrm.core import serialize


def test_serialize_user_fills_blanks():
    u = SimpleNamespace(
        id=7, first_name="Al", last_name=None, username=None, phone=None, bot=False
    )
    out = serialize.serialize_user(u)
    assert out["id"] == 7 and out["last_name"] == "" and out["is_bot"] is False
    assert "display_name" in out


def test_serialize_chat_info_user_type():
    from telethon.tl.types import User

    u = User(id=1, first_name="A", access_hash=0)
    out = serialize.serialize_chat_info(u, None)
    assert out["type"] == "user" and out["participants_count"] is None


def test_serialize_search_message_includes_chat_id():
    msg = SimpleNamespace(
        id=3,
        chat_id=99,
        date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        sender_id=5,
        text="hi",
        media=None,
        photo=None,
        voice=None,
        video=None,
        audio=None,
        document=None,
    )
    out = serialize.serialize_search_message(msg, None)
    assert out["chat_id"] == 99 and out["id"] == 3 and out["media_type"] is None
