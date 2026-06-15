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
                "create-group", "add-members", "remove-members", "leave", "schedule", "poll",
                "transcribe",]:
        assert cmd in sub.choices


def test_send_requires_target():
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["send", "--text", "hi"])  # missing --target


def test_global_session_flag(monkeypatch):
    parser = build_parser()
    args = parser.parse_args(["--session", "/tmp/sessions/mcp", "chats"])
    assert args.session == "/tmp/sessions/mcp"
    assert args.command == "chats"


def test_session_flag_sets_env(monkeypatch):
    # main() should export the resolved session path before dispatching.
    monkeypatch.setenv("TG_API_ID", "1")
    monkeypatch.setenv("TG_API_HASH", "h")
    monkeypatch.delenv("TG_SESSION_PATH", raising=False)
    monkeypatch.setattr(sys, "argv", ["tlgrm", "--session", "~/mcp_sess", "chats"])
    monkeypatch.setattr(cli, "run_command", lambda args: None)
    monkeypatch.setattr(cli.asyncio, "run", lambda coro: coro)
    cli.main()
    import os
    assert os.environ["TG_SESSION_PATH"] == os.path.expanduser("~/mcp_sess")


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
