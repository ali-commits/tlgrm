"""Outgoing-message permission guard. Before a write op runs, check its target
against the account's `write` filter and raise PermissionError if blocked. The
target is matched as written (normalized @name/id) — no network resolution."""

import argparse

from . import accounts

# Commands that send/post to a target, and which arg holds that target.
_WRITE_TARGET = {
    "send": "target",
    "reply": "target",
    "edit": "target",
    "react": "target",
    "pin": "target",
    "poll": "target",
    "forward": "to_chat",
}


def write_target(cmd: str, args: argparse.Namespace) -> str | None:
    """The target a write command acts on, or None if the command isn't a
    guarded write (e.g. reads, or `saved` which always goes to yourself)."""
    if cmd == "schedule":
        target: str | None = (
            getattr(args, "target", None)
            if getattr(args, "schedule_command", None) == "send"
            else None
        )
        return target
    field = _WRITE_TARGET.get(cmd)
    result: str | None = getattr(args, field, None) if field else None
    return result


def _norm(token: str) -> str:
    return str(token).lstrip("@").lower()


def check_write(account: str | None, cmd: str, args: argparse.Namespace) -> None:
    """Raise PermissionError if the account's write filter blocks this target."""
    target = write_target(cmd, args)
    if target is None:
        return
    try:
        name = accounts.resolve_account(account)
    except Exception:
        return  # no account context → nothing to scope a guard to
    flt = accounts.filter_config(name, "write")
    matched = _norm(target) in {_norm(t) for t in flt["list"]}
    blocked = matched if flt["mode"] == "block" else not matched
    if blocked:
        raise PermissionError(
            f"Writing to {target!r} is blocked by account '{name}'s write filter "
            f"(mode={flt['mode']})."
        )
