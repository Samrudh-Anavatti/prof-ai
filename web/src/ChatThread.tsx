import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import {
  ApiError,
  UNAVAILABLE,
  type Author,
  type ChatMessage,
  type ConversationDetail,
  type ConversationVersion,
  type LessonOverview,
  type Me,
  type ReplyHandlers,
  type SendResult,
} from "./api";
import { Avatar } from "./Avatar";

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
  send: (content: string, handlers: ReplyHandlers) => Promise<SendResult>;
}

export function asksAi(shared: boolean, content: string): boolean {
  return !shared || AI_MENTION.test(content);
}

export function withMention(content: string): string {
  return AI_MENTION.test(content) ? content : `@AI ${content}`;
}

/** Suggestions that fill the composer; in a lesson chat they start with @AI so Prof AI replies. */
export function starterPrompts(lesson: LessonOverview | null): string[] {
  if (!lesson) return GENERAL_STARTERS;
  const topics = lesson.topics.map((t) => t.trim()).filter(Boolean);
  const subjects = topics.length > 0 ? topics : [lesson.title.trim()].filter(Boolean);
  return subjects
    .slice(0, MAX_STARTERS)
    .map((subject, index) => withMention(TOPIC_STARTERS[index](subject)));
}

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

function firstName(me: Me): string {
  return me.display_name.split(" ")[0] || me.display_name;
}

export function ChatThread({
  me,
  endpoints,
  onTitle,
}: {
  me: Me;
  endpoints: ChatEndpoints;
  onTitle?: (title: string) => void;
}) {
  const viewer: Author = me.role === "tutor" ? "tutor" : "student";
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [draft, setDraft] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const threadEnd = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const sending = reply !== null;
  const shared = detail?.lesson != null;

  useEffect(() => {
    endpoints
      .load()
      .then(setDetail)
      .catch((e: unknown) => setError(messageOf(e)));
  }, [endpoints]);

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ block: "end" });
  }, [detail?.messages.length, reply]);

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

  async function send(content: string) {
    if (!detail || !content || sending) return;
    setError(null);
    setDraft("");
    const before = detail;
    const mine: ChatMessage = {
      role: "user",
      author: viewer,
      author_name: me.display_name,
      content,
      at: new Date().toISOString(),
    };
    setDetail({ ...before, messages: [...before.messages, mine] });
    setReply(asksAi(shared, content) ? "" : null);
    let streamed = "";
    try {
      const result = await endpoints.send(content, {
        onDelta: (text) => {
          streamed += text;
          setReply(streamed);
        },
      });
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

  const messages = detail?.messages ?? [];
  const lesson = detail?.lesson ?? null;
  const starters = viewer === "student" || !shared ? starterPrompts(lesson) : [];

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
      <div className="thread" aria-live="polite">
        {!detail && !error && (
          <div className="thread-skeleton" role="status">
            <span className="visually-hidden">Loading the chat…</span>
            <span className="skeleton skeleton-bubble" />
            <span className="skeleton skeleton-bubble mine" />
            <span className="skeleton skeleton-bubble" />
          </div>
        )}
        {detail && messages.length === 0 && reply === null && (
          <div className="empty">
            <p className="empty-wave" aria-hidden="true">
              👋
            </p>
            <h1>Hi {firstName(me)}</h1>
            <p className="muted">
              {shared
                ? `This chat is about ${lesson?.title}. Write a message here, or start it with @AI to ask Prof AI.`
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
                {m.content}
              </div>
            </div>
          );
        })}
        {reply !== null && (
          <div className="message theirs by-ai">
            <Avatar name="Prof AI" tone="ai" />
            <div className="bubble assistant by-ai">
              <span className="bubble-author">Prof AI</span>
              {reply || (
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
            shared ? "Write a message, or start with @AI to ask Prof AI…" : "Ask Prof AI…"
          }
          aria-label="Message"
          disabled={!detail}
        />
        <div className="composer-actions">
          <button type="submit" disabled={sending || !detail || !draft.trim()}>
            Send
          </button>
          {shared && (
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
