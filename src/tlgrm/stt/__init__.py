"""Pluggable speech-to-text. `transcribe_audio(path)` resolves the configured
backend and dispatches; returns None (logged) on any failure or missing
dependency, so transcription is always best-effort and optional."""

import logging

from .settings import resolve_backend, resolve_model
from . import local, cloud

logger = logging.getLogger("tlgrm-stt")

_LOCAL = {
    "faster-whisper": local.faster_whisper_transcribe,
    "whisper": local.whisper_transcribe,
    "whispercpp": local.whispercpp_transcribe,
    "vosk": local.vosk_transcribe,
}
_CLOUD = {
    "openai": cloud.openai_transcribe,
    "groq": cloud.groq_transcribe,
    "deepgram": cloud.deepgram_transcribe,
    "elevenlabs": cloud.elevenlabs_transcribe,
    "google": cloud.google_transcribe,
}


def transcribe_audio(file_path):
    """Transcribe an audio file using the configured backend; None on failure."""
    backend = resolve_backend()
    fn = _LOCAL.get(backend) or _CLOUD.get(backend)
    if fn is None:
        logger.warning(f"Unknown STT backend '{backend}'; skipping transcription.")
        return None
    try:
        text = fn(file_path, resolve_model())
        if text:
            logger.info(f"Transcribed via '{backend}': \"{text}\"")
        return text or None
    except Exception as e:
        logger.error(f"STT backend '{backend}' failed: {e}")
        return None
