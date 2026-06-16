"""Permission tiers for control-socket commands. A connection is granted a tier
(read < write < destructive); the server rejects commands above it."""

_ORDER = {"read": 0, "write": 1, "destructive": 2}

COMMAND_TIERS = {
    # read
    "chats": "read", "history": "read", "search": "read", "whoami": "read",
    "user-info": "read", "chat-info": "read", "members": "read", "download": "read",
    "ping": "read", "reload": "read",
    # write
    "send": "write", "reply": "write", "edit": "write", "read": "write",
    "react": "write", "forward": "write", "pin": "write", "unpin": "write",
    "mute": "write", "unmute": "write", "saved": "write", "create-group": "write",
    "add-members": "write", "schedule": "write", "poll": "write",
    # destructive
    "delete": "destructive", "remove-members": "destructive", "leave": "destructive",
}


def is_allowed(conn_tier, cmd):
    """True if a connection granted `conn_tier` may run `cmd`. Unknown commands
    require the highest tier (fail safe)."""
    need = COMMAND_TIERS.get(cmd, "destructive")
    return _ORDER.get(conn_tier, -1) >= _ORDER[need]
