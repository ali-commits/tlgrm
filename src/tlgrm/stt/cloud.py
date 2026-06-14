"""Cloud STT backends. Each returns None (logged) if its API key is unset.
Audio is sent directly; only use these with consent — they transmit private
voice data to a third party (see the Telegram API ToS, AI/ML clause)."""

import os
import base64
import logging

import httpx

logger = logging.getLogger("tlgrm-stt")

_TIMEOUT = 120.0


def _require(env):
    key = os.getenv(env)
    if not key:
        logger.error(f"{env} is not set; cannot use this STT backend.")
    return key


def _multipart(path):
    # Read bytes eagerly so no file handle is left open if the request fails.
    with open(path, "rb") as f:
        data = f.read()
    return {"file": (os.path.basename(path), data, "application/octet-stream")}


def openai_transcribe(path, model):
    key = _require("OPENAI_API_KEY")
    if not key:
        return None
    r = httpx.post("https://api.openai.com/v1/audio/transcriptions",
                   headers={"Authorization": f"Bearer {key}"},
                   files=_multipart(path), data={"model": model or "whisper-1"},
                   timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json().get("text", "").strip()


def groq_transcribe(path, model):
    key = _require("GROQ_API_KEY")
    if not key:
        return None
    r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions",
                   headers={"Authorization": f"Bearer {key}"},
                   files=_multipart(path),
                   data={"model": model or "whisper-large-v3-turbo"},
                   timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json().get("text", "").strip()


def deepgram_transcribe(path, model):
    key = _require("DEEPGRAM_API_KEY")
    if not key:
        return None
    with open(path, "rb") as f:
        audio = f.read()
    r = httpx.post(f"https://api.deepgram.com/v1/listen?model={model or 'nova-3'}&smart_format=true",
                   headers={"Authorization": f"Token {key}", "Content-Type": "audio/ogg"},
                   content=audio, timeout=_TIMEOUT)
    r.raise_for_status()
    channels = r.json().get("results", {}).get("channels", [])
    if not channels or not channels[0].get("alternatives"):
        return None
    return channels[0]["alternatives"][0].get("transcript", "").strip()


def elevenlabs_transcribe(path, model):
    key = _require("ELEVENLABS_API_KEY")
    if not key:
        return None
    r = httpx.post("https://api.elevenlabs.io/v1/speech-to-text",
                   headers={"xi-api-key": key},
                   files=_multipart(path), data={"model_id": model or "scribe_v1"},
                   timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json().get("text", "").strip()


def google_transcribe(path, model):
    key = _require("GOOGLE_API_KEY")
    if not key:
        return None
    with open(path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    body = {"config": {"encoding": "OGG_OPUS", "sampleRateHertz": 48000,
                       "languageCode": os.getenv("TG_STT_LANGUAGE", "en-US")},
            "audio": {"content": content}}
    # Pass the key as a header, not a URL query param, so it can't leak via logs/proxies.
    r = httpx.post("https://speech.googleapis.com/v1/speech:recognize",
                   headers={"X-Goog-Api-Key": key}, json=body, timeout=_TIMEOUT)
    r.raise_for_status()
    results = r.json().get("results", [])
    if not results:
        return None
    return results[0]["alternatives"][0].get("transcript", "").strip()
