import { describe, expect, it, vi } from "vitest";

import { changeStudentChatSupport, sendMessage } from "./api";
import { asksAi, starterPrompts } from "./ChatThread";
import { SUPPORT_LEVELS, supportLevel } from "./lessons";

function sseResponse(...events: [string, unknown][]): Response {
  const body = events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
  return new Response(body.join(""), { headers: { "Content-Type": "text/event-stream" } });
}

describe("who asks Prof AI in a lesson chat", () => {
  it("asks for a student's message by default", () => {
    expect(asksAi(true, "student", "how do I start?")).toBe(true);
  });

  it("skips Prof AI for a message to the tutor only, unless it mentions @AI", () => {
    expect(asksAi(true, "student", "see you Thursday", true)).toBe(false);
    expect(asksAi(true, "student", "@AI one more hint", true)).toBe(true);
  });

  it("asks for a tutor only with @AI", () => {
    expect(asksAi(true, "tutor", "try Q4 next")).toBe(false);
    expect(asksAi(true, "tutor", "@AI give Alex a hint")).toBe(true);
  });
});

describe("starter prompts", () => {
  it("don't need @AI in a lesson chat", () => {
    const prompts = starterPrompts({ title: "Ratios", topics: ["Simplifying ratios"] });
    expect(prompts.some((p) => p.includes("@AI"))).toBe(false);
  });
});

describe("support levels", () => {
  it("offers the three levels the server accepts, balanced as the fallback", () => {
    expect(SUPPORT_LEVELS.map((l) => l.value)).toEqual(["step_by_step", "balanced", "stretch"]);
    expect(supportLevel("stretch").label).toBe("Stretch");
  });

  it("changes a chat's level with a PATCH", async () => {
    const chat = { id: "c1", support: "stretch" };
    const fetchFn = vi.fn<typeof fetch>(async () => new Response(JSON.stringify(chat)));
    await changeStudentChatSupport("alex", "c1", "stretch", { fetchFn });
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/students/alex/chats/c1");
    expect(init?.method).toBe("PATCH");
    expect(init?.body).toBe(JSON.stringify({ support: "stretch" }));
  });
});

describe("sending to the tutor only", () => {
  it("adds to_tutor only when asked", async () => {
    const fetchFn = vi.fn<typeof fetch>(async () =>
      sseResponse(["done", { title: "Ratios", ai: false }]),
    );
    await sendMessage("c1", "see you Thursday", { onDelta: () => {} }, { fetchFn }, true);
    await sendMessage("c1", "help", { onDelta: () => {} }, { fetchFn });
    const bodies = fetchFn.mock.calls.map(([, init]) => init?.body);
    expect(bodies).toEqual([
      JSON.stringify({ content: "see you Thursday", to_tutor: true }),
      JSON.stringify({ content: "help" }),
    ]);
  });
});
