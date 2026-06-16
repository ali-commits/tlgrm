import types
import pytest
from tlgrm import write_guard, accounts


@pytest.fixture
def tmp_home(monkeypatch, tmp_path):
    monkeypatch.setenv("TG_CONFIG_PATH", str(tmp_path / "config.toml"))
    monkeypatch.setattr(accounts, "_accounts_dir", lambda: str(tmp_path / "acc"))
    accounts.add_account("work")
    return tmp_path


def test_write_target_extraction():
    assert write_guard.write_target("send", types.SimpleNamespace(target="@x")) == "@x"
    assert (
        write_guard.write_target("forward", types.SimpleNamespace(to_chat="@y")) == "@y"
    )
    assert write_guard.write_target("chats", types.SimpleNamespace()) is None
    assert write_guard.write_target("whoami", types.SimpleNamespace()) is None


def test_block_mode_blocks_listed(tmp_home):
    accounts.filter_add("work", "write", ["@boss"])
    with pytest.raises(PermissionError):
        write_guard.check_write("work", "send", types.SimpleNamespace(target="@boss"))
    write_guard.check_write("work", "send", types.SimpleNamespace(target="@other"))


def test_allow_mode_blocks_unlisted(tmp_home):
    accounts.filter_set_mode("work", "write", "allow")
    accounts.filter_add("work", "write", ["123"])
    write_guard.check_write("work", "send", types.SimpleNamespace(target="123"))
    with pytest.raises(PermissionError):
        write_guard.check_write("work", "send", types.SimpleNamespace(target="@nope"))


def test_no_target_and_unknown_account_are_noops(tmp_home):
    write_guard.check_write("work", "chats", types.SimpleNamespace())
    write_guard.check_write(None, "send", types.SimpleNamespace(target="@x"))


def test_matching_is_normalized(tmp_home):
    accounts.filter_add("work", "write", ["@Boss"])
    with pytest.raises(PermissionError):
        write_guard.check_write("work", "send", types.SimpleNamespace(target="boss"))
