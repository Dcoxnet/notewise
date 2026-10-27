from __future__ import annotations

import os
import logging
import json
import mimetypes
import sqlite3
import subprocess
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from obsws_python import ReqClient
from .services.transcriber import transcribe_media
from .services.summarizer import create_presentation_summary
from .services.slide_diagrams import write_slide_diagrams


logging.getLogger("obsws_python").setLevel(logging.WARNING)
app = FastAPI(title="NoteWise Local API", version="0.1.0")
DATA_DIR = Path(os.getenv("NOTES_DATA_DIR", "data")).expanduser().resolve()
DATABASE_PATH = DATA_DIR / "lessons.sqlite3"
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "NOTES_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def protect_obs_controls(request, call_next):
    if request.method == "POST" and request.url.path.startswith("/api/obs/"):
        if request.headers.get("origin") not in allowed_origins:
            return JSONResponse(status_code=403, content={"detail": "Источник запроса не разрешён."})
    return await call_next(request)


def obs_configured() -> bool:
    return bool(os.getenv("OBS_WEBSOCKET_PASSWORD"))


def obs_client() -> ReqClient:
    password = os.getenv("OBS_WEBSOCKET_PASSWORD")
    if not password:
        raise HTTPException(
            status_code=503,
            detail="Задайте OBS_WEBSOCKET_PASSWORD и включите сервер OBS WebSocket с паролем.",
        )
    try:
        return ReqClient(
            host=os.getenv("OBS_WEBSOCKET_HOST", "127.0.0.1"),
            port=int(os.getenv("OBS_WEBSOCKET_PORT", "4455")),
            password=password,
            timeout=3,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Не удалось подключиться к OBS: {exc}") from exc


def obs_recording_state(client: ReqClient) -> bool:
    try:
        return bool(client.get_record_status().output_active)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Не удалось получить состояние OBS: {exc}") from exc


@contextmanager
def database() -> Iterator[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """CREATE TABLE IF NOT EXISTS lessons (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_name TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL DEFAULT 0
        )"""
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(lessons)")}
    migrations = {
        "transcription_status": "TEXT NOT NULL DEFAULT 'not_started'",
        "transcription_progress": "INTEGER NOT NULL DEFAULT 0",
        "transcript_path": "TEXT",
        "transcription_error": "TEXT",
        "summary_status": "TEXT NOT NULL DEFAULT 'not_started'",
        "summary_progress": "INTEGER NOT NULL DEFAULT 0",
        "summary_path": "TEXT",
        "summary_pdf_path": "TEXT",
        "summary_error": "TEXT",
    }
    for column, definition in migrations.items():
        if column not in columns:
            connection.execute(f"ALTER TABLE lessons ADD COLUMN {column} {definition}")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def save_lesson(file_path: str, duration_ms: int | None) -> dict[str, Any]:
    path = Path(file_path).expanduser().resolve()
    lesson = {
        "id": str(uuid.uuid4()),
        "title": path.stem,
        "file_path": str(path),
        "file_name": path.name,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": max(0, int((duration_ms or 0) / 1000)),
        "transcription_status": "not_started",
        "transcription_progress": 0,
        "transcription_error": None,
    }
    with database() as connection:
        connection.execute(
            "INSERT INTO lessons (id, title, file_path, file_name, recorded_at, duration_seconds, "
            "transcription_status, transcription_progress, transcription_error) "
            "VALUES (:id, :title, :file_path, :file_name, :recorded_at, :duration_seconds, "
            ":transcription_status, :transcription_progress, :transcription_error)",
            lesson,
        )
    return {key: value for key, value in lesson.items() if key != "file_path"}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "notewise-local", "obs_configured": obs_configured()}


@app.get("/api/lessons")
def list_lessons() -> list[dict[str, Any]]:
    with database() as connection:
        rows = connection.execute(
            "SELECT id, title, file_name, recorded_at, duration_seconds, "
            "transcription_status, transcription_progress, transcription_error, "
            "summary_status, summary_progress, summary_error "
            "FROM lessons ORDER BY recorded_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def run_summary(lesson_id: str) -> None:
    with database() as connection:
        row = connection.execute(
            "SELECT title, transcript_path FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
        if row is None:
            return
        if not row["transcript_path"]:
            connection.execute(
                "UPDATE lessons SET summary_status = 'failed', summary_error = ? WHERE id = ?",
                ("Сначала нужно завершить транскрибацию.", lesson_id),
            )
            return
        transcript_path = Path(row["transcript_path"])
        title = row["title"]
        output_dir = DATA_DIR / "summaries" / lesson_id
        summary_path = output_dir / "presentation.json"
        pdf_path = output_dir / "presentation.pdf"
        connection.execute(
            "UPDATE lessons SET summary_status = 'processing', summary_progress = 1, "
            "summary_error = NULL, summary_path = ?, summary_pdf_path = ? WHERE id = ?",
            (str(summary_path), str(pdf_path), lesson_id),
        )

    try:
        transcript = json.loads(transcript_path.read_text(encoding="utf-8"))

        def update_progress(percent: int, _message: str) -> None:
            with database() as connection:
                connection.execute(
                    "UPDATE lessons SET summary_progress = ? WHERE id = ?",
                    (max(0, min(94, percent)), lesson_id),
                )

        summary = create_presentation_summary(title, transcript.get("segments", []), update_progress)
        output_dir.mkdir(parents=True, exist_ok=True)
        write_slide_diagrams(summary, output_dir)
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        template_path = Path(__file__).parent / "templates" / "lesson_presentation.typ"
        typst_path = output_dir / "presentation.typ"
        typst_path.write_text(template_path.read_text(encoding="utf-8"), encoding="utf-8")
        update_progress(96, "Создаём PDF-презентацию")
        result = subprocess.run(
            [os.getenv("TYPST_PATH", "typst"), "compile", str(typst_path), str(pdf_path)],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0:
            detail = result.stderr.strip().splitlines()
            raise RuntimeError(detail[-1] if detail else "Typst не смог собрать PDF.")
        with database() as connection:
            connection.execute(
                "UPDATE lessons SET summary_status = 'completed', summary_progress = 100, "
                "summary_error = NULL WHERE id = ?",
                (lesson_id,),
            )
    except Exception as exc:
        logging.exception("Presentation generation failed for lesson %s", lesson_id)
        with database() as connection:
            connection.execute(
                "UPDATE lessons SET summary_status = 'failed', summary_error = ? WHERE id = ?",
                (str(exc)[:500], lesson_id),
            )


@app.post("/api/lessons/{lesson_id}/summarize", status_code=202)
def start_summary(lesson_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    with database() as connection:
        row = connection.execute(
            "SELECT transcription_status, summary_status FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Урок не найден.")
        if row["transcription_status"] != "completed":
            raise HTTPException(status_code=409, detail="Сначала завершите транскрибацию урока.")
        if row["summary_status"] == "processing":
            return {"status": "processing", "message": "Конспект уже создаётся."}
        connection.execute(
            "UPDATE lessons SET summary_status = 'queued', summary_progress = 0, summary_error = NULL "
            "WHERE id = ?", (lesson_id,)
        )
    background_tasks.add_task(run_summary, lesson_id)
    return {"status": "queued", "message": "Создание конспекта и PDF поставлено в очередь."}


@app.get("/api/lessons/{lesson_id}/summary")
def get_summary(lesson_id: str) -> dict[str, Any]:
    with database() as connection:
        row = connection.execute(
            "SELECT summary_path, summary_status FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Урок не найден.")
    path = Path(row["summary_path"]) if row["summary_path"] else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Конспект ещё не готов.")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/lessons/{lesson_id}/summary/pdf")
def summary_pdf(lesson_id: str) -> FileResponse:
    with database() as connection:
        row = connection.execute(
            "SELECT title, summary_pdf_path FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Урок не найден.")
    path = Path(row["summary_pdf_path"]) if row["summary_pdf_path"] else None
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="PDF ещё не создан.")
    return FileResponse(path, filename=f"{row['title']}-конспект.pdf", media_type="application/pdf")


def run_transcription(lesson_id: str) -> None:
    with database() as connection:
        row = connection.execute(
            "SELECT file_path, transcript_path FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
        if row is None:
            return
        media_path = Path(row["file_path"])
        transcript_path = Path(row["transcript_path"] or DATA_DIR / "transcripts" / f"{lesson_id}.json")
        audio_path = DATA_DIR / "audio" / f"{lesson_id}.wav"
        connection.execute(
            "UPDATE lessons SET transcription_status = 'processing', transcription_progress = 1, "
            "transcription_error = NULL, transcript_path = ? WHERE id = ?",
            (str(transcript_path), lesson_id),
        )

    def update_progress(percent: int, _message: str) -> None:
        with database() as connection:
            connection.execute(
                "UPDATE lessons SET transcription_progress = ? WHERE id = ?",
                (max(0, min(99, percent)), lesson_id),
            )

    try:
        transcribe_media(media_path, transcript_path, audio_path, DATA_DIR / "models", update_progress)
        with database() as connection:
            connection.execute(
                "UPDATE lessons SET transcription_status = 'completed', transcription_progress = 100, "
                "transcription_error = NULL WHERE id = ?",
                (lesson_id,),
            )
    except Exception as exc:
        logging.exception("Transcription failed for lesson %s", lesson_id)
        with database() as connection:
            connection.execute(
                "UPDATE lessons SET transcription_status = 'failed', transcription_error = ? WHERE id = ?",
                (str(exc)[:500], lesson_id),
            )


@app.post("/api/lessons/import")
async def import_lesson(file: UploadFile = File(...)) -> dict[str, Any]:
    allowed_extensions = {".mp4", ".mkv", ".mov", ".m4v", ".webm", ".mp3", ".m4a", ".wav", ".ogg"}
    original_name = Path(file.filename or "recording").name
    suffix = Path(original_name).suffix.lower()
    if suffix not in allowed_extensions:
        raise HTTPException(status_code=415, detail="Поддерживаются MP4, MKV, MOV, WebM и аудиофайлы.")
    recordings_dir = DATA_DIR / "recordings"
    recordings_dir.mkdir(parents=True, exist_ok=True)
    target = recordings_dir / f"{uuid.uuid4()}{suffix}"
    size = 0
    try:
        with target.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 20 * 1024 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Файл превышает лимит 20 ГБ.")
                output.write(chunk)
        lesson = save_lesson(str(target), None)
        return lesson
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.post("/api/lessons/{lesson_id}/transcribe", status_code=202)
def start_transcription(lesson_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    with database() as connection:
        row = connection.execute(
            "SELECT transcription_status FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Урок не найден.")
        if row["transcription_status"] == "processing":
            return {"status": "processing", "message": "Транскрибация уже выполняется."}
        connection.execute(
            "UPDATE lessons SET transcription_status = 'queued', transcription_progress = 0, "
            "transcription_error = NULL WHERE id = ?", (lesson_id,)
        )
    background_tasks.add_task(run_transcription, lesson_id)
    return {"status": "queued", "message": "Транскрибация поставлена в очередь."}


@app.get("/api/lessons/{lesson_id}/transcript")
def get_transcript(lesson_id: str) -> dict[str, Any]:
    with database() as connection:
        row = connection.execute(
            "SELECT transcript_path, transcription_status FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Урок не найден.")
    path = Path(row["transcript_path"]) if row["transcript_path"] else DATA_DIR / "transcripts" / f"{lesson_id}.json"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Транскрипт ещё не готов.")
    import json
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/api/lessons/{lesson_id}/file")
def lesson_file(lesson_id: str) -> FileResponse:
    with database() as connection:
        row = connection.execute(
            "SELECT file_path, file_name FROM lessons WHERE id = ?", (lesson_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Запись не найдена.")
    path = Path(row["file_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Файл записи не найден на диске.")
    return FileResponse(
        path,
        filename=row["file_name"],
        media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
    )


@app.get("/api/obs/status")
def obs_status() -> dict[str, Any]:
    client = obs_client()
    try:
        version = client.get_version()
        record_status = client.get_record_status()
        recording = bool(record_status.output_active)
        return {
            "connected": True,
            "recording": recording,
            "duration_ms": getattr(record_status, "output_duration", 0),
            "obs_version": version.obs_version,
            "websocket_version": version.obs_web_socket_version,
        }
    finally:
        client.disconnect()


@app.post("/api/obs/start")
def start_recording() -> dict[str, Any]:
    client = obs_client()
    try:
        if obs_recording_state(client):
            return {"recording": True, "message": "Запись уже идёт."}
        client.start_record()
        return {"recording": True, "message": "Запись запущена."}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"OBS не удалось начать запись: {exc}") from exc
    finally:
        client.disconnect()


@app.post("/api/obs/stop")
def stop_recording(background_tasks: BackgroundTasks) -> dict[str, Any]:
    client = obs_client()
    try:
        record_status = client.get_record_status()
        if not record_status.output_active:
            return {"recording": False, "message": "Запись уже остановлена."}
        response = client.stop_record()
        output_path = getattr(response, "output_path", None)
        try:
            saved_lesson = save_lesson(output_path, getattr(record_status, "output_duration", 0)) if output_path else None
        except Exception as exc:
            return {
                "recording": False,
                "lesson": None,
                "message": f"Запись остановлена, но сохранить её в библиотеку не удалось: {exc}",
            }
        if saved_lesson:
            with database() as connection:
                connection.execute(
                    "UPDATE lessons SET transcription_status = 'queued' WHERE id = ?",
                    (saved_lesson["id"],),
                )
            background_tasks.add_task(run_transcription, saved_lesson["id"])
            saved_lesson["transcription_status"] = "queued"
        return {
            "recording": False,
            "lesson": saved_lesson,
            "message": "Запись добавлена в библиотеку, транскрибация запущена." if saved_lesson else "Запись остановлена, но OBS не вернул путь к файлу.",
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"OBS не удалось остановить запись: {exc}") from exc
    finally:
        client.disconnect()
