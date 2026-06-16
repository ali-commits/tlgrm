from tlgrm.server import tiers


def test_read_tier_blocks_write_and_destructive():
    assert tiers.is_allowed("read", "chats")
    assert not tiers.is_allowed("read", "send")
    assert not tiers.is_allowed("read", "delete")


def test_write_tier_allows_write_not_destructive():
    assert tiers.is_allowed("write", "send")
    assert not tiers.is_allowed("write", "delete")


def test_destructive_tier_allows_everything():
    for cmd in ("chats", "send", "delete", "leave", "remove-members"):
        assert tiers.is_allowed("destructive", cmd)


def test_unknown_command_defaults_to_destructive_requirement():
    assert not tiers.is_allowed("write", "totally-unknown")
    assert tiers.is_allowed("destructive", "totally-unknown")
