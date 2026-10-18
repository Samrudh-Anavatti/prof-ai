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
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [reply, setReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showList, setShowList] = useState(false);
  const threadEnd = useRef<HTMLDivElement>(null);
  const sending = reply !== null;

  useEffect(() => {
    listConversations()
      .then(setConversations)
      .catch((e: unknown) => setError(messageOf(e)));
  }, []);

  useEffect(() => {
    threadEnd.current?.scrollIntoView({ block: "end" });
  }, [messages, reply]);

  async function openConversation(id: string) {
    setShowList(false);
    setError(null);
    try {
      const detail = await getConversation(id);
      setActiveId(detail.id);
      setMessages(detail.messages);
    } catch (e) {
      setError(messageOf(e));
    }
  }

  function newChat() {
    setShowList(false);
    setActiveId(null);
    setMessages([]);
    setError(null);
  }

  async function send(event?: FormEvent) {
    event?.preventDefault();
    const content = draft.trim();
    if (!content || sending) return;
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
        ...current.filter((c) => c.id !== conversationId),
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

  return (
    <div className="chat-layout">
      <aside className={showList ? "sidebar open" : "sidebar"}>
        <button type="button" className="new-chat" onClick={newChat}>
          + New chat
        </button>
        <ul className="conversation-list">
          {conversations.map((c) => (
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
        <div className="thread" aria-live="polite">
          {messages.length === 0 && reply === null && (
            <div className="empty">
              <h1>Hi {firstName(me)}!</h1>
              <p className="muted">
                What are you working on? Ask about a topic or a question you're stuck on, and we'll
                work through it together.
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
            placeholder="Ask your tutor…"
            aria-label="Message"
          />
          <button type="submit" disabled={sending || !draft.trim()}>
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
