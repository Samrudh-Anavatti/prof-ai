import { describe, expect, it } from "vitest";

import type { ChatMessage } from "./api";
import { asksAi } from "./ChatThread";
import { messagesForQuestion } from "./progress";

function message(author: ChatMessage["author"], content: string, question?: string): ChatMessage {
  return {
    role: author === "ai" ? "assistant" : "user",
    author,
    author_name: author,
    content,
    at: "2026-10-21T09:00:00Z",
    question,
  };
}

describe("who Prof AI answers", () => {
  it("answers a tutor in their own lesson chat without @AI, as the server does", () => {
    expect(asksAi(true, "tutor", "how do I start?", false, "tutor")).toBe(true);
  });

  it("still needs @AI from a tutor in their student's chat", () => {
    expect(asksAi(true, "tutor", "try Q2 next", false, "student")).toBe(false);
    expect(asksAi(true, "tutor", "@AI a hint for Alex", false, "student")).toBe(true);
  });
});

describe("the thread follows the current question", () => {
  const thread = [
    message("tutor", "Welcome to the lesson"),
    message("student", "Stuck on 1", "1"),
    message("ai", "Add the parts first.", "1"),
    message("student", "What about 2?", "2"),
    message("ai", "Find the highest common factor."),
  ];

  it("shows that question's messages and untagged ones", () => {
    expect(messagesForQuestion(thread, "1").map((m) => m.content)).toEqual([
      "Welcome to the lesson",
      "Stuck on 1",
      "Add the parts first.",
    ]);
  });

  it("keeps an untagged Prof AI reply with the message it answers", () => {
    expect(messagesForQuestion(thread, "2").map((m) => m.content)).toEqual([
      "Welcome to the lesson",
      "What about 2?",
      "Find the highest common factor.",
    ]);
  });

  it("shows only untagged messages for a question nobody has asked about", () => {
    expect(messagesForQuestion(thread, "3").map((m) => m.content)).toEqual([
      "Welcome to the lesson",
    ]);
  });
});
