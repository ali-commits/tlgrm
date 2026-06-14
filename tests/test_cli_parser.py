# tests/test_cli_parser.py
import sys
import pytest
from tlgrm import cli
from tlgrm.cli import build_parser


def test_parser_has_all_commands():
    parser = build_parser()
    sub = next(a for a in parser._actions if a.dest == "command")
    for cmd in ["login", "chats", "send", "edit", "delete",
                "history", "members", "listen", "daemon",
                "search", "reply", "read", "download",
                "whoami", "user-info", "chat-info",
                "forward", "react", "pin", "unpin", "mute", "unmute", "saved",
                "create-group", "add-members", "remove-members", "leave", "schedule", "poll",]:
        assert cmd in sub.choices


def test_send_requires_target():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["send", "--text", "hi"])  # missing --target


def test_missing_credentials_exits_1_with_json(monkeypatch, capsys):
    # The behavior-preservation contract: credential failures exit 1 and
    # report the error as JSON.
    monkeypatch.delenv("TG_API_ID", raising=False)
    monkeypatch.delenv("TG_API_HASH", raising=False)
    monkeypatch.setattr(sys, "argv", ["tlgrm", "chats"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert '"success": false' in capsys.readouterr().out
