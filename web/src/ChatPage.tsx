import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  getConversation,
  getConversationVersion,
  listConversations,
  sendMessage,
  startConversation,
  UNAVAILABLE,
  type ConversationSummary,
  type Me,
} from "./api";
import { ChatThread, type ChatEndpoints } from "./ChatThread";

function messageOf(error: unknown): string {
  return error instanceof ApiError ? error.message : UNAVAILABLE;
}

export function ChatPage({ me }: { me: Me }) {
  const isTutor = me.role === "tutor";
  const [conversations, setConversations] = useState<ConversationSummary[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showList, setShowList] = useState(false);

  useEffect(() => {
    listConversations()
      .then((list) => {
        setConversations(list);
        // Students go straight into their latest chat; tutors pick or start a test chat.
        if (!isTutor && list.length > 0) setActiveId(list[0].id);
      })
      .catch((e: unknown) => setError(messageOf(e)));
  }, [isTutor]);

  const endpoints = useMemo<ChatEndpoints | null>(
    () =>
      activeId === null
        ? null
        : {
            load: () => getConversation(activeId),
            version: () => getConversationVersion(activeId),
            send: (content, handlers) => sendMessage(activeId, content, handlers),
          },
    [activeId],
  );

  function open(id: string) {
    setShowList(false);
    setActiveId(id);
  }

  async function newTestChat() {
    setError(null);
    try {
      const chat = await startConversation();
      setConversations((current) => [chat, ...(current ?? [])]);
      open(chat.id);
    } catch (e) {
      setError(messageOf(e));
    }
  }

  function renamed(title: string) {
    setConversations((current) =>
      (current ?? []).map((c) => (c.id === activeId ? { ...c, title } : c)),
    );
  }

  return (
    <div className="chat-layout">
      <aside className={showList ? "sidebar open" : "sidebar"}>
        {isTutor && (
          <button type="button" className="new-chat" onClick={() => void newTestChat()}>
            + New test chat
          </button>
        )}
        <ul className="conversation-list">
          {(conversations ?? []).map((c) => (
            <li key={c.id}>
              <button
                type="button"
                className={c.id === activeId ? "conversation active" : "conversation"}
                onClick={() => open(c.id)}
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
        {endpoints ? (
          <ChatThread key={activeId} me={me} endpoints={endpoints} onTitle={renamed} />
        ) : (
          <div className="thread">
            <div className="empty">
              <h1>Hi {me.display_name.split(" ")[0]}!</h1>
              <p className="muted">
                {conversations === null
                  ? "Loading your chats…"
                  : isTutor
                    ? "Pick a chat, or start a test chat to try your teaching style. Set up chats for your students on the Lessons page."
                    : "Your tutor hasn't set up a chat for you yet. When they do, it'll appear here."}
              </p>
            </div>
          </div>
        )}
        {error && (
          <div className="notice" role="alert">
            {error}
          </div>
        )}
      </section>
    </div>
  );
}
