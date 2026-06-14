"""Typed errors raised by the core layer. Core never prints or exits;
callers (CLI, MCP, webhooks) decide how to present these."""


class TlgrmError(Exception):
    """Base class for all tlgrm errors."""


class CredentialsError(TlgrmError):
    """TG_API_ID / TG_API_HASH missing or invalid."""


class NotAuthorizedError(TlgrmError):
    """No authorized session — the user must run `tlgrm login`."""


class TargetNotFoundError(TlgrmError):
    """Could not resolve the requested chat/user target."""


class MessageNotFoundError(TlgrmError):
    """No message with the requested ID was found."""
