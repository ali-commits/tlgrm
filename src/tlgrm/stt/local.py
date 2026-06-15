"""Local (offline) STT backends — the multilingual whisper family.
Each lazily imports its dependency and returns None (logged) if unavailable."""

import os
import logging

logger = logging.getLogger("tlgrm-stt")

_models = {}  # cache loaded model instances by key


def _language():
    """Optional forced language (TG_STT_LANGUAGE); None means auto-detect."""
    return os.getenv("TG_STT_LANGUAGE") or None


def _fw_device():
    """Resolve faster-whisper device: TG_STT_DEVICE override, else auto-detect a
    *usable* CUDA GPU via ctranslate2 (returns a GPU only if its runtime libs load),
    else cpu."""
    dev = os.getenv("TG_STT_DEVICE")
    if dev:
        return dev
    try:
        from ctranslate2 import get_cuda_device_count
        if get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def faster_whisper_transcribe(path, model):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.debug("faster-whisper not installed (pip install 'tlgrm[stt]').")
        return None
    name = model or "tiny"
    device = _fw_device()
    # Try the resolved device; if a GPU was chosen but is unusable (CUDA libs
    # missing — which surfaces at *load or inference* time), fall back to CPU.
    devices = [device, "cpu"] if device != "cpu" else ["cpu"]
    for dev in devices:
        compute = os.getenv("TG_STT_COMPUTE") or ("float16" if dev == "cuda" else "int8")
        key = ("faster-whisper", name, dev, compute)
        try:
            if key not in _models:
                logger.info(f"Loading faster-whisper model '{name}' on {dev} ({compute})...")
                _models[key] = WhisperModel(name, device=dev, compute_type=compute)
            segments, _ = _models[key].transcribe(path, language=_language())
            return " ".join(s.text for s in segments).strip()
        except Exception as e:
            _models.pop(key, None)  # don't keep a broken model cached
            if dev == "cpu":
                raise
            logger.warning(f"faster-whisper on {dev} failed ({e}); retrying on CPU.")


def whisper_transcribe(path, model):
    try:
        import whisper
    except ImportError:
        logger.debug("openai-whisper not installed (pip install 'tlgrm[stt-whisper]').")
        return None
    import shutil
    if not shutil.which("ffmpeg"):
        logger.error("ffmpeg not found — required for the 'whisper' backend "
                     "(the default faster-whisper backend does not need it).")
        return None
    name = model or "tiny"
    key = ("whisper", name)
    if key not in _models:
        logger.info(f"Loading whisper model '{name}'...")
        _models[key] = whisper.load_model(name)
    return _models[key].transcribe(path, language=_language()).get("text", "").strip()
