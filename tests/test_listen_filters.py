"""Tests for the listener's chat/user whitelist (--only) and blacklist (--ignore)."""

import pytest

from tlgrm import webhooks, daemon


# --- token splitting -------------------------------------------------------

def test_split_tokens_handles_commas_and_repeats():
    assert webhooks._split_tokens(["@a,@b", " @c "]) == ["@a", "@b", "@c"]
    assert webhooks._split_tokens(None) == []
    assert webhooks._split_tokens(["", ","]) == []


# --- matching --------------------------------------------------------------

def test_matches_by_chat_id():
    assert webhooks._matches({123}, set(), chat_id=123, sender_id=999,
                             chat_username=None, sender_username=None)


def test_matches_by_sender_id():
    # e.g. ignoring a person whose message arrives inside a group chat
    assert webhooks._matches({555}, set(), chat_id=-100123, sender_id=555,
                             chat_username="group", sender_username="spammer")


def test_matches_by_username_case_insensitive():
    assert webhooks._matches(set(), {"workgroup"}, chat_id=-1, sender_id=-2,
                             chat_username="WorkGroup", sender_username=None)


def test_no_match_returns_false():
    assert not webhooks._matches({123}, {"foo"}, chat_id=1, sender_id=2,
                                 chat_username="bar", sender_username="baz")


# --- resolution (entity lookup mocked) ------------------------------------

class _FakeUser:
    def __init__(self, id, username=None):
        self.id = id
        self.username = username


@pytest.mark.asyncio
async def test_resolve_filters_uses_marked_peer_id(monkeypatch):
    monkeypatch.setattr(webhooks.utils, "get_peer_id", lambda e: e.id)

    class _Client:
        async def get_entity(self, token):
            return _FakeUser(42, username="Boss")

    ids, names = await webhooks._resolve_filters(_Client(), ["@boss"])
    assert ids == {42}
    assert names == {"boss"}


@pytest.mark.asyncio
async def test_resolve_filters_falls_back_on_unresolvable(monkeypatch):
    class _Client:
        async def get_entity(self, token):
            raise ValueError("no such entity")

    ids, names = await webhooks._resolve_filters(_Client(), ["-100999", "@ghost"])
    assert ids == {-100999}        # numeric token matched literally
    assert names == {"ghost"}      # @username matched literally


# --- daemon embedding / validation ----------------------------------------

def test_validate_filter_tokens_rejects_injection():
    with pytest.raises(ValueError):
        daemon.validate_filter_tokens(['@a"; rm -rf /'])
    with pytest.raises(ValueError):
        daemon.validate_filter_tokens(["bad token"])  # whitespace


def test_validate_filter_tokens_accepts_normal():
    daemon.validate_filter_tokens(["@user", "-1001234567890", "+15551234567", "a,b"])


def test_daemon_install_embeds_filters(monkeypatch):
    monkeypatch.setattr(daemon, "check_systemctl", lambda: True)
    monkeypatch.setattr(daemon, "_write_env_file", lambda: [])
    monkeypatch.setattr(daemon, "run_systemctl_cmd", lambda args: (True, "", ""))
    monkeypatch.setattr(daemon.shutil, "which", lambda x: "/usr/bin/tlgrm")
    monkeypatch.setattr(daemon.os, "chmod", lambda *a, **k: None)
    monkeypatch.setattr(daemon.os, "makedirs", lambda *a, **k: None)
    monkeypatch.setattr(daemon.os, "open", lambda *a, **k: 0)

    captured = {"text": ""}

    class _Sink:
        def write(self, s):
            captured["text"] += s

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(daemon.os, "fdopen", lambda *a, **k: _Sink())

    daemon.daemon_install("https://example.com/hook",
                          only=["@workgroup"], ignore=["@spammer", "12345"])

    unit = captured["text"]
    assert "--only @workgroup" in unit
    assert "--ignore @spammer" in unit
    assert "--ignore 12345" in unit
