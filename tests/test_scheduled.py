import asyncio
import datetime
from tlgrm.core import messages


class _Req:
    def __init__(self, result): self.result = result; self.called = None
    async def __call__(self, request): self.called = request; return self.result


def test_list_scheduled():
    m = type("Msg", (), {"id": 5, "message": "hi",
                         "date": datetime.datetime(2026, 6, 20, 9, 0)})()
    client = _Req(type("Res", (), {"messages": [m]})())
    out = asyncio.run(messages.list_scheduled(client, "@x"))
    assert out["count"] == 1
    assert out["scheduled"][0]["id"] == 5 and out["scheduled"][0]["text"] == "hi"
    assert type(client.called).__name__ == "GetScheduledHistoryRequest"


def test_cancel_scheduled():
    client = _Req(None)
    out = asyncio.run(messages.cancel_scheduled(client, "@x", ["5", 6]))
    assert out["cancelled"] == [5, 6]
    assert type(client.called).__name__ == "DeleteScheduledMessagesRequest"
