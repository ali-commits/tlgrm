# tlgrm workflow recipes

## Summarize unread chats
1. `tlgrm chats --limit 20` → pick entries with `unread_count > 0`.
2. For each, `tlgrm history --target <id> --limit <unread_count>`.
3. Summarize per chat; present a digest. (Read-only — no confirmation needed.)

## Find a specific message
1. `tlgrm search --query "<keywords>"` (global) or add `--target <chat>` to scope it.
2. Use the returned `chat_id` / `id` to fetch surrounding context with
   `tlgrm history --target <chat_id> --offset-id <id+1> --limit 5` if needed.

## Reply to the last message from someone
1. `tlgrm history --target <person> --limit 1` → note the message `id`.
2. Draft the reply and **show it to the user for confirmation**.
3. On approval: `tlgrm reply --target <person> --message-id <id> --text "<reply>"`.

## Send a file
1. Confirm the recipient and file path with the user.
2. `tlgrm send --target <T> --file <path> [--caption "..."]` (add `--voice` for a voice note).

## Notes
- Always preflight with `tlgrm whoami`.
- Confirm before any send/reply/edit/delete.
