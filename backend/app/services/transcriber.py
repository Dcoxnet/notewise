from __future__ import annotations

import json
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable


_model_lock = threading.Lock()
_model: Any | None = None


def _get_model(model_dir: Path) -> Any:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    from faster_whisper import WhisperModel
                except ImportError as exc:
                    raise RuntimeError(
                        "faster-whisper не установлен. Активируйте .venv и выполните "
                        "pip install -r backend/requirements.txt."
                    ) from exc
                _model = WhisperModel(
                    os.getenv("WHISPER_MODEL", "small.en"),
                    device=os.getenv("WHISPER_DEVICE", "cpu"),
                    compute_type=os.getenv("WHISPER_COMPUTE_TYPE", "int8"),
                    download_root=str(model_dir),
                )
    return _model


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, suffix=".tmp", delete=False
    ) as temp_file:
        json.dump(payload, temp_file, ensure_ascii=False, indent=2)
        temp_path = Path(temp_file.name)
    temp_path.replace(path)


def transcribe_media(
    media_path: Path,
    output_path: Path,
    audio_path: Path,
    model_dir: Path,
    progress: Callable[[int, str], None],
) -> dict[str, Any]:
    if not media_path.is_file():
        raise FileNotFoundError("Файл записи не найден.")

    ffmpeg = os.getenv("FFMPEG_PATH", "ffmpeg")
    progress(5, "Извлекаем аудио через FFmpeg")
    audio_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(media_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip().splitlines()
        raise RuntimeError(detail[-1] if detail else "FFmpeg не смог извлечь аудио.")

    progress(18, "Загружаем локальную модель распознавания")
    model = _get_model(model_dir)
    segments, info = model.transcribe(
        str(audio_path),
        language="en",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False,
    )

    transcript: dict[str, Any] = {
        "language": "en",
        "language_probability": 0.0,
        "duration_seconds": 0.0,
        "text": "",
        "segments": [],
        "complete": False,
    }
    total_duration = max(float(info.duration or 0), 1.0)
    transcript["language_probability"] = float(info.language_probability or 0)
    transcript["duration_seconds"] = float(info.duration or 0)
    progress(20, "Распознаём речь и сохраняем таймкоды")

    full_text: list[str] = []
    for segment in segments:
        entry = {
            "start": round(float(segment.start), 3),
            "end": round(float(segment.end), 3),
            "text": segment.text.strip(),
        }
        transcript["segments"].append(entry)
        full_text.append(entry["text"])
        transcript["text"] = " ".join(full_text)
        percent = min(98, 20 + int(float(segment.end) / total_duration * 78))
        progress(percent, "Распознаём речь и сохраняем таймкоды")
        if len(transcript["segments"]) % 10 == 0:
            _save_json(output_path, transcript)

    transcript["complete"] = True
    _save_json(output_path, transcript)
    return transcript
