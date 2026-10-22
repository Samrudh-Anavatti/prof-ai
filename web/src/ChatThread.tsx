import { useEffect, useRef, useState, type KeyboardEvent } from "react";

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
import { Composer, type Recipient } from "./Composer";
import { LessonPanel } from "./LessonPanel";
import { Markdown } from "./Markdown";
import { HELP_PROMPTS, messagesForQuestion, nextQuestion } from "./progress";

export type { Recipient } from "./Composer";

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

/** Who the composer can send to, the default first. One choice means no toggle. */
export function recipients(shared: boolean, solving: boolean, viewer: Author): Recipient[] {
  if (!shared) return ["ai"];
  if (!solving) return ["student", "ai"];
  return viewer === "student" ? ["ai", "tutor"] : ["ai"];
}

/** What to send so the message reaches the chosen recipient, as chat.service.asks_ai decides. */
export function outgoing(
  recipient: Recipient,
  solving: boolean,
  content: string,
): { content: string; toTutor: boolean } {
  if (recipient === "tutor") return { content, toTutor: true };
  if (recipient === "ai" && !solving) return { content: withMention(content), toTutor: false };
  return { content, toTutor: false };
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

/** A lesson with questions puts them on the left and the chat on the right (a sheet on narrow
 * screens); any other chat is the chat alone. own: the viewer owns this chat, so in a lesson they
 * work the questions, as a student does (a tutor trying a lesson on themselves). */
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
  const thread = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);
  const chatButton = useRef<HTMLButtonElement>(null);
  const [pickedQuestion, setPickedQuestion] = useState<string | null>(null);
  const [showAllQuestions, setShowAllQuestions] = useState(false);
  const [pickedRecipient, setPickedRecipient] = useState<Recipient | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [seen, setSeen] = useState(0);
  const sending = reply !== null;
  const lesson = detail?.lesson ?? null;
  const shared = lesson !== null;
  const questions = lesson?.questions ?? [];
  const hasWorksheet = questions.length > 0 || (lesson?.worked_examples ?? []).length > 0;
  const currentQuestion = questions.some((q) => q.number === pickedQuestion)
    ? pickedQuestion
    : nextQuestion(questions, detail?.progress ?? []);
  const solving = shared && own;

  useEffect(() => {
    endpoints
      .load()
      .then((loaded) => {
        setDetail(loaded);
        setSeen(loaded.messages.length);
      })
      .catch((e: unknown) => setError(messageOf(e)));
  }, [endpoints]);

  useEffect(() => {
    const element = thread.current;
    if (element) element.scrollTop = element.scrollHeight;
  }, [detail?.messages.length, reply, currentQuestion, showAllQuestions, chatOpen]);

  useEffect(() => {
    if (chatOpen) composer.current?.focus();
  }, [chatOpen]);

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

  const allMessages = detail?.messages ?? [];
  const filtering = hasWorksheet && currentQuestion !== null && !showAllQuestions;
  const messages = filtering ? messagesForQuestion(allMessages, currentQuestion) : allMessages;
  const starters = (own || !shared) && !hasWorksheet ? starterPrompts(lesson) : [];
  const recipientOptions = recipients(shared, solving, viewer);
  const recipient =
    pickedRecipient && recipientOptions.includes(pickedRecipient)
      ? pickedRecipient
      : recipientOptions[0];
  // Counted while the chat sheet is closed; on wide screens the chat is always in view.
  const unread = chatOpen ? 0 : allMessages.slice(seen).filter((m) => m.author !== viewer).length;

  function sendDraft() {
    const message = outgoing(recipient, solving || !shared, draft.trim());
    void send(message.content, message.toTutor);
  }

  function askForHelp(text: string) {
    setChatOpen(true);
    void send(text);
  }

  function closeChat() {
    setSeen(allMessages.length);
    setChatOpen(false);
    chatButton.current?.focus();
  }

  function onPaneKeyDown(event: KeyboardEvent<HTMLElement>) {
    if (event.key === "Escape" && chatOpen) closeChat();
  }

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
    <div
      className={hasWorksheet ? "lesson-layout has-workspace" : "lesson-layout"}
      data-chat-open={chatOpen || undefined}
    >
      {lesson && hasWorksheet && (
        <LessonPanel
          lesson={lesson}
          progress={detail?.progress ?? []}
          attempts={detail?.attempts ?? []}
          current={currentQuestion}
          onSelect={setPickedQuestion}
          onStuck={solving ? askForHelp : undefined}
          onCheck={endpoints.check && solving ? checkAnswer : undefined}
          onCheckWorking={endpoints.checkWorking && solving ? checkWorking : undefined}
          busy={sending}
        />
      )}
      <section className="chat-pane" aria-label="Chat" onKeyDown={onPaneKeyDown}>
        {hasWorksheet ? (
          <header className="chat-pane-head">
            <h2 className="chat-pane-title">
              Chat{" "}
              <span className="muted">
                · {filtering ? `question ${currentQuestion}` : "all questions"}
              </span>
            </h2>
            {currentQuestion !== null && (
              <button
                type="button"
                className="link-button"
                onClick={() => setShowAllQuestions(!showAllQuestions)}
              >
                {showAllQuestions ? `Only question ${currentQuestion}` : "Show all questions"}
              </button>
            )}
            <button
              type="button"
              className="chat-pane-close"
              aria-label="Close chat"
              onClick={closeChat}
            >
              ×
            </button>
          </header>
        ) : (
          lesson && (
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
          )
        )}
        <div className="thread" ref={thread} aria-live="polite">
          {!detail && !error && (
            <div className="thread-skeleton" role="status">
              <span className="visually-hidden">Loading the chat…</span>
              <span className="skeleton skeleton-bubble" />
              <span className="skeleton skeleton-bubble mine" />
              <span className="skeleton skeleton-bubble" />
            </div>
          )}
          {detail && hasWorksheet && messages.length === 0 && reply === null && (
            <div className="chat-empty">
              {solving ? (
                <>
                  <p>Stuck on question {currentQuestion}? Ask Prof AI here, or try one of these.</p>
                  {HELP_PROMPTS.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      className="starter"
                      onClick={() => askForHelp(prompt)}
                    >
                      {prompt}
                    </button>
                  ))}
                </>
              ) : (
                <p className="muted">No messages about question {currentQuestion} yet.</p>
              )}
            </div>
          )}
          {detail && !hasWorksheet && allMessages.length === 0 && reply === null && (
            <div className="empty">
              <p className="empty-wave" aria-hidden="true">
                👋
              </p>
              <h1>Hi {firstName(me)}</h1>
              <p className="muted">
                {solving
                  ? `This chat is about ${lesson?.title}. Ask Prof AI anything about this lesson${viewer === "student" ? ", or send a message to your tutor only" : ""}.`
                  : shared
                    ? `This chat is about ${lesson?.title}. Write to your student here, or switch to Prof AI below.`
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
            const mine = m.author === viewer;
            return (
              <div key={index} className={`message ${mine ? "mine" : "theirs"} by-${m.author}`}>
                {!mine && <Avatar name={m.author_name} tone={m.author} />}
                <div className={`bubble ${mine ? "user" : "assistant"} by-${m.author}`}>
                  {!mine && <span className="bubble-author">{m.author_name}</span>}
                  {m.question && !filtering && (
                    <span className="question-tag">Question {m.question}</span>
                  )}
                  {/* Submissions and maths-field working carry $…$ maths; other messages stay plain. */}
                  {m.author === "ai" || m.content.includes("$") ? (
                    <Markdown text={m.content} />
                  ) : (
                    m.content
                  )}
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
        </div>

        {error && (
          <div className="notice" role="alert">
            {error}
          </div>
        )}

        <Composer
          value={draft}
          onChange={setDraft}
          onSend={sendDraft}
          options={recipientOptions}
          recipient={recipient}
          onRecipient={setPickedRecipient}
          ready={detail !== null}
          sending={sending}
          textareaRef={composer}
        />
        <p className="disclaimer">
          {shared && viewer === "student" && "Your tutor can read this chat. "}
          Prof AI can make mistakes. Check important answers with your tutor.
        </p>
      </section>
      {hasWorksheet && (
        <button
          ref={chatButton}
          type="button"
          className="chat-sheet-button"
          aria-expanded={chatOpen}
          onClick={() => setChatOpen(true)}
        >
          {solving ? "Ask Prof AI" : "Chat"}
          {unread > 0 && (
            <span className="unread-badge">
              <span className="visually-hidden">, </span>
              {unread} new
            </span>
          )}
        </button>
      )}
    </div>
  );
}
