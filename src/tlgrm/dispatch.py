"""Maps parsed CLI args to core operations and emits their JSON results."""

from .core.client import get_client, open_client
from .execute import execute
from .output import emit


async def _login(name=None):
    from . import accounts
    account = name or "default"
    client = get_client(account=account, must_exist=False)
    print(f"Connecting to Telegram to log in account '{account}'...")
    await client.start()
    me = await client.get_me()
    accounts.add_account(account)  # register on success
    print(f"\nLogged in account '{account}' as: {me.first_name} "
          f"(@{me.username or 'No Username'}) [ID: {me.id}]")
    await client.disconnect()


def run_account_command(args):
    """Handle `tlgrm account <list|use|rename|remove>` (sync, no Telegram I/O)."""
    from . import accounts
    cmd = args.account_command
    if cmd == "list":
        cfg = accounts.load_config()
        default = cfg.get("default_account")
        emit({"success": True, "default": default,
              "accounts": [{"name": n, "default": n == default}
                           for n in cfg["accounts"]]})
    elif cmd == "use":
        accounts.set_default(args.name)
        emit({"success": True, "default": args.name})
    elif cmd == "rename":
        accounts.rename_account(args.old, args.new)
        emit({"success": True, "renamed": [args.old, args.new]})
    elif cmd == "remove":
        accounts.remove_account(args.name)
        emit({"success": True, "removed": args.name})


async def run_command(args):
    """Run an authenticated command and emit its result."""
    account = getattr(args, "account", None)
    if args.command == "login":
        await _login(account)
        return
    if args.command == "account" and args.account_command == "add":
        await _login(args.name)
        return
    async with open_client(account) as client:
        emit(await execute(client, args, account=account))


def run_command_routed(args):
    """Dual-mode entry for authenticated commands: route through a running
    server, else run directly. login / account-add always go direct (they own
    interactive TTY and session creation)."""
    import asyncio
    from . import ipc
    from .output import emit

    direct_only = args.command in ("login",) or (
        args.command == "account" and getattr(args, "account_command", None) == "add")
    if direct_only or not ipc.is_server_running():
        asyncio.run(run_command(args))
        return

    payload = {k: v for k, v in vars(args).items()
               if k not in ("command", "account", "session")}
    resp = ipc.request_sync(args.command, account=getattr(args, "account", None),
                            args=payload, tier="destructive")
    if resp.get("ok"):
        emit(resp["data"])
    else:
        e = resp.get("error", {})
        emit({"success": False, "error": e.get("message", "server error")})
