"""Pluggable speech-to-text. `transcribe_audio(path)` resolves the configured
backend and dispatches; returns None (logged) on any failure or missing
dependency, so transcription is always best-effort and optional."""

import logging

from .settings import resolve_backend, resolve_model
from . import local, cloud

logger = logging.getLogger("tlgrm-stt")

# Local backends are the multilingual whisper family (handle Arabic, English, etc.).
_LOCAL = {
    "faster-whisper": local.faster_whisper_transcribe,
    "whisper": local.whisper_transcribe,
}
_CLOUD = {
    "openai": cloud.openai_transcribe,
    "groq": cloud.groq_transcribe,
    "deepgram": cloud.deepgram_transcribe,
    "elevenlabs": cloud.elevenlabs_transcribe,
    "google": cloud.google_transcribe,
}


def transcribe_audio(file_path, backend=None, model=None):
    """Transcribe an audio file; None on failure.

    `backend`/`model` override the configured selection (useful for the
    `transcribe` command and A/B testing); otherwise the env/config defaults apply.
    """
    backend = backend or resolve_backend()
    fn = _LOCAL.get(backend) or _CLOUD.get(backend)
    if fn is None:
        logger.warning(f"Unknown STT backend '{backend}'; skipping transcription.")
        return None
    try:
        text = fn(file_path, model or resolve_model())
        if text:
            logger.info(f"Transcribed via '{backend}': \"{text}\"")
        return text or None
    except Exception as e:
        logger.error(f"STT backend '{backend}' failed: {e}")
        return None


def reset_models():
    """Drop cached STT models so the next transcription reloads with current
    settings (frees memory after a backend/model/device change)."""
    local._models.clear()


def preload():
    """Warm the configured local STT model (e.g. at daemon startup) so the first
    real voice note isn't delayed by a model load. Best-effort; no-op for cloud
    backends or when no local STT dependency is installed."""
    import os
    import tempfile
    import wave

    backend = resolve_backend()
    if backend not in _LOCAL:
        return  # cloud backends have no local model to warm
    fd, p = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    try:
        with wave.open(p, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x00" * 16000)  # 1s of silence
        transcribe_audio(p, backend=backend)
        logger.info(f"STT backend '{backend}' pre-warmed.")
    except Exception as e:
        logger.warning(f"STT preload skipped ({e}); the model will load on first use.")
    finally:
        try:
            os.remove(p)
        except OSError:
            pass
