import types
import asyncio
import datetime
from tlgrm import execute as ex


def test_parse_duration():
    assert ex._parse_duration("90s") == datetime.timedelta(seconds=90)
    assert ex._parse_duration("30m") == datetime.timedelta(minutes=30)
    assert ex._parse_duration("2h") == datetime.timedelta(hours=2)
    assert ex._parse_duration("1d") == datetime.timedelta(days=1)


def test_execute_schedule_send_uses_in(monkeypatch):
    captured = {}

    class _Msgs:
        async def schedule_message(self, client, target, when, text=None):
            captured["when"] = when
            captured["text"] = text
            return {"message_id": 1}

    monkeypatch.setattr(ex, "messages", _Msgs())
    args = types.SimpleNamespace(
        command="schedule",
        schedule_command="send",
        target="@x",
        text="hi",
        at=None,
        in_="2h",
    )
    out = asyncio.run(ex.execute(object(), args))
    assert out["success"] and isinstance(captured["when"], datetime.timedelta)


def test_execute_schedule_list_and_cancel(monkeypatch):
    class _Msgs:
        async def list_scheduled(self, client, target):
            return {"count": 0, "scheduled": []}

        async def cancel_scheduled(self, client, target, ids):
            return {"cancelled": list(ids)}

    monkeypatch.setattr(ex, "messages", _Msgs())
    lst = asyncio.run(
        ex.execute(
            object(),
            types.SimpleNamespace(
                command="schedule", schedule_command="list", target="@x"
            ),
        )
    )
    assert lst["count"] == 0
    canc = asyncio.run(
        ex.execute(
            object(),
            types.SimpleNamespace(
                command="schedule", schedule_command="cancel", target="@x", ids=[5]
            ),
        )
    )
    assert canc["success"] and canc["cancelled"] == [5]
