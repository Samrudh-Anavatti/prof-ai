import { describe, expect, it, vi } from "vitest";

import {
  getConversationVersion,
  getStudentChat,
  getStudentChatVersion,
  sendMessage,
  sendStudentChatMessage,
} from "./api";
import { asksAi, withMention } from "./ChatThread";

function sseResponse(...events: [string, unknown][]): Response {
  const body = events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  return new Response(body.join(""), { headers: { "Content-Type": "text/event-stream" } });
}

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
}

describe("@AI", () => {
  it("matches the server: a whole-word mention, case-insensitive", () => {
    expect(asksAi(true, "tutor", "@AI help")).toBe(true);
    expect(asksAi(true, "tutor", "can you help @ai?")).toBe(true);
    expect(asksAi(true, "tutor", "my email is me@ai.example")).toBe(false);
    expect(asksAi(true, "tutor", "@aid is not a mention")).toBe(false);
    expect(asksAi(true, "tutor", "see you Thursday")).toBe(false);
  });

  it("always asks Prof AI in a chat that isn't shared", () => {
    expect(asksAi(false, "tutor", "see you Thursday")).toBe(true);
  });

  it("adds @AI only when it's missing", () => {
    expect(withMention("what's a ratio?")).toBe("@AI what's a ratio?");
    expect(withMention("@ai what's a ratio?")).toBe("@ai what's a ratio?");
  });
});

describe("shared chat API", () => {
  it("reports a plain message that Prof AI didn't answer", async () => {
    const fetchFn = vi.fn<typeof fetch>(async () =>
      sseResponse(["done", { title: "Ratios", ai: false }]),
    );
    const onDelta = vi.fn();
    await expect(sendMessage("c1", "see you Thursday", { onDelta }, { fetchFn })).resolves.toEqual({
      title: "Ratios",
      ai: false,
    });
    expect(onDelta).not.toHaveBeenCalled();
  });

  it("sends a tutor's message to their student's chat", async () => {
    const fetchFn = vi.fn<typeof fetch>(async () =>
      sseResponse(["done", { title: "Ratios", ai: false }]),
    );
    await sendStudentChatMessage("alex", "c 1", "Try Q4", { onDelta: () => {} }, { fetchFn });
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/students/alex/chats/c%201/messages");
    expect(init?.body).toBe(JSON.stringify({ content: "Try Q4" }));
  });

  it("polls the cheap version endpoints and loads a student's chat", async () => {
    const version = { updated_at: "2026-10-20T09:00:00Z" };
    const fetchFn = vi.fn<typeof fetch>(async () => jsonResponse(version));
    await expect(getConversationVersion("c1", { fetchFn })).resolves.toEqual(version);
    await getStudentChatVersion("alex", "c1", { fetchFn });
    await getStudentChat("alex", "c1", { fetchFn });
    expect(fetchFn.mock.calls.map(([path]) => path)).toEqual([
      "/api/chat/conversations/c1/version",
      "/api/students/alex/chats/c1/version",
      "/api/students/alex/chats/c1",
    ]);
  });
});
