"""Local (offline) STT backends. Each lazily imports its dependency and
returns None (logged) if the dependency or model is unavailable."""

import os
import logging

logger = logging.getLogger("tlgrm-stt")

_models = {}  # cache loaded model instances by (backend, model) key


def _decode_wav16k(path):
    """Decode any audio to 16 kHz mono WAV via ffmpeg; returns a temp path or None."""
    import shutil
    import subprocess
    import tempfile
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg not found; required for this STT backend.")
        return None
    fd, out = tempfile.mkstemp(suffix=".wav")
    os.close(fd)  # ffmpeg writes to the path, not the fd
    try:
        subprocess.run(["ffmpeg", "-y", "-i", path, "-ar", "16000", "-ac", "1", out],
                       check=True, capture_output=True)
        return out
    except Exception as e:
        logger.error(f"ffmpeg decode failed: {e}")
        return None


def faster_whisper_transcribe(path, model):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.debug("faster-whisper not installed (pip install 'tlgrm[stt]').")
        return None
    name = model or "tiny"
    # Default to CPU so it works without CUDA; opt into GPU via TG_STT_DEVICE=cuda.
    device = os.getenv("TG_STT_DEVICE", "cpu")
    compute = os.getenv("TG_STT_COMPUTE", "int8" if device == "cpu" else "default")
    key = ("faster-whisper", name, device, compute)
    if key not in _models:
        logger.info(f"Loading faster-whisper model '{name}' on {device} ({compute})...")
        _models[key] = WhisperModel(name, device=device, compute_type=compute)
    segments, _ = _models[key].transcribe(path)
    return " ".join(s.text for s in segments).strip()


def whisper_transcribe(path, model):
    try:
        import whisper
    except ImportError:
        logger.debug("openai-whisper not installed (pip install 'tlgrm[stt-whisper]').")
        return None
    name = model or "tiny"
    key = ("whisper", name)
    if key not in _models:
        logger.info(f"Loading whisper model '{name}'...")
        _models[key] = whisper.load_model(name)
    return _models[key].transcribe(path).get("text", "").strip()


def whispercpp_transcribe(path, model):
    try:
        from pywhispercpp.model import Model
    except ImportError:
        logger.debug("pywhispercpp not installed (pip install 'tlgrm[stt-whispercpp]').")
        return None
    name = model or "tiny"
    key = ("whispercpp", name)
    if key not in _models:
        logger.info(f"Loading whisper.cpp model '{name}'...")
        _models[key] = Model(name)
    segments = _models[key].transcribe(path)
    return " ".join(getattr(s, "text", "") for s in segments).strip()


def vosk_transcribe(path, model):
    try:
        from vosk import Model, KaldiRecognizer
    except ImportError:
        logger.debug("vosk not installed (pip install 'tlgrm[stt-vosk]').")
        return None
    import json
    import wave
    model_path = model or os.getenv("VOSK_MODEL_PATH")
    if not model_path or not os.path.isdir(model_path):
        logger.error("vosk needs a model directory; set TG_STT_MODEL or VOSK_MODEL_PATH "
                     "to a folder downloaded from https://alphacephei.com/vosk/models.")
        return None
    wav = _decode_wav16k(path)
    if not wav:
        return None
    try:
        with wave.open(wav, "rb") as wf:
            rec = KaldiRecognizer(Model(model_path), wf.getframerate())
            parts = []
            while True:
                data = wf.readframes(4000)
                if not data:
                    break
                if rec.AcceptWaveform(data):
                    parts.append(json.loads(rec.Result()).get("text", ""))
            parts.append(json.loads(rec.FinalResult()).get("text", ""))
        return " ".join(p for p in parts if p).strip()
    finally:
        try:
            os.remove(wav)
        except OSError:
            pass
