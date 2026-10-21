import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

import {
  ApiError,
  changeStudentChatModel,
  changeStudentChatSupport,
  createStudentChat,
  deleteStudentChat,
  extractPdf,
  listModels,
  listStudentChats,
  listUsers,
  setPreferredModel,
  UNAVAILABLE,
  type ExtractedPage,
  type LessonSource,
  type Me,
  type ModelList,
  type StudentChat,
  type StudentChats,
  type SupportLevel,
  type UserView,
} from "./api";
import { PageSkeleton } from "./Skeleton";
import {
  initialModel,
  lessonTokens,
  MAX_PDF_BYTES,
  modelAllowed,
  modelSummary,
  pagesText,
  SUPPORT_LEVELS,
  supportLevel,
  toBase64,
} from "./lessons";

interface UploadedPdf {
  filename: string;
  pages: ExtractedPage[];
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

function byName(a: UserView, b: UserView): number {
  return a.display_name.localeCompare(b.display_name);
}

function shortDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

export function LessonsPage({
  me,
  onOpenChat,
}: {
  me: Me;
  onOpenChat: (studentId: string, chatId: string) => void;
}) {
  const [students, setStudents] = useState<UserView[] | null>(null);
  const [studentId, setStudentId] = useState("");
  const [chats, setChats] = useState<StudentChats | null>(null);
  const [title, setTitle] = useState("");
  const [topics, setTopics] = useState("");
  const [notes, setNotes] = useState("");
  const [material, setMaterial] = useState("");
  const [sources, setSources] = useState<LessonSource[]>([]);
  const [support, setSupport] = useState<SupportLevel>("balanced");
  const [models, setModels] = useState<ModelList | null>(null);
  const [pickedModel, setPickedModel] = useState<string | null>(null);
  const [licensed, setLicensed] = useState(false);
  const [pdf, setPdf] = useState<UploadedPdf | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listUsers()
      .then((users) => {
        const mine = users.filter((u) => u.role === "student").sort(byName);
        setStudents(mine);
        setStudentId(mine[0]?.id ?? me.id);
      })
      .catch((e: unknown) => setError(messageOf(e)));
  }, [me.id]);

  useEffect(() => {
    listModels()
      .then(setModels)
      .catch((e: unknown) => setError(messageOf(e)));
  }, []);

  const forStudent = studentId !== me.id;
  const pickedOption = models?.models.find((m) => m.id === pickedModel);
  const model = !models
    ? ""
    : pickedOption && modelAllowed(pickedOption, forStudent)
      ? pickedOption.id
      : initialModel(models, forStudent);

  useEffect(() => {
    if (!studentId) return;
    listStudentChats(studentId)
      .then(setChats)
      .catch((e: unknown) => setError(messageOf(e)));
  }, [studentId]);

  const lesson = { title, topics: topics.split("\n"), notes, material, sources, support };
  const tokens = lessonTokens(lesson);
  const maxTokens = chats?.max_lesson_tokens ?? 0;
  const overCap = chats !== null && tokens > maxTokens;
  const full = chats !== null && chats.chats.length >= chats.max_chats;
  const studentName =
    studentId === me.id
      ? "you"
      : (students?.find((s) => s.id === studentId)?.display_name ?? "this student");
  const canSave =
    !busy &&
    chats !== null &&
    !full &&
    title.trim() !== "" &&
    !overCap &&
    (!material.trim() || licensed);

  async function act(work: () => Promise<string>) {
    setBusy(true);
    setError(null);
    setStatus(null);
    try {
      setStatus(await work());
    } catch (e) {
      setError(messageOf(e));
    } finally {
      setBusy(false);
    }
  }

  function resetForm() {
    setTitle("");
    setTopics("");
    setNotes("");
    setMaterial("");
    setSources([]);
    setSupport("balanced");
    setPickedModel(null);
    setLicensed(false);
    setPdf(null);
    setPicked(new Set());
  }

  function choosePdf(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > MAX_PDF_BYTES) {
      setError("That PDF is over 10 MB. Upload just the pages for this lesson.");
      return;
    }
    void act(async () => {
      const bytes = new Uint8Array(await file.arrayBuffer());
      const extracted = await extractPdf(file.name, toBase64(bytes));
      setPdf({ filename: file.name, pages: extracted.pages });
      setPicked(new Set(extracted.pages.filter((p) => p.text).map((p) => p.number)));
      return `Read ${extracted.pages.length} pages from ${file.name}. Untick any you don't want.`;
    });
  }

  function togglePage(number: number) {
    setPicked((current) => {
      const next = new Set(current);
      if (next.has(number)) next.delete(number);
      else next.add(number);
      return next;
    });
  }

  function addPages() {
    if (!pdf) return;
    const text = pagesText(pdf.pages, picked);
    setMaterial((current) => (current.trim() ? `${current.trim()}\n\n${text}` : text));
    setSources((current) => [
      ...current,
      { filename: pdf.filename, pages: [...picked].sort((a, b) => a - b) },
    ]);
    setPdf(null);
    setPicked(new Set());
  }

  function create(event: FormEvent) {
    event.preventDefault();
    void act(async () => {
      const chat = await createStudentChat(studentId, lesson, licensed, {}, model || undefined);
      setChats((current) => current && { ...current, chats: [chat, ...current.chats] });
      resetForm();
      return `Set up "${chat.title}" for ${studentName}.`;
    });
  }

  function changeSupport(chat: StudentChat, level: SupportLevel) {
    void act(async () => {
      const changed = await changeStudentChatSupport(studentId, chat.id, level);
      setChats(
        (current) =>
          current && {
            ...current,
            chats: current.chats.map((c) => (c.id === changed.id ? changed : c)),
          },
      );
      return `"${chat.title}" is now ${supportLevel(level).label}.`;
    });
  }

  function changeModel(chat: StudentChat, id: string) {
    void act(async () => {
      const changed = await changeStudentChatModel(studentId, chat.id, id);
      setChats(
        (current) =>
          current && {
            ...current,
            chats: current.chats.map((c) => (c.id === changed.id ? changed : c)),
          },
      );
      return `"${chat.title}" now uses ${models?.models.find((m) => m.id === id)?.label ?? id}.`;
    });
  }

  function changePreferred(id: string) {
    void act(async () => {
      const updated = await setPreferredModel(id === models?.default ? null : id);
      setModels(updated);
      return "Saved your default model.";
    });
  }

  function modelOptions(forThisStudent: boolean) {
    return models?.models.map((m) => (
      <option key={m.id} value={m.id} disabled={!modelAllowed(m, forThisStudent)}>
        {m.label}
        {!modelAllowed(m, forThisStudent) && " (not approved for students)"}
      </option>
    ));
  }

  const chosenModel = models?.models.find((m) => m.id === model);

  function remove(chat: StudentChat) {
    const confirmed = window.confirm(
      `Delete "${chat.title}"? Its messages are deleted too, and ${studentName} can't get them back.`,
    );
    if (!confirmed) return;
    void act(async () => {
      await deleteStudentChat(studentId, chat.id);
      setChats(
        (current) =>
          current && {
            ...current,
            chats: current.chats.filter((c) => c.id !== chat.id),
          },
      );
      return `Deleted "${chat.title}".`;
    });
  }

  if (students === null) {
    return (
      <div className="centred">
        {error ? (
          <div className="notice" role="alert">
            {error}
          </div>
        ) : (
          <PageSkeleton />
        )}
      </div>
    );
  }

  return (
    <section className="admin-page">
      <h1>Lessons</h1>
      <p className="muted">
        Set up a chat for each lesson. Prof AI teaches from the lesson material you add, and your
        student picks the chat from their list.
      </p>

      <div className="invite-fields lesson-student">
        <label>
          Student
          <select
            value={studentId}
            onChange={(e) => {
              setChats(null);
              setStudentId(e.target.value);
            }}
          >
            {students.map((s) => (
              <option key={s.id} value={s.id}>
                {s.display_name} ({s.email})
              </option>
            ))}
            <option value={me.id}>Yourself, to try a lesson out</option>
          </select>
        </label>
        {models && (
          <label>
            Your default model
            <select
              value={models.preferred ?? models.default}
              disabled={busy}
              onChange={(e) => changePreferred(e.target.value)}
            >
              {modelOptions(false)}
            </select>
            <span className="muted lesson-hint">
              For your own test chats, and picked first for new lessons when it's allowed.
            </span>
          </label>
        )}
      </div>

      {status && (
        <p className="admin-status" role="status">
          {status}
        </p>
      )}
      {error && (
        <div className="notice" role="alert">
          {error}
        </div>
      )}

      {chats === null ? (
        <PageSkeleton label="Loading chats…" />
      ) : (
        <>
          <h2 className="lesson-heading">
            Chats{" "}
            <span className="muted">
              ({chats.chats.length} of {chats.max_chats})
            </span>
          </h2>
          {chats.chats.length === 0 ? (
            <p className="muted list-empty">No chats yet. Set up the first lesson below.</p>
          ) : (
            <ul className="user-list">
              {chats.chats.map((chat) => (
                <li key={chat.id} className="user-row">
                  <div className="user-main">
                    <span className="user-name">{chat.title}</span>
                    {chat.topics.length > 0 && (
                      <span className="muted user-email">{chat.topics.join(" · ")}</span>
                    )}
                  </div>
                  <div className="user-meta">
                    <span className="muted">
                      {chat.message_count} messages · updated {shortDate(chat.updated_at)}
                    </span>
                    {chat.has_material && (
                      <span className="status-badge material">Material added</span>
                    )}
                  </div>
                  <div className="user-actions">
                    {models && (
                      <select
                        aria-label={`Model for ${chat.title}`}
                        value={chat.model ?? models.default}
                        disabled={busy}
                        onChange={(e) => changeModel(chat, e.target.value)}
                      >
                        {modelOptions(forStudent)}
                      </select>
                    )}
                    {chat.support && (
                      <select
                        aria-label={`Support level for ${chat.title}`}
                        value={chat.support}
                        disabled={busy}
                        onChange={(e) => changeSupport(chat, e.target.value as SupportLevel)}
                      >
                        {SUPPORT_LEVELS.map((level) => (
                          <option key={level.value} value={level.value}>
                            {level.label}
                          </option>
                        ))}
                      </select>
                    )}
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => onOpenChat(studentId, chat.id)}
                    >
                      Open
                    </button>
                    <button
                      type="button"
                      className="danger"
                      disabled={busy}
                      onClick={() => remove(chat)}
                    >
                      Delete
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {full ? (
            <div className="notice">
              {studentName === "you" ? "You have" : `${studentName} has`} {chats.max_chats} chats.
              Delete one to set up a new lesson.
            </div>
          ) : (
            <form className="invite-form lesson-form" onSubmit={create}>
              <h2>New lesson chat</h2>
              <div className="invite-fields">
                <label>
                  Lesson title
                  <input
                    required
                    maxLength={120}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="Ratios"
                  />
                </label>
              </div>
              <label className="lesson-field">
                Topics covered, one per line
                <textarea
                  rows={3}
                  value={topics}
                  onChange={(e) => setTopics(e.target.value)}
                  placeholder={"Simplifying ratios\nSharing in a ratio"}
                />
              </label>
              <label className="lesson-field">
                How much help should Prof AI give?
                <select
                  value={support}
                  onChange={(e) => setSupport(e.target.value as SupportLevel)}
                >
                  {SUPPORT_LEVELS.map((level) => (
                    <option key={level.value} value={level.value}>
                      {level.label}
                    </option>
                  ))}
                </select>
                <span className="muted lesson-hint">
                  {supportLevel(support).hint} It never gives final answers. You can change this
                  later.
                </span>
              </label>
              {models && (
                <label className="lesson-field">
                  Model
                  <select value={model} onChange={(e) => setPickedModel(e.target.value)}>
                    {modelOptions(forStudent)}
                  </select>
                  {chosenModel && (
                    <span className="muted lesson-hint">{modelSummary(chosenModel)}</span>
                  )}
                </label>
              )}
              <label className="lesson-field">
                Notes for Prof AI (what to focus on, what they found hard)
                <textarea
                  rows={3}
                  maxLength={2000}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
              </label>

              <div className="lesson-field">
                <span>Lesson material</span>
                <p className="muted lesson-hint">
                  Add pages from a PDF of the chapter, then edit the text if you need to.
                </p>
                <div className="signup-link lesson-warning">
                  Leave out answer pages and mark schemes. Students should work answers out
                  themselves.
                </div>
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={choosePdf}
                  disabled={busy}
                />
                {pdf && (
                  <div className="page-pick">
                    <ul>
                      {pdf.pages.map((page) => (
                        <li key={page.number}>
                          <label>
                            <input
                              type="checkbox"
                              checked={picked.has(page.number)}
                              disabled={!page.text}
                              onChange={() => togglePage(page.number)}
                            />
                            <strong>Page {page.number}</strong>{" "}
                            <span className="muted">
                              {page.text
                                ? `${page.tokens.toLocaleString()} tokens · ${page.text.slice(0, 90)}…`
                                : "no text found (a scanned page?)"}
                            </span>
                          </label>
                        </li>
                      ))}
                    </ul>
                    <button
                      type="button"
                      className="secondary"
                      disabled={picked.size === 0}
                      onClick={addPages}
                    >
                      Add {picked.size} selected {picked.size === 1 ? "page" : "pages"}
                    </button>
                  </div>
                )}
                <textarea
                  className="style-editor"
                  rows={10}
                  value={material}
                  onChange={(e) => setMaterial(e.target.value)}
                  aria-label="Lesson material"
                />
              </div>

              <div className="style-actions">
                <span className={overCap ? "byte-count over" : "byte-count muted"}>
                  {tokens.toLocaleString()} of {maxTokens.toLocaleString()} tokens
                  {overCap && ": remove some pages or text"}
                </span>
              </div>
              {material.trim() && (
                <label className="lesson-licence">
                  <input
                    type="checkbox"
                    checked={licensed}
                    onChange={(e) => setLicensed(e.target.checked)}
                  />
                  I'm allowed to use this material with {studentName}: it's my own, or its licence
                  allows it.
                </label>
              )}
              <button type="submit" className="primary" disabled={!canSave}>
                Set up chat
              </button>
            </form>
          )}
        </>
      )}
    </section>
  );
}
