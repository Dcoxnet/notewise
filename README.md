# NoteWise

Локальное приложение для записи уроков через OBS, транскрибации англоязычной речи и создания краткой презентации в PDF.

Транскрибация речи выполняется локально через faster-whisper. Конспект создаёт Ollama, PDF собирает Typst. Текст и изображения со слайдов урока приложение пока не распознаёт.

## Требования

- Linux
- Node.js и pnpm (`pnpm` версии из `package.json`)
- Python 3.14
- OBS Studio с включённым WebSocket-сервером
- FFmpeg, Typst и Ollama

На CachyOS/Arch установи системные пакеты:

```bash
sudo pacman -S --needed ffmpeg typst
```

Установи Ollama, если её ещё нет:

```bash
curl -fL https://ollama.com/install.sh -o /tmp/ollama-install.sh
sh /tmp/ollama-install.sh
```

Если Ollama не работает как системная служба, запусти её в отдельном терминале:

```bash
ollama serve
```

В другом терминале загрузи модель:

```bash
ollama pull qwen2.5:7b
```

## Установка проекта

Команды выполняются из каталога проекта:

```bash
cd ~/zoom-ai-notes
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
pnpm install
```

## Запуск

```bash
./dev.sh
```

Скрипт запускает backend на `http://127.0.0.1:8000` и frontend на `http://localhost:3000`. При запуске он запросит пароль OBS WebSocket скрытым вводом. Остановка: `Ctrl+C`.

Проверка backend:

```bash
curl http://127.0.0.1:8000/api/health
```

## Настройка OBS

В OBS открой **Инструменты → WebSocket Server Settings**:

1. Включи WebSocket-сервер и аутентификацию.
2. Используй порт `4455`.
3. Добавь захват экрана и системного звука.
4. Выбери папку и качество записей в настройках OBS.

При захвате экрана в KDE Wayland подтверди системный запрос на доступ к экрану.

## Работа с уроком

**Новая запись:** открой NoteWise, запусти запись OBS через интерфейс и останови её после урока. Транскрибация начнётся автоматически. Когда статус станет «Готово», открой текст или создай PDF.

**Существующая запись:** нажми «Импортировать запись», выбери аудио или видео, затем нажми «Транскрибировать». После завершения можно открыть текст или создать PDF.

При первом запуске faster-whisper скачает модель `small.en` в `data/models`. Для PDF нужна запущенная Ollama с моделью `qwen2.5:7b`.

## Локальные данные

Все данные приложения хранятся в `data/`:

- `recordings/` — импортированные записи;
- `audio/` — извлечённое аудио;
- `transcripts/` — транскрипты;
- `summaries/` — данные презентаций и PDF;
- `models/` — модель faster-whisper;
- `lessons.sqlite3` — база библиотеки уроков.

Каталог `data/`, записи, транскрипты, PDF-конспекты, базы и секреты исключены из Git. `README.md` — основная документация проекта и добавляется в репозиторий.

## Локальные команды проверки

```bash
pnpm lint
pnpm exec tsc --noEmit
.venv/bin/python -m compileall -q backend/app
```
