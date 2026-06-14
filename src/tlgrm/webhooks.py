import os
import sys
import json
import asyncio
import logging
import httpx
from datetime import datetime, timezone
from telethon import events
from .config import DOWNLOADS_DIR
from .core.client import get_client, ensure_authorized
from .core.errors import NotAuthorizedError
from .core import serialize
from .stt import transcribe_audio

# Set up logging for the webhook daemon
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("tlgrm-webhook")

async def forward_webhook(url, payload, headers=None, retries=3):
    """POST the payload to the webhook URL, retrying transient failures."""
    for attempt in range(1, retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            if 200 <= response.status_code < 300:
                logger.info(f"Webhook forwarded successfully! Status: {response.status_code}")
                return
            logger.error(f"Webhook forward failed with status code {response.status_code}: {response.text}")
        except Exception as e:
            logger.error(f"Failed to forward webhook to {url} (attempt {attempt}/{retries}): {e}")
        if attempt < retries:
            await asyncio.sleep(2 ** (attempt - 1))

async def run_listener(webhook_url=None, webhook_headers=None, verbose=False):
    if verbose:
        logger.setLevel(logging.DEBUG)
        
    client = get_client()
    try:
        await ensure_authorized(client)
    except NotAuthorizedError as e:
        logger.error(str(e))
        await client.disconnect()
        return
    
    # Parse custom headers
    parsed_headers = {}
    if webhook_headers:
        for header_str in webhook_headers:
            if ":" in header_str:
                k, v = header_str.split(":", 1)
                parsed_headers[k.strip()] = v.strip()
                logger.info(f"Configured custom webhook header -> {k.strip()}: [REDACTED]")
    
    me = await client.get_me()
    logger.info(f"Logged in as: {me.first_name} (@{me.username or 'No Username'}) [ID: {me.id}]")
    logger.info("Webhook daemon listening for new messages...")
    if webhook_url:
        logger.info(f"Webhooks will be emitted to: {webhook_url}")
    else:
        logger.info("No webhook URL provided. Messages will be printed as JSON to console.")

    # Keep strong references to in-flight forwarding tasks so the event loop
    # doesn't garbage-collect them before they finish.
    pending_tasks = set()

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        try:
            msg = event.message
            chat = await event.get_chat()
            sender = await event.get_sender()
            
            # Construct sender details
            sender_info = serialize.serialize_sender(sender)
            chat_type = ("user" if event.is_private else "group" if event.is_group
                         else "channel" if event.is_channel else "unknown")
            chat_info = serialize.serialize_chat(chat, chat_type)
            chat_info["id"] = event.chat_id  # prefer the event's chat_id

            # Media info & Download
            media_info = {"present": False, "type": None, "local_path": None,
                          "transcription": None, "self_destruct": False}
            if msg.media:
                media_info["present"] = True
                media_info["type"] = serialize.media_type(msg)

                if serialize.is_self_destruct(msg):
                    # Telegram API ToS §1.4: do not preserve self-destructing media.
                    media_info["self_destruct"] = True
                    logger.info(f"Skipping download of self-destructing media "
                                f"(message ID {msg.id}) to respect Telegram's ToS.")
                else:
                    try:
                        logger.info(f"Downloading incoming {media_info['type']} media from message ID {msg.id}...")
                        # Download media to the configured downloads directory
                        local_path = await msg.download_media(file=DOWNLOADS_DIR)
                        if local_path:
                            media_info["local_path"] = os.path.abspath(local_path)
                            logger.info(f"Downloaded media saved to: {media_info['local_path']}")

                            # Auto-transcribe if it's a voice note or audio file
                            if media_info["type"] in ["voice", "audio"]:
                                transcription = transcribe_audio(media_info["local_path"])
                                if transcription:
                                    media_info["transcription"] = transcription
                    except Exception as ex:
                        logger.error(f"Error downloading/transcribing media: {ex}")
            
            # Build full message payload
            payload = {
                "event": "new_message",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": {
                    "id": msg.id,
                    "text": msg.text or "",
                    "date": msg.date.isoformat() if msg.date else "",
                    "reply_to_msg_id": msg.reply_to_msg_id
                },
                "chat": chat_info,
                "sender": sender_info,
                "media": media_info
            }
            
            # Print to stdout/logger
            logger.info(f"New message received from {sender_info['display_name']} in {chat_info['name']}: {msg.text or '[Media]'}")
            if verbose or not webhook_url:
                print(json.dumps(payload, indent=2, ensure_ascii=False))

            # If webhook URL is set, emit webhook
            if webhook_url:
                # Forward using background asyncio task so we don't block the listener loop
                task = client.loop.create_task(forward_webhook(webhook_url, payload, parsed_headers))
                pending_tasks.add(task)
                task.add_done_callback(pending_tasks.discard)
                
        except Exception as e:
            logger.error(f"Error in message handler: {e}")

    # Run the client until disconnected
    await client.run_until_disconnected()
