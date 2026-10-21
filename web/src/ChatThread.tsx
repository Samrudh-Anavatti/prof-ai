import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import {
  ApiError,
  UNAVAILABLE,
  type Author,
  type ChatMessage,
  type CheckOutcome,
  type ConversationDetail,
  type ConversationVersion,
  type LessonOverview,
  type Me,
  type ReplyHandlers,
  type SendResult,
  type WorkingOutcome,
} from "./api";
import { Avatar } from "./Avatar";
import { LessonPanel } from "./LessonPanel";
import { Markdown } from "./Markdown";
import { messagesForQuestion, nextQuestion } from "./progress";

const MAX_INPUT_CHARS = 2000;
const POLL_MS = 5000;
// Mirrors the server: a whole-word @AI, so an address like me@ai.example doesn't count.
const AI_MENTION = /(?<![\w@.])@ai\b/i;
const MAX_STARTERS = 3;
const TOPIC_STARTERS = [
  (topic: string) => `Can you explain ${topic} step by step?`,
  (topic: string) => `Give me a practice question on ${topic}.`,
  (topic: string) => `Check my working on ${topic}.`,
];
const GENERAL_STARTERS = [
  "Explain a topic I'm stuck on.",
  "Give me a practice question.",
  "Check my working on a question.",
];

export interface ChatEndpoints {
  load: () => Promise<ConversationDetail>;
  version: () => Promise<ConversationVersion>;
  send: (
    content: string,
    handlers: ReplyHandlers,
    toTutor?: boolean,
    question?: string,
  ) => Promise<SendResult>;
  /** Only in the student's own chat. */
  check?: (question: string, working: string[], answer: string) => Promise<CheckOutcome>;
  checkWorking?: (question: string, working: string[]) => Promise<WorkingOutcome>;
}

/** Mirrors chat.service.asks_ai: in a lesson chat, its owner gets Prof AI by default. */
export function asksAi(
  shared: boolean,
  author: Author,
  content: string,
  toTutor = false,
  ownerAuthor: Author = "student",
): boolean {
  if (!shared || AI_MENTION.test(content)) return true;
  return author === ownerAuthor && !toTutor;
}

export function withMention(content: string): string {
  return AI_MENTION.test(content) ? content : `@AI ${content}`;
}

