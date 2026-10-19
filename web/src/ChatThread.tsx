import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import {
  ApiError,
  UNAVAILABLE,
  type Author,
  type ChatMessage,
  type ConversationDetail,
  type ConversationVersion,
  type Me,
  type ReplyHandlers,
  type SendResult,
} from "./api";

const MAX_INPUT_CHARS = 2000;
const POLL_MS = 5000;
// Mirrors the server: a whole-word @AI, so an address like me@ai.example doesn't count.
const AI_MENTION = /(?<![\w@.])@ai\b/i;

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
  return (
    <>
      {lesson && (
        <header className="lesson-banner">
          <strong>{lesson.title}</strong>
          {lesson.topics.length > 0 && <span className="muted">{lesson.topics.join(" · ")}</span>}
        </header>
      )}
      <div className="thread" aria-live="polite">
        {detail && messages.length === 0 && reply === null && (
          <div className="empty">
            <h1>Hi {firstName(me)}!</h1>
            <p className="muted">
              {shared
                ? `This chat is about ${lesson?.title}. Write a message here, or start it with @AI to ask Prof AI.`
                : "What are you working on? Ask about a topic or a question you're stuck on, and we'll work through it together."}
            </p>
          </div>
        )}
        {messages.map((m, index) => {
          const own = m.author === viewer;
          return (
            <div key={index} className={`bubble ${own ? "user" : "assistant"} by-${m.author}`}>
              {!own && <span className="bubble-author">{m.author_name}</span>}
              {m.content}
            </div>
          );
        })}
        {reply !== null && (
          <div className="bubble assistant by-ai">
            <span className="bubble-author">Prof AI</span>
            {reply || <span className="typing">Thinking…</span>}
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
