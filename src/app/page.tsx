"use client";

import { useEffect, useRef, useState } from "react";

type IconName = "grid" | "record" | "library" | "settings" | "search" | "bell" | "play" | "clock" | "arrow" | "spark" | "mic" | "monitor" | "check" | "chevron";

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true as const };
  const paths: Record<IconName, React.ReactNode> = {
    grid: <><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></>,
    record: <><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/></>,
    library: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v16H6.5A2.5 2.5 0 0 0 4 21z"/><path d="M4 5.5v15M8 7h8M8 11h7"/></>,
    settings: <><circle cx="12" cy="12" r="3"/><path d="m19.4 15 .1.1a1.7 1.7 0 0 1-2.4 2.4l-.1-.1a1.7 1.7 0 0 0-2.9 1.2v.2a1.7 1.7 0 0 1-3.4 0v-.2a1.7 1.7 0 0 0-2.9-1.2l-.1.1a1.7 1.7 0 1 1-2.4-2.4l.1-.1a1.7 1.7 0 0 0-1.2-2.9H4a1.7 1.7 0 0 1 0-3.4h.2a1.7 1.7 0 0 0 1.2-2.9l-.1-.1a1.7 1.7 0 1 1 2.4-2.4l.1.1a1.7 1.7 0 0 0 2.9-1.2V2a1.7 1.7 0 0 1 3.4 0v.2a1.7 1.7 0 0 0 2.9 1.2l.1-.1a1.7 1.7 0 1 1 2.4 2.4l-.1.1a1.7 1.7 0 0 0 1.2 2.9h.2a1.7 1.7 0 0 1 0 3.4h-.2a1.7 1.7 0 0 0-1.2 2.9Z"/></>,
    search: <><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/></>,
    bell: <><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9"/><path d="M10 21h4"/></>,
    play: <path d="m9 6 10 6-10 6z" fill="currentColor" stroke="none"/>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    spark: <><path d="m12 3 1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="m19 16 .8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"/></>,
    mic: <><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3m-4 0h8"/></>,
    monitor: <><rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/></>,
    check: <path d="m5 12 4 4L19 6"/>,
    chevron: <path d="m9 18 6-6-6-6"/>,
  };
  return <svg {...common}>{paths[name]}</svg>;
}

type SavedLesson = {
  id: string;
  title: string;
  file_name: string;
  recorded_at: string;
  duration_seconds: number;
  transcription_status: "not_started" | "queued" | "processing" | "completed" | "failed";
  transcription_progress: number;
  transcription_error: string | null;
  summary_status: "not_started" | "queued" | "processing" | "completed" | "failed";
  summary_progress: number;
  summary_error: string | null;
};

type Transcript = { text: string; segments: { start: number; end: number; text: string }[] };

