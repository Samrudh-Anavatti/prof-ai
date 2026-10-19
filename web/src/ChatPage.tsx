import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import {
  ApiError,
  getConversation,
  listConversations,
  sendMessage,
  startConversation,
  UNAVAILABLE,
  type ChatMessage,
  type ConversationSummary,
  type LessonOverview,
  type Me,
} from "./api";

const MAX_INPUT_CHARS = 2000;

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

function firstName(me: Me): string {
  return me.display_name.split(" ")[0] || me.display_name;
}

export function ChatPage({ me }: { me: Me }) {
  const isTutor = me.role === "tutor";
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [lesson, setLesson] = useState<LessonOverview | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showList, setShowList] = useState(false);
  const threadEnd = useRef<HTMLDivElement>(null);
  const sending = reply !== null;
  // Students can only use chats their tutor set up; tutors can start test chats of their own.
  const canSend = activeId !== null || isTutor;

  useEffect(() => {
    listConversations()
      .then(async (list) => {
        setConversations(list);
        if (isTutor || list.length === 0) return;
        const detail = await getConversation(list[0].id);
        setActiveId(detail.id);
        setLesson(detail.lesson);
        setMessages(detail.messages);
      })
      .catch((e: unknown) => setError(messageOf(e)));
  }, [isTutor]);

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ block: "end" });
  }, [messages, reply]);

  async function openConversation(id: string) {
    setShowList(false);
    setError(null);
    try {
      const detail = await getConversation(id);
      setActiveId(detail.id);
      setLesson(detail.lesson);
      setMessages(detail.messages);
    } catch (e) {
      setError(messageOf(e));
    }
  }

  function newChat() {
    setShowList(false);
    setActiveId(null);
    setLesson(null);
    setMessages([]);
    setError(null);
  }

  async function send(event?: FormEvent) {
    event?.preventDefault();
    const content = draft.trim();
    if (!content || sending || !canSend) return;
    setError(null);
    setDraft("");
    setReply("");
    const previous = messages;
    setMessages([...previous, { role: "user", content, at: new Date().toISOString() }]);
    let streamed = "";
    try {
      let id = activeId;
      if (!id) {
        id = (await startConversation()).id;
        setActiveId(id);
      }
      const title = await sendMessage(id, content, {
        onDelta: (text) => {
          streamed += text;
          setReply(streamed);
        },
      });
      const now = new Date().toISOString();
      setMessages((current) => [...current, { role: "assistant", content: streamed, at: now }]);
      const conversationId = id;
      setConversations((current) => [
        { id: conversationId, title, updated_at: now },
        ...(current ?? []).filter((c) => c.id !== conversationId),
      ]);
    } catch (e) {
      setMessages(previous);
      setDraft(content);
      setError(messageOf(e));
    } finally {
      setReply(null);
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  const noChatsYet = !isTutor && conversations !== null && conversations.length === 0;

  return (
    <div className="chat-layout">
      <aside className={showList ? "sidebar open" : "sidebar"}>
        {isTutor && (
          <button type="button" className="new-chat" onClick={newChat}>
            + New test chat
          </button>
        )}
        <ul className="conversation-list">
          {(conversations ?? []).map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className={c.id === activeId ? "conversation active" : "conversation"}
                onClick={() => void openConversation(c.id)}
              >
                {c.title || "New chat"}
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <section className="chat">
        <button type="button" className="toggle-list" onClick={() => setShowList(!showList)}>
          {showList ? "Close" : "Your chats"}
        </button>
        {lesson && (
          <header className="lesson-banner">
            <strong>{lesson.title}</strong>
            {lesson.topics.length > 0 && <span className="muted">{lesson.topics.join(" · ")}</span>}
          </header>
        )}
        <div className="thread" aria-live="polite">
          {messages.length === 0 && reply === null && (
            <div className="empty">
              <h1>Hi {firstName(me)}!</h1>
              <p className="muted">
                {noChatsYet
                  ? "Your tutor hasn't set up a chat for you yet. When they do, it'll appear here."
                  : lesson
                    ? `This chat is about ${lesson.title}. What would you like to go over?`
                    : "What are you working on? Ask about a topic or a question you're stuck on, and we'll work through it together."}
              </p>
            </div>
          )}
          {messages.map((m, index) => (
            <div key={index} className={`bubble ${m.role}`}>
              {m.content}
            </div>
          ))}
          {reply !== null && (
            <div className="bubble assistant">
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

        <form className="composer" onSubmit={(e) => void send(e)}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={onKeyDown}
            maxLength={MAX_INPUT_CHARS}
            rows={2}
            placeholder={canSend ? "Ask your tutor…" : "Pick a chat to start"}
            aria-label="Message"
            disabled={!canSend}
          />
          <button type="submit" disabled={sending || !canSend || !draft.trim()}>
            Send
          </button>
        </form>
        <p className="disclaimer">
          Prof AI can make mistakes. Check important answers with your tutor.
        </p>
      </section>
    </div>
  );
}
