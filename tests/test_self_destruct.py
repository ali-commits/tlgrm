from types import SimpleNamespace
from tlgrm.core import serialize


def test_no_media_is_not_self_destruct():
    assert serialize.is_self_destruct(SimpleNamespace(media=None)) is False


def test_media_without_ttl_is_not_self_destruct():
    msg = SimpleNamespace(media=SimpleNamespace(ttl_seconds=None))
    assert serialize.is_self_destruct(msg) is False


def test_media_with_ttl_is_self_destruct():
    msg = SimpleNamespace(media=SimpleNamespace(ttl_seconds=5))
    assert serialize.is_self_destruct(msg) is True