/** Suggestions that fill a student's composer; Prof AI answers them without @AI. */
export function starterPrompts(lesson: LessonOverview | null): string[] {
  if (!lesson) return GENERAL_STARTERS;
  const topics = lesson.topics.map((t) => t.trim()).filter(Boolean);
  const subjects = topics.length > 0 ? topics : [lesson.title.trim()].filter(Boolean);
  return subjects.slice(0, MAX_STARTERS).map((subject, index) => TOPIC_STARTERS[index](subject));
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

function firstName(me: Me): string {
  return me.display_name.split(" ")[0] || me.display_name;
}

/** own: the viewer owns this chat, so in a lesson they work the questions, as a student does
 * (a tutor trying a lesson on themselves). */
export function ChatThread({
  me,
  endpoints,
  own = false,
  onTitle,
}: {
  me: Me;
  endpoints: ChatEndpoints;
  own?: boolean;
  onTitle?: (title: string) => void;
}) {
  const viewer: Author = me.role === "tutor" ? "tutor" : "student";
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [draft, setDraft] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const threadEnd = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const [pickedQuestion, setPickedQuestion] = useState<string | null>(null);
  const [showAllQuestions, setShowAllQuestions] = useState(false);
  const sending = reply !== null;
  const shared = detail?.lesson != null;
  const questions = detail?.lesson?.questions ?? [];
  const hasWorksheet = questions.length > 0 || (detail?.lesson?.worked_examples ?? []).length > 0;
  const currentQuestion = questions.some((q) => q.number === pickedQuestion)
    ? pickedQuestion
    : nextQuestion(questions, detail?.progress ?? []);

  useEffect(() => {
    endpoints
      .load()
      .then(setDetail)
      .catch((e: unknown) => setError(messageOf(e)));
  }, [endpoints]);

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ block: "end" });
  }, [detail?.messages.length, reply, currentQuestion, showAllQuestions]);

  const knownVersion = detail?.updated_at;
  useEffect(() => {
    if (!knownVersion || sending) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      endpoints
        .version()
        .then(async (version) => {
          if (version.updated_at !== knownVersion) setDetail(await endpoints.load());
        })
        .catch(() => undefined);
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [endpoints, knownVersion, sending]);

  async function send(content: string, toTutor = false) {
    if (!detail || !content || sending) return;
    const question = currentQuestion ?? undefined;
    setError(null);
    setDraft("");
    const before = detail;
    const mine: ChatMessage = {
      role: "user",
      author: viewer,
      author_name: me.display_name,
      content,
      at: new Date().toISOString(),
      question,
    };
    setDetail({ ...before, messages: [...before.messages, mine] });
    setReply(asksAi(shared, viewer, content, toTutor, own ? viewer : "student") ? "" : null);
    let streamed = "";
    try {
      const result = await endpoints.send(
        content,
        {
          onDelta: (text) => {
            streamed += text;
            setReply(streamed);
          },
        },
        toTutor,
        question,
      );
      onTitle?.(result.title);
      setDetail(await endpoints.load());
    } catch (e) {
      setDetail(before);
      setDraft(content);
      setError(messageOf(e));
    } finally {
      setReply(null);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void send(draft.trim());
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(draft.trim());
    }
  }

  const allMessages = detail?.messages ?? [];
  const filtering = currentQuestion !== null && !showAllQuestions;
  const messages = filtering ? messagesForQuestion(allMessages, currentQuestion) : allMessages;
  const lesson = detail?.lesson ?? null;
  const solving = shared && own;
  const starters = (own || !shared) && !hasWorksheet ? starterPrompts(lesson) : [];

  async function checkAnswer(
    question: string,
    working: string[],
    answer: string,
  ): Promise<CheckOutcome> {
    if (!endpoints.check) throw new Error("Checking isn't available here.");
    const outcome = await endpoints.check(question, working, answer);
    setDetail(await endpoints.load());
    return outcome;
  }

  async function checkWorking(question: string, working: string[]): Promise<WorkingOutcome> {
    if (!endpoints.checkWorking) throw new Error("Checking isn't available here.");
    const outcome = await endpoints.checkWorking(question, working);
    setDetail(await endpoints.load());
    return outcome;
  }

  function pickStarter(text: string) {
    setDraft(text);
    composer.current?.focus();
  }

  return (
    <>
      {lesson && (
        <header className="lesson-banner">
          <span className="lesson-kicker">Lesson</span>
          <strong className="lesson-title">{lesson.title}</strong>
          {lesson.topics.length > 0 && (
            <ul className="topic-chips" aria-label="Topics">
              {lesson.topics.map((topic) => (
                <li key={topic}>{topic}</li>
              ))}
            </ul>
          )}
        </header>
      )}
      {lesson && hasWorksheet && (
        <LessonPanel
          lesson={lesson}
          progress={detail?.progress ?? []}
          current={currentQuestion}
          onSelect={setPickedQuestion}
          onHelp={solving ? (text) => void send(text) : undefined}
          onCheck={endpoints.check && solving ? checkAnswer : undefined}
          onCheckWorking={endpoints.checkWorking && solving ? checkWorking : undefined}
          busy={sending}
        />
      )}
      <div className="thread" aria-live="polite">
        {currentQuestion !== null && allMessages.length > 0 && (
          <div className="thread-filter">
            <span className="muted">
              {showAllQuestions
                ? "Showing every question's messages"
                : `Showing messages about question ${currentQuestion}`}
            </span>
            <button
              type="button"
              className="secondary"
              onClick={() => setShowAllQuestions(!showAllQuestions)}
            >
              {showAllQuestions ? `Only question ${currentQuestion}` : "Show all questions"}
            </button>
          </div>
        )}
        {!detail && !error && (
          <div className="thread-skeleton" role="status">
            <span className="visually-hidden">Loading the chat…</span>
            <span className="skeleton skeleton-bubble" />
            <span className="skeleton skeleton-bubble mine" />
            <span className="skeleton skeleton-bubble" />
          </div>
        )}
        {filtering && allMessages.length > 0 && messages.length === 0 && reply === null && (
          <p className="muted thread-filter-empty">No messages about this question yet.</p>
        )}
        {detail && allMessages.length === 0 && reply === null && (
          <div className="empty">
            <p className="empty-wave" aria-hidden="true">
              👋
            </p>
            <h1>Hi {firstName(me)}</h1>
            <p className="muted">
              {solving && hasWorksheet
                ? "Try the question above. When you're stuck, use a help button or ask Prof AI here."
                : solving
                  ? `This chat is about ${lesson?.title}. Ask Prof AI anything about this lesson${viewer === "student" ? ", or send a message to your tutor only" : ""}.`
                  : shared
                    ? `This chat is about ${lesson?.title}. Write to your student here, or start with @AI to ask Prof AI.`
                    : "What are you working on? Ask about a topic or a question you're stuck on, and we'll work through it together."}
            </p>
            {starters.length > 0 && (
              <div className="starters">
                <p className="starters-label">Not sure where to start? Try one:</p>
                {starters.map((text) => (
                  <button
                    key={text}
                    type="button"
                    className="starter"
                    onClick={() => pickStarter(text)}
                  >
                    {text}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
        {messages.map((m, index) => {
          const own = m.author === viewer;
          return (
            <div key={index} className={`message ${own ? "mine" : "theirs"} by-${m.author}`}>
              {!own && <Avatar name={m.author_name} tone={m.author} />}
              <div className={`bubble ${own ? "user" : "assistant"} by-${m.author}`}>
                {!own && <span className="bubble-author">{m.author_name}</span>}
                {m.question && <span className="question-tag">Question {m.question}</span>}
                {m.author === "ai" ? <Markdown text={m.content} /> : m.content}
              </div>
            </div>
          );
        })}
        {reply !== null && (
          <div className="message theirs by-ai">
            <Avatar name="Prof AI" tone="ai" />
            <div className="bubble assistant by-ai">
              <span className="bubble-author">Prof AI</span>
              {reply ? (
                <Markdown text={reply} />
              ) : (
                <span className="typing">
                  <span className="visually-hidden">Prof AI is thinking…</span>
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                  <span className="typing-dot" />
                </span>
              )}
            </div>
          </div>
        )}
        <div ref={threadEnd} />
      </div>

      {error && (
        <div className="notice" role="alert">
          {error}
        </div>
      )}

      <form className="composer" onSubmit={submit}>
        <textarea
          ref={composer}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          maxLength={MAX_INPUT_CHARS}
          rows={2}
          placeholder={
            shared && !solving
              ? "Write a message, or start with @AI to ask Prof AI…"
              : "Ask Prof AI…"
          }
          aria-label="Message"
          disabled={!detail}
        />
        <div className="composer-actions">
          <button type="submit" disabled={sending || !detail || !draft.trim()}>
            {solving ? "Ask Prof AI" : "Send"}
          </button>
          {solving && viewer === "student" && (
            <button
              type="button"
              className="secondary"
              disabled={sending || !draft.trim()}
              onClick={() => void send(draft.trim(), true)}
            >
              Send to tutor only
            </button>
          )}
          {shared && !solving && (
            <button
              type="button"
              className="ask-ai"
              disabled={sending || !draft.trim()}
              onClick={() => void send(withMention(draft.trim()))}
            >
              Ask Prof AI
            </button>
          )}
        </div>
      </form>
      <p className="disclaimer">
        {shared && viewer === "student" && "Your tutor can read this chat. "}
        Prof AI can make mistakes. Check important answers with your tutor.
      </p>
    </>
  );
}
