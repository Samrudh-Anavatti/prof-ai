import { useMemo, type MouseEvent } from "react";

import { getStudentChat, getStudentChatVersion, sendStudentChatMessage, type Me } from "./api";
import { ChatThread, type ChatEndpoints } from "./ChatThread";

/** A tutor in one of their student's lesson chats: they can write, and ask Prof AI with @AI. */
export function TutorChatPage({
  me,
  studentId,
  chatId,
  onBack,
}: {
  me: Me;
  studentId: string;
  chatId: string;
  onBack: () => void;
}) {
  const endpoints = useMemo<ChatEndpoints>(
    () => ({
      load: () => getStudentChat(studentId, chatId),
      version: () => getStudentChatVersion(studentId, chatId),
      send: (content, handlers) => sendStudentChatMessage(studentId, chatId, content, handlers),
    }),
    [studentId, chatId],
  );

  function back(event: MouseEvent<HTMLAnchorElement>) {
    event.preventDefault();
    onBack();
  }

  return (
    <div className="chat-layout single">
      <section className="chat">
        <a className="back-link" href="/lessons" onClick={back}>
          <span aria-hidden="true">←</span> Back to lessons
        </a>
        <ChatThread me={me} endpoints={endpoints} />
      </section>
    </div>
  );
}
