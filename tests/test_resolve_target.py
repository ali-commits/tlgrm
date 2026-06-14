# tests/test_resolve_target.py
from tlgrm.core.client import resolve_target


def test_numeric_string_becomes_int():
    assert resolve_target("738667936") == 738667936


def test_username_passes_through():
    assert resolve_target("@username") == "@username"


def test_none_passes_through():
    assert resolve_target(None) is None
