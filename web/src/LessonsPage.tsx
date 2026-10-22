import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

import {
  ApiError,
  changeStudentChatModel,
  changeStudentChatSupport,
  createStudentChat,
  deleteStudentChat,
  draftFirstSteps,
  draftLesson,
  extractPdf,
  extractWorksheet,
  listModels,
  listStudentChats,
  listUsers,
  setPreferredModel,
  solveQuestions,
  UNAVAILABLE,
  type ExtractedPage,
  type LessonSource,
  type Me,
  type ModelList,
  type Question,
  type StudentChat,
  type StudentChats,
  type SupportLevel,
  type UserView,
  type WorkedExample,
} from "./api";
import { DescribeLesson } from "./DescribeLesson";
import { PageSkeleton } from "./Skeleton";
import {
  applyDraft,
  initialModel,
  lessonTokens,
  MAX_PDF_BYTES,
  modelAllowed,
  modelSummary,
  pagesText,
  SUPPORT_LEVELS,
  supportLevel,
  toBase64,
  type DraftField,
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
  const [workedExamples, setWorkedExamples] = useState<WorkedExample[]>([]);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [models, setModels] = useState<ModelList | null>(null);
  const [pickedModel, setPickedModel] = useState<string | null>(null);
  const [licensed, setLicensed] = useState(false);
  const [pdf, setPdf] = useState<UploadedPdf | null>(null);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const [describing, setDescribing] = useState(false);
  const [description, setDescription] = useState("");
  const [unanswered, setUnanswered] = useState<string[] | null>(null);
  const [unfilled, setUnfilled] = useState<DraftField[]>([]);
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

  const lesson = {
    title,
    topics: topics.split("\n"),
    notes,
    material,
    sources,
    support,
    worked_examples: workedExamples,
    questions,
  };
  const hasContent = material.trim() !== "" || workedExamples.length > 0 || questions.length > 0;
  const tokens = lessonTokens(lesson);
  const maxTokens = chats?.max_lesson_tokens ?? 0;
  const overCap = chats !== null && tokens > maxTokens;
  const full = chats !== null && chats.chats.length >= chats.max_chats;
  const studentName =
    studentId === me.id
      ? "you"
      : (students?.find((s) => s.id === studentId)?.display_name ?? "this student");
  const missingAnswers = questions.filter((q) => q.text.trim() && !(q.answer ?? "").trim());
  const toReview = questions.filter((q) => q.answer_needs_review && (q.answer ?? "").trim());
  const missingFirstSteps = questions.filter((q) => q.text.trim() && !(q.first_step ?? "").trim());
  const stepsToReview = questions.filter(
    (q) => q.first_step_needs_review && (q.first_step ?? "").trim(),
  );
  const canSave =
    !busy &&
    chats !== null &&
    !full &&
    title.trim() !== "" &&
    !overCap &&
    toReview.length === 0 &&
    stepsToReview.length === 0 &&
    (!hasContent || licensed);

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
    setWorkedExamples([]);
    setQuestions([]);
    setPickedModel(null);
    setLicensed(false);
    setPdf(null);
    setPicked(new Set());
    setDescribing(false);
    setDescription("");
    setUnanswered(null);
    setUnfilled([]);
  }

  function filled(field: DraftField) {
    setUnfilled((current) => current.filter((f) => f !== field));
  }

  function fieldClass(field: DraftField, base = ""): string | undefined {
    return [base, unfilled.includes(field) && "needs-input"].filter(Boolean).join(" ") || undefined;
  }

  function notInDescription(field: DraftField) {
    return (
      unfilled.includes(field) && (
        <span className="needs-input-hint">Not in your description: add it here.</span>
      )
    );
  }

  function draft() {
    void act(async () => {
      const drafted = await draftLesson(description);
      const applied = applyDraft({ title, topics, notes, support }, drafted);
      setTitle(applied.fields.title);
      setTopics(applied.fields.topics);
      setNotes(applied.fields.notes);
      setSupport(applied.fields.support);
      setUnfilled(applied.unfilled);
      setUnanswered(drafted.unanswered);
      return "Drafted from your description. Check the fields below before setting up the chat.";
    });
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

  function extractPages() {
    if (!pdf) return;
    const text = pagesText(pdf.pages, picked);
    const source = { filename: pdf.filename, pages: [...picked].sort((a, b) => a - b) };
    void act(async () => {
      const worksheet = await extractWorksheet(text);
      setWorkedExamples((current) => [...current, ...worksheet.worked_examples]);
      setQuestions((current) => [...current, ...worksheet.questions]);
      if (!title.trim()) setTitle(worksheet.title);
      if (!topics.trim()) setTopics(worksheet.topics.join("\n"));
      setSources((current) => [...current, source]);
      setPdf(null);
      setPicked(new Set());
      return (
        `Found ${worksheet.questions.length} questions and ` +
        `${worksheet.worked_examples.length} worked examples in ${source.filename}. ` +
        "Check them below before saving."
      );
    });
  }

  function changeQuestion(index: number, change: Partial<Question>) {
    setQuestions((current) => current.map((q, i) => (i === index ? { ...q, ...change } : q)));
  }

  function workOutAnswers() {
    void act(async () => {
      const { answers } = await solveQuestions(
        missingAnswers.map((q) => ({ number: q.number, text: q.text })),
      );
      const solved = new Map(answers.filter((a) => a.answer).map((a) => [a.number, a.answer]));
      setQuestions((current) =>
        current.map((q) => {
          const answer = solved.get(q.number);
          return answer && !(q.answer ?? "").trim()
            ? { ...q, answer, answer_needs_review: true }
            : q;
        }),
      );
      const missed = missingAnswers.length - solved.size;
      return (
        `Prof AI worked out ${solved.size} ${solved.size === 1 ? "answer" : "answers"}. ` +
        "Check each one marked below before saving." +
        (missed > 0 ? ` ${missed} still need an answer from you.` : "")
      );
    });
  }

  function draftSteps() {
    void act(async () => {
      const { first_steps } = await draftFirstSteps(
        missingFirstSteps.map((q) => ({ number: q.number, text: q.text, answer: q.answer })),
      );
      const drafted = new Map(
        first_steps.filter((s) => s.first_step).map((s) => [s.number, s.first_step]),
      );
      setQuestions((current) =>
        current.map((q) => {
          const step = drafted.get(q.number);
          return step && !(q.first_step ?? "").trim()
            ? { ...q, first_step: step, first_step_needs_review: true }
            : q;
        }),
      );
      const missed = missingFirstSteps.length - drafted.size;
      return (
        `Prof AI drafted ${drafted.size} first ${drafted.size === 1 ? "step" : "steps"}. ` +
        "Check each one marked below before saving." +
        (missed > 0
          ? ` ${missed} ${missed === 1 ? "question has" : "questions have"} none: a first step ` +
            "would give the answer away, or Prof AI wasn't sure."
          : "")
      );
    });
  }

  function changeExample(index: number, change: Partial<WorkedExample>) {
    setWorkedExamples((current) => current.map((e, i) => (i === index ? { ...e, ...change } : e)));
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
                <li key={chat.id} className="user-row lesson-row">
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
              <div className="lesson-form-head">
                <h2>New lesson chat</h2>
                <button
                  type="button"
                  className="secondary"
                  aria-expanded={describing}
                  onClick={() => setDescribing((open) => !open)}
                >
                  Describe it instead
                </button>
              </div>
              {describing && (
                <DescribeLesson
                  description={description}
                  onChange={setDescription}
                  unanswered={unanswered}
                  busy={busy}
                  onDraft={draft}
                  onClose={() => setDescribing(false)}
                />
              )}
              <div className="invite-fields">
                <label className={fieldClass("title")}>
                  Lesson title
                  <input
                    required
                    maxLength={120}
                    value={title}
                    onChange={(e) => {
                      setTitle(e.target.value);
                      filled("title");
                    }}
                    placeholder="Ratios"
                  />
                  {notInDescription("title")}
                </label>
              </div>
              <label className={fieldClass("topics", "lesson-field")}>
                Topics covered, one per line
                <textarea
                  rows={3}
                  value={topics}
                  onChange={(e) => {
                    setTopics(e.target.value);
                    filled("topics");
                  }}
                  placeholder={"Simplifying ratios\nSharing in a ratio"}
                />
                {notInDescription("topics")}
              </label>
              <label className={fieldClass("support", "lesson-field")}>
                How much help should Prof AI give?
                <select
                  value={support}
                  onChange={(e) => {
                    setSupport(e.target.value as SupportLevel);
                    filled("support");
                  }}
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
                {notInDescription("support")}
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
              <label className={fieldClass("notes", "lesson-field")}>
                Notes for Prof AI (what to focus on, what they found hard)
                <textarea
                  rows={3}
                  maxLength={2000}
                  value={notes}
                  onChange={(e) => {
                    setNotes(e.target.value);
                    filled("notes");
                  }}
                />
                {notInDescription("notes")}
              </label>

              <div className="lesson-field">
                <span>Lesson material</span>
                <p className="muted lesson-hint">
                  Add pages from a PDF of the chapter, then edit the text if you need to.
                </p>
                <div className="signup-link lesson-warning">
                  Adding pages as text? Leave out answer pages and mark schemes. Extracting
                  questions keeps answers separate: Prof AI only uses them to check a student&apos;s
                  answer, and students never see them.
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
                    <div className="page-pick-actions">
                      <button
                        type="button"
                        className="primary"
                        disabled={picked.size === 0 || busy}
                        onClick={extractPages}
                      >
                        Extract questions and examples
                      </button>
                      <button
                        type="button"
                        className="secondary"
                        disabled={picked.size === 0 || busy}
                        onClick={addPages}
                      >
                        Add {picked.size} {picked.size === 1 ? "page" : "pages"} as text
                      </button>
                    </div>
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

              {workedExamples.length > 0 && (
                <div className="lesson-field worksheet-review">
                  <span>Worked examples ({workedExamples.length})</span>
                  {workedExamples.map((example, index) => (
                    <div key={index} className="review-item">
                      <div className="review-row">
                        <input
                          aria-label={`Worked example ${index + 1} title`}
                          value={example.title}
                          onChange={(e) => changeExample(index, { title: e.target.value })}
                        />
                        <button
                          type="button"
                          className="danger"
                          onClick={() =>
                            setWorkedExamples((current) => current.filter((_, i) => i !== index))
                          }
                        >
                          Remove
                        </button>
                      </div>
                      <textarea
                        rows={6}
                        aria-label={`Worked example ${index + 1}`}
                        value={example.text}
                        onChange={(e) => changeExample(index, { text: e.target.value })}
                      />
                    </div>
                  ))}
                </div>
              )}

              <div className="lesson-field worksheet-review">
                <span>Questions ({questions.length})</span>
                <p className="muted lesson-hint">
                  Extract them from a worksheet above, or add them by hand. Answers are only for
                  checking students&apos; working: students never see them.
                </p>
                {(missingAnswers.length > 0 || missingFirstSteps.length > 0) && (
                  <div className="page-pick-actions">
                    {missingAnswers.length > 0 && (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={workOutAnswers}
                      >
                        Work out missing answers ({missingAnswers.length})
                      </button>
                    )}
                    {missingFirstSteps.length > 0 && (
                      <button
                        type="button"
                        className="secondary"
                        disabled={busy}
                        onClick={draftSteps}
                      >
                        Draft first steps ({missingFirstSteps.length})
                      </button>
                    )}
                  </div>
                )}
                {questions.map((question, index) => (
                  <div key={index} className="review-item">
                    <div className="review-row">
                      <input
                        className="question-number"
                        aria-label={`Question ${index + 1} number`}
                        value={question.number}
                        onChange={(e) => changeQuestion(index, { number: e.target.value })}
                      />
                      <input
                        aria-label={`Question ${index + 1} answer`}
                        placeholder="Answer (optional)"
                        value={question.answer ?? ""}
                        onChange={(e) =>
                          changeQuestion(index, {
                            answer: e.target.value,
                            answer_needs_review: false,
                          })
                        }
                      />
                      <button
                        type="button"
                        className="danger"
                        onClick={() =>
                          setQuestions((current) => current.filter((_, i) => i !== index))
                        }
                      >
                        Remove
                      </button>
                    </div>
                    <textarea
                      rows={3}
                      aria-label={`Question ${index + 1}`}
                      value={question.text}
                      onChange={(e) => changeQuestion(index, { text: e.target.value })}
                    />
                    {question.answer_needs_review && (
                      <div className="answer-review">
                        <span className="status-badge ai-answer">Worked out by Prof AI</span>
                        <span className="muted">Check it against the question.</span>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => changeQuestion(index, { answer_needs_review: false })}
                        >
                          Looks right
                        </button>
                      </div>
                    )}
                    <label className="first-step-field">
                      <span>First step (shown at Step by step)</span>
                      <input
                        aria-label={`Question ${index + 1} first step`}
                        maxLength={300}
                        placeholder="Optional: the first line of working, never the answer"
                        value={question.first_step ?? ""}
                        onChange={(e) =>
                          changeQuestion(index, {
                            first_step: e.target.value,
                            first_step_needs_review: false,
                          })
                        }
                      />
                    </label>
                    {question.first_step_needs_review && (
                      <div className="answer-review">
                        <span className="status-badge ai-answer">Drafted by Prof AI</span>
                        <span className="muted">Check it doesn&apos;t give the answer away.</span>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() => changeQuestion(index, { first_step_needs_review: false })}
                        >
                          Looks right
                        </button>
                      </div>
                    )}
                  </div>
                ))}
                <button
                  type="button"
                  className="secondary"
                  onClick={() =>
                    setQuestions((current) => [
                      ...current,
                      { number: String(current.length + 1), text: "", answer: null },
                    ])
                  }
                >
                  Add a question
                </button>
              </div>

              <div className="style-actions">
                <span className={overCap ? "byte-count over" : "byte-count muted"}>
                  {tokens.toLocaleString()} of {maxTokens.toLocaleString()} tokens
                  {overCap && ": remove some pages or text"}
                </span>
              </div>
              {hasContent && (
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
              {toReview.length > 0 && (
                <p className="lesson-hint needs-input-hint">
                  Check the {toReview.length === 1 ? "answer" : "answers"} Prof AI worked out before
                  setting up the chat.
                </p>
              )}
              {stepsToReview.length > 0 && (
                <p className="lesson-hint needs-input-hint">
                  Check the first {stepsToReview.length === 1 ? "step" : "steps"} Prof AI drafted
                  before setting up the chat.
                </p>
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