export default function Home() {
  const [section, setSection] = useState<"overview" | "recording">("overview");
  const [notice, setNotice] = useState(false);
  const [apiState, setApiState] = useState<"checking" | "offline" | "ready">("checking");
  const [obsConnected, setObsConnected] = useState(false);
  const [recording, setRecording] = useState(false);
  const [lessons, setLessons] = useState<SavedLesson[]>([]);
  const [busy, setBusy] = useState(false);
  const [apiError, setApiError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [selectedTranscript, setSelectedTranscript] = useState<{ id: string; title: string; transcript: Transcript } | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef<number | null>(null);
  const uploadInput = useRef<HTMLInputElement | null>(null);
  const apiBase = process.env.NEXT_PUBLIC_LOCAL_API_URL ?? "http://127.0.0.1:8000";

  useEffect(() => {
    let active = true;
    const refreshLessons = async () => {
      try {
        const response = await fetch(`${apiBase}/api/lessons`, { cache: "no-store" });
        if (!response.ok) return;
        const data: SavedLesson[] = await response.json();
        if (active) setLessons(data);
      } catch {
        // The library stays empty until the local backend is running.
      }
    };
    void refreshLessons();
    const interval = window.setInterval(() => void refreshLessons(), 10000);
    return () => { active = false; window.clearInterval(interval); };
  }, [apiBase]);

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const response = await fetch(`${apiBase}/api/obs/status`, { cache: "no-store" });
        if (!response.ok) {
          const payload = await response.json().catch(() => null);
          throw new Error(payload?.detail ?? "Не удалось связаться с OBS.");
        }
        const payload: { connected: boolean; recording: boolean; duration_ms: number } = await response.json();
        if (active) {
          if (payload.recording && startedAt.current === null) {
            startedAt.current = Date.now() - payload.duration_ms;
            setElapsed(Math.floor(payload.duration_ms / 1000));
          }
          if (!payload.recording) startedAt.current = null;
          setApiState("ready");
          setObsConnected(payload.connected);
          setRecording(payload.recording);
          setApiError("");
        }
      } catch (error) {
        if (active) {
          setApiState("offline");
          setObsConnected(false);
          setApiError(error instanceof Error ? error.message : "Локальный backend недоступен.");
        }
      }
    };
    void refresh();
    const interval = window.setInterval(() => void refresh(), 4000);
    return () => { active = false; window.clearInterval(interval); };
  }, [apiBase]);

  useEffect(() => {
    if (!recording) return;
    const start = startedAt.current ?? Date.now();
    startedAt.current = start;
    const tick = () => setElapsed(Math.floor((Date.now() - start) / 1000));
    const interval = window.setInterval(tick, 1000);
    return () => window.clearInterval(interval);
  }, [recording]);

  async function changeRecording(action: "start" | "stop") {
    setBusy(true);
    setApiError("");
    try {
      const response = await fetch(`${apiBase}/api/obs/${action}`, { method: "POST" });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail ?? "Команда OBS завершилась ошибкой.");
      startedAt.current = payload.recording ? (startedAt.current ?? Date.now()) : null;
      if (!payload.recording) setElapsed(0);
      setRecording(payload.recording);
      setObsConnected(true);
      setApiState("ready");
      if (action === "stop") {
        const lessonsResponse = await fetch(`${apiBase}/api/lessons`, { cache: "no-store" });
        if (lessonsResponse.ok) setLessons(await lessonsResponse.json());
        if (!payload.lesson) setApiError(payload.message ?? "Файл остановленной записи не появился в библиотеке.");
      }
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Не удалось выполнить команду OBS.");
    } finally {
      setBusy(false);
    }
  }

  async function importRecording(file?: File) {
    if (!file) return;
    setUploading(true);
    setApiError("");
    try {
      const form = new FormData();
      form.append("file", file);
      const response = await fetch(`${apiBase}/api/lessons/import`, { method: "POST", body: form });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail ?? "Не удалось импортировать запись.");
      const lessonsResponse = await fetch(`${apiBase}/api/lessons`, { cache: "no-store" });
      if (lessonsResponse.ok) setLessons(await lessonsResponse.json());
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Не удалось импортировать запись.");
    } finally {
      setUploading(false);
      if (uploadInput.current) uploadInput.current.value = "";
    }
  }

  async function transcribeLesson(lesson: SavedLesson) {
    setApiError("");
    try {
      if (lesson.transcription_status === "completed") {
        const response = await fetch(`${apiBase}/api/lessons/${lesson.id}/transcript`, { cache: "no-store" });
        const payload = await response.json().catch(() => null);
        if (!response.ok) throw new Error(payload?.detail ?? "Не удалось загрузить транскрипт.");
        setSelectedTranscript({ id: lesson.id, title: lesson.title, transcript: payload });
        return;
      }
      const response = await fetch(`${apiBase}/api/lessons/${lesson.id}/transcribe`, { method: "POST" });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail ?? "Не удалось запустить транскрибацию.");
      const lessonsResponse = await fetch(`${apiBase}/api/lessons`, { cache: "no-store" });
      if (lessonsResponse.ok) setLessons(await lessonsResponse.json());
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Ошибка транскрибации.");
    }
  }

  async function createSummary(lesson: SavedLesson) {
    setApiError("");
    try {
      const response = await fetch(`${apiBase}/api/lessons/${lesson.id}/summarize`, { method: "POST" });
      const payload = await response.json().catch(() => null);
      if (!response.ok) throw new Error(payload?.detail ?? "Не удалось создать PDF-конспект.");
      const lessonsResponse = await fetch(`${apiBase}/api/lessons`, { cache: "no-store" });
      if (lessonsResponse.ok) setLessons(await lessonsResponse.json());
    } catch (error) {
      setApiError(error instanceof Error ? error.message : "Ошибка при создании PDF-конспекта.");
    }
  }

  const timestamp = (seconds: number) => `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;

  function downloadTranscript() {
    if (!selectedTranscript) return;
    const contents = selectedTranscript.transcript.segments
      .map((segment) => `[${timestamp(segment.start)}] ${segment.text}`)
      .join("\n\n");
    const blob = new Blob([`Транскрипт: ${selectedTranscript.title}\n\n${contents}\n`], {
      type: "text/plain;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${selectedTranscript.title.replace(/[\\/:*?\"<>|]/g, "-")}-transcript.txt`;
    link.click();
    URL.revokeObjectURL(url);
  }

  const elapsedLabel = `${String(Math.floor(elapsed / 3600)).padStart(2, "0")}:${String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
  const totalLearningHours = (lessons.reduce((total, lesson) => total + lesson.duration_seconds, 0) / 3600).toFixed(1);
  const durationLabel = (seconds: number) => seconds >= 3600
    ? `${Math.floor(seconds / 3600)} ч ${Math.floor((seconds % 3600) / 60)} мин`
    : `${Math.floor(seconds / 60)} мин`;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" onClick={() => setSection("overview")}>
          <span className="brand-mark"><span /><span /><span /></span>
          <span className="brand-name">note<span>wise</span></span>
        </a>
        <div className="workspace-label">РАБОЧЕЕ ПРОСТРАНСТВО</div>
        <nav className="main-nav" aria-label="Основная навигация">
          <button className={`nav-item ${section === "overview" ? "active" : ""}`} onClick={() => setSection("overview")}><Icon name="grid"/><span>Обзор</span></button>
          <button className={`nav-item ${section === "recording" ? "active" : ""}`} onClick={() => setSection("recording")}><Icon name="record"/><span>Запись</span><span className="nav-pill">NEW</span></button>
          <button className="nav-item" onClick={() => setNotice(true)}><Icon name="library"/><span>Мои уроки</span><span className="nav-count">{lessons.length}</span></button>
        </nav>
        <div className="sidebar-bottom">
          <div className="storage-card"><div className="storage-head"><span>Хранилище</span><span>2.4 / 10 ГБ</span></div><div className="storage-track"><span /></div><p>Записи хранятся только на вашем устройстве</p></div>
          <button className="nav-item" onClick={() => setNotice(true)}><Icon name="settings"/><span>Настройки</span></button>
          <div className="profile"><div className="avatar">АК</div><div className="profile-copy"><strong>Алексей К.</strong><span>Локальный профиль</span></div><button className="more-button" aria-label="Дополнительные настройки">•••</button></div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar"><div className="breadcrumb">Моё пространство <Icon name="chevron" size={15}/><strong>{section === "overview" ? "Обзор" : "Запись"}</strong></div><div className="top-actions"><button className="icon-button" aria-label="Поиск" onClick={() => setNotice(true)}><Icon name="search"/></button><button className="icon-button notification-button" aria-label="Уведомления" onClick={() => setNotice(true)}><Icon name="bell"/><i /></button><div className="top-divider"/><div className="mini-avatar">АК</div></div></header>

        <div className="content">
          {section === "overview" ? <>
            <div className="welcome-row"><div><div className="eyebrow"><span className="eyebrow-dot"/> ВАШЕ ПРОСТРАНСТВО ДЛЯ ЗНАНИЙ</div><h1>Доброе утро, Алексей <span className="wave">✳</span></h1><p className="subtitle">Каждый урок становится знанием, к которому легко вернуться.</p></div><button className="primary-button" onClick={() => setSection("recording")}><Icon name="record" size={18}/> Начать запись</button></div>

            <section className="hero-card"><div className="hero-copy"><div className="hero-tag"><Icon name="spark" size={15}/> ВАШ AI-КОНСПЕКТ</div><h2>Больше внимания<br/>уроку. Меньше заметкам.</h2><p>Записывайте занятия, а NoteWise сохранит ключевые идеи, термины и примеры на русском.</p><button className="hero-link" onClick={() => setSection("recording")}>Записать урок <Icon name="arrow" size={17}/></button></div><div className="hero-art" aria-hidden="true"><div className="art-glow"/><div className="note-sheet"><div className="sheet-top"><span className="sheet-dot"/><span className="sheet-line short"/></div><div className="sheet-heading">Нейронные сети</div><div className="sheet-line wide"/><div className="sheet-line medium"/><div className="sheet-highlight"><span className="highlight-star">✦</span> Важная идея урока</div><div className="sheet-line wide muted"/><div className="sheet-line short muted"/><div className="sheet-time"><span>◷</span> 12:48</div></div><div className="art-bubble bubble-one">Aa</div><div className="art-bubble bubble-two"><Icon name="spark" size={20}/></div><div className="art-orbit orbit-one"/><div className="art-orbit orbit-two"/></div><div className="hero-foot"><span><span className="privacy-dot"/> Файлы остаются на вашем устройстве</span><span>Локально и конфиденциально</span></div></section>

            <div className="section-heading"><div><h2>Ваша библиотека</h2><p>Продолжайте с того места, где остановились</p></div><div className="library-actions"><input ref={uploadInput} type="file" accept="video/mp4,video/x-matroska,video/quicktime,video/webm,audio/*,.m4v" hidden onChange={(event) => void importRecording(event.target.files?.[0])}/><button className="text-link" disabled={uploading} onClick={() => uploadInput.current?.click()}>{uploading ? "Загружаем…" : "Импортировать запись"}</button></div></div>
            {apiError && section === "overview" && <div className="api-error" role="alert">{apiError}</div>}
            <section className="lesson-list" aria-label="Последние уроки">{lessons.length ? lessons.map((lesson) => <div className="lesson-row" key={lesson.id}><span className="lesson-icon violet">{lesson.title.slice(0, 2).toUpperCase()}</span><span className="lesson-main"><strong>{lesson.title}</strong><span>{new Date(lesson.recorded_at).toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" })}</span></span><span className="lesson-duration"><Icon name="clock" size={15}/>{durationLabel(lesson.duration_seconds)}</span><span className={`lesson-status ${lesson.transcription_status === "completed" ? "ready" : lesson.transcription_status === "processing" || lesson.transcription_status === "queued" ? "processing" : "ready"}`}><i/>{lesson.transcription_status === "completed" ? "Готово" : lesson.transcription_status === "processing" ? `${lesson.transcription_progress}%` : lesson.transcription_status === "queued" ? "В очереди" : lesson.transcription_status === "failed" ? "Ошибка" : "Сохранено"}</span><button className="transcribe-button" onClick={() => void transcribeLesson(lesson)} disabled={lesson.transcription_status === "processing" || lesson.transcription_status === "queued"}>{lesson.transcription_status === "completed" ? "Открыть текст" : lesson.transcription_status === "processing" || lesson.transcription_status === "queued" ? "Распознаём" : lesson.transcription_status === "failed" ? "Повторить" : "Транскрибировать"}</button>{lesson.transcription_status === "completed" && <>{lesson.summary_status === "completed" && <a className="transcribe-button pdf-download" href={`${apiBase}/api/lessons/${lesson.id}/summary/pdf`} download>PDF</a>}<button className="transcribe-button" onClick={() => void createSummary(lesson)} disabled={lesson.summary_status === "processing" || lesson.summary_status === "queued"}>{lesson.summary_status === "processing" ? `PDF ${lesson.summary_progress}%` : lesson.summary_status === "queued" ? "PDF в очереди" : lesson.summary_status === "completed" ? "Обновить PDF" : lesson.summary_status === "failed" ? "Повторить PDF" : "Создать PDF"}</button></>}<a className="lesson-open" href={`${apiBase}/api/lessons/${lesson.id}/file`} target="_blank" rel="noreferrer" aria-label={`Открыть видео ${lesson.file_name}`} title="Открыть видео"><Icon name="arrow" size={17}/></a>{((lesson.transcription_status === "failed" && lesson.transcription_error) || (lesson.summary_status === "failed" && lesson.summary_error)) && <span className="lesson-error">{lesson.summary_error || lesson.transcription_error}</span>}</div>) : <div className="empty-library"><Icon name="library" size={22}/><strong>Записей пока нет</strong><span>Импортируйте записанный файл или начните запись в OBS.</span><button onClick={() => uploadInput.current?.click()}>Импортировать запись <Icon name="arrow" size={15}/></button></div>}</section>
            {selectedTranscript && <section className="transcript-panel"><div className="transcript-heading"><div><strong>{selectedTranscript.title}</strong><span>Транскрипт на английском · с таймкодами</span></div><div className="transcript-actions"><button className="transcribe-button" onClick={downloadTranscript}>Скачать текст</button><button onClick={() => setSelectedTranscript(null)} aria-label="Закрыть транскрипт">×</button></div></div><div className="transcript-text">{selectedTranscript.transcript.segments.map((segment, index) => <p key={`${selectedTranscript.id}-${index}`}><time>{timestamp(segment.start)}</time>{segment.text}</p>)}</div></section>}

            <div className="bottom-grid"><section className="stat-card"><div className="stat-icon purple"><Icon name="library" size={18}/></div><div><span>Всего уроков</span><strong>{lessons.length} <small>уроков</small></strong></div><div className="stat-spark spark-purple"><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/></div></section><section className="stat-card"><div className="stat-icon green"><Icon name="clock" size={18}/></div><div><span>Время обучения</span><strong>{totalLearningHours} <small>часов</small></strong></div><div className="stat-spark spark-green"><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/></div></section><section className="stat-card focus-card"><div className="focus-icon"><Icon name="spark" size={18}/></div><div><strong>Маленький шаг — большое знание</strong><span>Запишите следующий урок, чтобы сохранить важное.</span></div></section></div>
          </> : <div className="recording-page"><div className="eyebrow"><span className="eyebrow-dot"/> ЛОКАЛЬНАЯ ЗАПИСЬ</div><h1>Запись урока</h1><p className="subtitle">Захват экрана и системного звука через OBS Studio.</p><section className="record-panel"><div className="record-visual"><div className={`record-ring ${recording ? "is-recording" : ""}`}><div><Icon name="record" size={34}/></div></div><span>{recording ? "Идёт запись" : obsConnected ? "OBS подключён" : "Подключение к OBS"}</span><p>{recording ? elapsedLabel : apiState === "checking" ? "Проверяем локальный сервис и OBS…" : obsConnected ? "Можно начать запись. Убедитесь, что выбраны нужные источники." : "Запустите локальный backend и настройте OBS WebSocket."}</p></div><div className="connection-list"><div className="connection-row"><span className="connection-icon"><Icon name="monitor"/></span><span><strong>OBS Studio</strong><small>{apiState === "checking" ? "Проверяем подключение" : obsConnected ? "Локальное подключение установлено" : apiState === "offline" ? "Локальный сервис или OBS недоступен" : "Подключение не настроено"}</small></span><span className={`connection-state ${obsConnected ? "connected-state" : ""}`}><i/>{obsConnected ? "Подключён" : "Не подключён"}</span></div><div className="connection-row"><span className="connection-icon"><Icon name="mic"/></span><span><strong>Системный звук</strong><small>Источник настраивается в OBS / PipeWire</small></span><span className="connection-state muted-state">В OBS</span></div><div className="connection-row"><span className="connection-icon"><Icon name="monitor"/></span><span><strong>Захват экрана</strong><small>Разрешение KDE / Wayland</small></span><span className="connection-state muted-state">В OBS</span></div><div className="record-actions">{recording ? <button className="stop-button" onClick={() => void changeRecording("stop")} disabled={busy}><Icon name="record" size={18}/>{busy ? "Останавливаем…" : "Остановить запись"}</button> : <button className="primary-button" onClick={() => void changeRecording("start")} disabled={!obsConnected || busy}><Icon name="record" size={18}/>{busy ? "Подключаемся…" : "Начать запись"}</button>}<button className="secondary-button" onClick={() => setNotice(true)}>Настроить OBS</button></div>{apiError && <div className="api-error" role="alert">{apiError}</div>}<div className="record-note"><span>ⓘ</span> Для записи необходимо разрешение участников встречи. Записи сохраняются локально.</div></div></section><section className="setup-card"><span className="setup-number">01</span><div><strong>Подготовьте OBS Studio</strong><p>Включите локальный WebSocket сервер, задайте пароль и добавьте захват экрана и системный звук.</p></div><span className="setup-check"><Icon name="check" size={17}/></span></section></div>}
          <footer className="page-footer"><span>NoteWise <span className="footer-dot">·</span> Ваша приватная AI-заметка</span><span><span className="privacy-dot"/> Все данные хранятся локально</span></footer>
        </div>
      </main>
      {notice && <div className="toast" role="status"><span className="toast-icon">i</span><span><strong>Этот раздел пока не подключён</strong><small>Библиотека записей, поиск и настройки появятся на следующих этапах. Управление OBS доступно во вкладке «Запись».</small></span><button onClick={() => setNotice(false)} aria-label="Закрыть">×</button></div>}
    </div>
  );
}
