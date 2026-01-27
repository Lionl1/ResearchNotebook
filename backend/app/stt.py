import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple

from faster_whisper import WhisperModel

from .config import STT_BEAM_SIZE, STT_COMPUTE_TYPE, STT_DEVICE, STT_MODEL, STT_PROVIDER


_MODEL: Optional[WhisperModel] = None


def _get_model() -> WhisperModel:
    global _MODEL
    if _MODEL is None:
        if not STT_MODEL:
            raise RuntimeError("STT_MODEL is not configured")
        _MODEL = WhisperModel(
            STT_MODEL,
            device=STT_DEVICE,
            compute_type=STT_COMPUTE_TYPE,
        )
    return _MODEL


def transcribe_audio(content: bytes, filename: str = "") -> Tuple[str, List[Dict[str, Any]]]:
    provider = (STT_PROVIDER or "").lower()
    if provider != "faster-whisper":
        raise RuntimeError(f"Unsupported STT provider: {provider}")

    suffix = os.path.splitext(filename)[1].lower() or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as handle:
        handle.write(content)
        handle.flush()
        model = _get_model()
        segments, _info = model.transcribe(
            handle.name,
            beam_size=STT_BEAM_SIZE,
        )
        segment_list: List[Dict[str, Any]] = []
        text_parts: List[str] = []
        for segment in segments:
            text_parts.append(segment.text or "")
            segment_list.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": (segment.text or "").strip(),
                }
            )
        text = "".join(text_parts).strip()
        if not text:
            raise RuntimeError("Empty transcription")
        return text, segment_list
