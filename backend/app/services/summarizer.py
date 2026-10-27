from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Callable


def _generate(prompt: str, system: str) -> dict[str, Any]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    payload = json.dumps(
        {
            "model": os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            "system": system,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 8192},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url}/api/generate", data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Ollama вернул ошибку для модели: {detail or exc.code}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Не удалось подключиться к Ollama. Установите и запустите Ollama, затем загрузите модель."
        ) from exc
    except TimeoutError as exc:
        raise RuntimeError("Ollama не ответил за 15 минут. Проверьте модель и нагрузку на компьютер.") from exc
    text = result.get("response", "").strip()
    if not text:
        raise RuntimeError("Ollama вернул пустой ответ.")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama вернул некорректный JSON. Повторите создание конспекта.") from exc
    return parsed


def _chunks(segments: list[dict[str, Any]], max_chars: int = 10_000) -> list[list[dict[str, Any]]]:
    result: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    current_chars = 0
    for segment in segments:
        line = f"[{float(segment['start']):.0f}s] {segment['text']}"
        if current and current_chars + len(line) > max_chars:
            result.append(current)
            current = []
            current_chars = 0
        current.append(segment)
        current_chars += len(line)
    if current:
        result.append(current)
    return result


def create_presentation_summary(
    title: str,
    segments: list[dict[str, Any]],
    progress: Callable[[int, str], None],
) -> dict[str, Any]:
    if not segments:
        raise RuntimeError("В транскрипте нет распознанной речи.")
    chunks = _chunks(segments)
    chunk_summaries: list[dict[str, Any]] = []
    system = (
        "Ты создаёшь точные учебные материалы по транскрипции занятия. "
        "Не добавляй факты, которых нет в источнике. Если фрагмент неразборчив или не по теме, "
        "не выдумывай смысл. Пиши по-русски, сохраняя английские термины там, где они важны."
    )
    for index, chunk in enumerate(chunks):
        source = "\n".join(
            f"[{float(segment['start']):.1f}–{float(segment['end']):.1f} сек] {segment['text']}"
            for segment in chunk
        )
        progress(5 + int(index / max(len(chunks), 1) * 60), f"Анализируем фрагмент {index + 1} из {len(chunks)}")
        chunk_summaries.append(
            _generate(
                f"Занятие: {title}\nФрагмент {index + 1}/{len(chunks)}.\n\n"
                "Верни компактный JSON: summary (1 предложение), key_points (до 4 конкретных пунктов), "
                "examples (до 1 короткого примера), terms (до 3 объектов с term и translation), "
                "action_items (только явно заданные домашние или практические задания; иначе пустой список), "
                "timeline (до 3 объектов timestamp и point). "
                "Не включай общие фразы и не добавляй выводов, которых нет в источнике.\n\n"
                f"{source}",
                system,
            )
        )

    duration = float(segments[-1].get("end", 0)) if segments else 0
    if duration < 20 * 60:
        min_slides, max_slides = 5, 7
    elif duration < 40 * 60:
        min_slides, max_slides = 7, 9
    elif duration < 70 * 60:
        min_slides, max_slides = 9, 11
    else:
        min_slides, max_slides = 11, 13

    compact_notes = []
    for note in chunk_summaries:
        timeline = note.get("timeline", []) if isinstance(note.get("timeline"), list) else []
        key_points = note.get("key_points", []) if isinstance(note.get("key_points"), list) else []
        examples = note.get("examples", []) if isinstance(note.get("examples"), list) else []
        compact_notes.append(
            {
                "summary": str(note.get("summary") or "")[:280],
                "key_points": [str(point)[:150] for point in key_points[:4]],
                "examples": [str(example)[:150] for example in examples[:1]],
                "timeline": [
                    {
                        "timestamp": str(point.get("timestamp") or "")[:20],
                        "point": str(point.get("point") or "")[:110],
                    }
                    for point in timeline[:3] if isinstance(point, dict)
                ],
            }
        )
    timeline_anchors = [
        {
            "start": f"{float(chunk[0]['start']):.1f}",
            "end": f"{float(chunk[-1].get('end', chunk[-1]['start'])):.1f}",
            "summary": note.get("summary", ""),
        }
        for chunk, note in zip(chunks, compact_notes)
    ]
    progress(72, "Собираем структуру презентации")
    merge_prompt = (
        "Подготовь связный краткий пересказ лекции, а не перечень тем или каталог терминов. "
        f"Сделай от {min_slides} до {max_slides} содержательных слайдов. "
        "Соблюдай ход мысли лектора: задача → подход → как он работает → пример → ограничения и вывод. "
        "Сохраняй порядок лекции и разделяй самостоятельные темы на разные слайды. "
        "Покрой запись от начала до конца по временным якорям ниже; не пропускай большие отрезки. "
        "Каждый слайд должен содержать title, claim (один ясный вывод), explanation "
        "(2–3 связанных предложения, объясняющие почему и как), example (конкретный пример из записи "
        "или пустую строку) и timestamp. Не используй bullets и не своди содержание к названиям тем. "
        "Добавь visual: type должен быть flow для последовательности или cards для ролей/вариантов; "
        "items — 2–4 объекта с короткими title и detail. Ставь type=none, если схема не поможет понять мысль. "
        "Не делай график из выдуманных чисел. "
        "Пример должен подтверждать мысль и происходить только из этой лекции. "
        "Не выдумывай примеры и причинно-следственные связи. "
        "Не повторяй мысли на разных слайдах. summary — максимум 2 коротких предложения. "
        "Используй только факты из заметок. Не угадывай термины по похожему звучанию; "
        "если распознанный термин неясен, пропусти его. Сохраняй английское написание терминов, "
        "когда перевод ненадёжен. Термины в словарь включай только если лекция объясняет их значение, максимум 4. "
        "В action_items включай только явно заданные задания или следующие шаги. "
        "Не включай приглашения задавать вопросы, участвовать в обсуждении или связываться с организаторами. "
        "Если конкретных заданий нет, верни пустой список.\n\n"
        f"Заголовок исходной записи: {title}\nЗаметки по частям:\n"
        f"{json.dumps(compact_notes, ensure_ascii=False)}\n\n"
        f"Временные якоря частей исходной записи (секунды): {json.dumps(timeline_anchors, ensure_ascii=False)}\n\n"
        "Верни JSON-объект с полями: title (строка), subtitle (строка), summary (строка), "
        "slides (массив объектов с title, claim, explanation, example, timestamp, "
        "visual: {type, items: [{title, detail}]}), "
        "terms (массив объектов term, translation, explanation), action_items (массив строк). "
        f"Строго соблюдай лимиты: от {min_slides} до {max_slides} слайдов, "
        "до 4 терминов и до 3 заданий."
    )
    merged = _generate(merge_prompt, system)
    raw_slides = merged.get("slides") if isinstance(merged.get("slides"), list) else []
    if len(raw_slides) < min_slides:
        progress(82, "Проверяем охват записи")
        merged = _generate(
            "Исправь предыдущий результат: в нём недостаточно слайдов для полного пересказа. "
            f"Верни ровно {min_slides} разных слайдов, равномерно охватывающих начало, середину и конец. "
            "Не добавляй фактов и не дроби одну мысль на повторы. Сохрани все поля и требования исходного задания.\n\n"
            f"Заметки: {json.dumps(compact_notes, ensure_ascii=False)}\n"
            f"Временные якоря: {json.dumps(timeline_anchors, ensure_ascii=False)}\n"
            f"Предыдущий ответ: {json.dumps(merged, ensure_ascii=False)}\n\n{merge_prompt}",
            system,
        )
        raw_slides = merged.get("slides") if isinstance(merged.get("slides"), list) else []
    if len(raw_slides) < min_slides:
        # Large final prompts make smaller local models collapse long lessons
        # into a few sections. Retry in chronological batches with a smaller
        # context and a smaller slide-count target per request.
        batch_count = min(3, len(compact_notes))
        batched_slides: list[dict[str, Any]] = []
        if batch_count:
            base_count, extra_count = divmod(min_slides, batch_count)
            for batch_index in range(batch_count):
                start = batch_index * len(compact_notes) // batch_count
                end = (batch_index + 1) * len(compact_notes) // batch_count
                batch_notes = compact_notes[start:end]
                batch_anchors = timeline_anchors[start:end]
                target_count = base_count + (1 if batch_index < extra_count else 0)
                progress(
                    83 + int(batch_index / batch_count * 12),
                    f"Собираем часть {batch_index + 1} из {batch_count}",
                )
                batch_prompt = (
                    f"Занятие: {title}. Составь ровно {target_count} разных слайдов "
                    "только по этому отрезку урока. Распредели их по временным якорям и сохраняй порядок. "
                    "Это связный пересказ: каждый слайд должен объяснять мысль, а не просто называть тему. "
                    "Не добавляй факты и не повторяй идеи. explanation — 2 коротких связанных предложения; "
                    "example — только конкретный пример из заметок или пустая строка. "
                    "Для visual используй type=none или cards/flow только если схема помогает понять мысль; "
                    "не придумывай числовые графики. Верни JSON с массивом slides, у каждого поля: "
                    "title, claim, explanation, example, timestamp, visual:{type,items:[{title,detail}]}.\n"
                    f"Заметки отрезка: {json.dumps(batch_notes, ensure_ascii=False)}\n"
                    f"Временные якоря: {json.dumps(batch_anchors, ensure_ascii=False)}"
                )
                batch_result = _generate(batch_prompt, system)
                batch_slides = batch_result.get("slides") if isinstance(batch_result.get("slides"), list) else []
                batch_slides = [slide for slide in batch_slides if isinstance(slide, dict)]
                if len(batch_slides) < target_count:
                    batch_result = _generate(
                        f"Верни ровно {target_count} слайдов, равномерно покрывающих эти заметки. "
                        "Нужны отдельные мысли из разных временных якорей, без повторов. Используй только факты ниже. "
                        "JSON: {slides:[{title,claim,explanation,example,timestamp,visual:{type,items:[{title,detail}]}}]}\n"
                        f"Заметки: {json.dumps(batch_notes, ensure_ascii=False)}\n"
                        f"Якоря: {json.dumps(batch_anchors, ensure_ascii=False)}",
                        system,
                    )
                    batch_slides = batch_result.get("slides") if isinstance(batch_result.get("slides"), list) else []
                    batch_slides = [slide for slide in batch_slides if isinstance(slide, dict)]
                batched_slides.extend(batch_slides[:target_count])
        if len(batched_slides) < min_slides:
            raise RuntimeError(
                f"Модель подготовила {len(batched_slides)} слайдов вместо минимум {min_slides}, "
                "даже при генерации по частям. Неполный пересказ не сохранён. "
                "Попробуйте выбрать более лёгкую локальную модель или запустить создание повторно."
            )
        merged["slides"] = batched_slides
        raw_slides = batched_slides
    raw_terms = merged.get("terms") if isinstance(merged.get("terms"), list) else []
    result = {
        "title": str(merged.get("title") or title),
        "subtitle": str(merged.get("subtitle") or "Конспект занятия"),
        "summary": str(merged.get("summary") or ""),
        "slides": [
            {
                "title": str(slide.get("title") or "Ключевая идея"),
                "claim": str(slide.get("claim") or ""),
                "explanation": str(slide.get("explanation") or ""),
                "example": str(slide.get("example") or ""),
                "timestamp": str(slide.get("timestamp") or ""),
                "visual": {
                    "type": slide.get("visual", {}).get("type", "none")
                    if isinstance(slide.get("visual"), dict) else "none",
                    "items": [
                        {
                            "title": str(item.get("title") or "")[:60],
                            "detail": str(item.get("detail") or "")[:160],
                        }
                        for item in slide.get("visual", {}).get("items", [])[:4]
                        if isinstance(item, dict)
                    ] if isinstance(slide.get("visual"), dict) and isinstance(slide.get("visual", {}).get("items"), list) else [],
                },
            }
            for slide in raw_slides[:max_slides] if isinstance(slide, dict)
        ],
        "terms": [
            {
                "term": str(term.get("term") or ""),
                "translation": str(term.get("translation") or ""),
                "explanation": str(term.get("explanation") or ""),
            }
            for term in raw_terms[:4] if isinstance(term, dict)
        ],
        "action_items": [str(item) for item in merged.get("action_items", [])[:3] if item is not None]
        if isinstance(merged.get("action_items", []), list) else [],
    }
    if not result["slides"]:
        raise RuntimeError("Ollama не сформировал слайды. Попробуйте повторить анализ.")
    return result
