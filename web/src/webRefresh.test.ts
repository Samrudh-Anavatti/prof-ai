import { describe, expect, it } from "vitest";

import { initials } from "./Avatar";
import { asksAi, starterPrompts } from "./ChatThread";

describe("initials", () => {
  it("uses the first and last word of a name", () => {
    expect(initials("Priya Natarajan")).toBe("PN");
    expect(initials("  ama   kofi  mensah ")).toBe("AM");
  });

  it("uses one letter for a single name", () => {
    expect(initials("Tomasz")).toBe("T");
  });

  it("falls back when the name is empty", () => {
    expect(initials("   ")).toBe("?");
  });
});

describe("starterPrompts", () => {
  const lesson = { title: "Ratios", topics: ["Simplifying ratios", " ", "Sharing in a ratio"] };

  it("asks Prof AI about the lesson's topics in a shared chat", () => {
    const prompts = starterPrompts(lesson);
    expect(prompts).toHaveLength(2);
    expect(prompts[0]).toContain("Simplifying ratios");
    expect(prompts[1]).toContain("Sharing in a ratio");
    expect(prompts.every((p) => asksAi(true, "student", p))).toBe(true);
  });

  it("offers at most three", () => {
    const many = { title: "Algebra", topics: ["a", "b", "c", "d", "e"] };
    expect(starterPrompts(many)).toHaveLength(3);
  });

  it("uses the lesson title when there are no topics", () => {
    const prompts = starterPrompts({ title: "Photosynthesis", topics: [] });
    expect(prompts).toHaveLength(1);
    expect(prompts[0]).toContain("Photosynthesis");
  });

  it("gives general prompts without a mention outside lesson chats", () => {
    const prompts = starterPrompts(null);
    expect(prompts.length).toBeGreaterThan(0);
    expect(prompts.some((p) => p.includes("@AI"))).toBe(false);
  });
});
