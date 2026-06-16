import asyncio
from tlgrm.server import protocol as p


def test_request_and_response_builders():
    req = p.request(1, "chats", account="work", args={"limit": 5}, tier="read")
    assert req == {"id": 1, "cmd": "chats", "account": "work",
                   "args": {"limit": 5}, "tier": "read"}
    assert p.ok(1, {"x": 2}) == {"id": 1, "ok": True, "data": {"x": 2}}
    assert p.err(1, "Boom", "bad") == {
        "id": 1, "ok": False, "error": {"type": "Boom", "message": "bad"}}


def test_read_write_roundtrip_over_a_pipe():
    async def go():
        class _W:
            def __init__(self): self.buf = b""
            def write(self, b): self.buf += b
            async def drain(self): pass

        w = _W()
        await p.write_message(w, {"hello": "world"})
        reader = asyncio.StreamReader()
        reader.feed_data(w.buf)
        reader.feed_eof()
        assert await p.read_message(reader) == {"hello": "world"}
        assert await p.read_message(reader) is None  # EOF
    asyncio.run(go())
