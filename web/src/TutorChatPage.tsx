import { useMemo, type MouseEvent } from "react";

import {
  checkAnswer,
  checkWorking,
  getStudentChat,
  getStudentChatVersion,
  sendStudentChatMessage,
  type Me,
} from "./api";
import { ChatThread, type ChatEndpoints } from "./ChatThread";

/** A tutor in one of their students' lesson chats, or in a lesson they set up for themselves. */
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
  const own = studentId === me.id;
  const endpoints = useMemo<ChatEndpoints>(
    () => ({
      load: () => getStudentChat(studentId, chatId),
      version: () => getStudentChatVersion(studentId, chatId),
      send: (content, handlers, _toTutor, question) =>
        sendStudentChatMessage(studentId, chatId, content, handlers, {}, question),
      ...(own && {
        check: (question: string, working: string[], answer: string) =>
          checkAnswer(chatId, question, working, answer),
        checkWorking: (question: string, working: string[]) =>
          checkWorking(chatId, question, working),
      }),
    }),
    [studentId, chatId, own],
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
        <ChatThread me={me} endpoints={endpoints} own={own} />
      </section>
    </div>
  );
}
