# NoteWise

Запись занятий через OBS, распознавание английской речи и создание PDF-конспектов. Обработка работает локально: faster-whisper распознаёт речь, Ollama составляет конспект, Typst собирает PDF.

## Требования

- Linux
- Node.js и pnpm (версия указана в `package.json`)
- Python 3.14
- OBS Studio, FFmpeg, Ollama и Typst

## Установка

```bash
git clone https://github.com/Dcoxnet/notewise.git
cd notewise
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
pnpm install
ollama pull qwen2.5:7b
```

Если Ollama не запущена, выполни в отдельном терминале:

```bash
ollama serve
```

## OBS

В **Tools → WebSocket Server Settings** включи сервер и аутентификацию. Порт: `4455`.

Добавь захват экрана и звука. Папка и качество записи задаются в настройках OBS.

## Запуск

Из корня проекта:

```bash
./dev.sh
```

Скрипт запросит пароль OBS WebSocket и запустит оба сервера:

- Интерфейс: http://localhost:3000
- API: http://127.0.0.1:8000

Остановка: `Ctrl+C`.

## Использование

Запусти и останови запись через интерфейс. После остановки начнётся распознавание речи. Готовый текст можно открыть или преобразовать в PDF.

Для существующего файла нажми **«Импортировать запись»**, выбери аудио или видео и запусти транскрибацию.

При первом распознавании скачивается модель `small.en`. Для создания PDF нужна запущенная Ollama с моделью `qwen2.5:7b`. Изображения и текст со слайдов в видео пока не распознаются.

## Данные

Записи, аудио, транскрипты, модели и PDF хранятся в `data/`. Библиотека занятий — в `data/lessons.sqlite3`. Локальные данные исключены из Git.

## Проверки

```bash
pnpm lint
pnpm exec tsc --noEmit
.venv/bin/python -m compileall -q backend/app
```
