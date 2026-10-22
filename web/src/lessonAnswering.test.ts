import { describe, expect, it } from "vitest";

import { asksAi, outgoing, recipients, type Recipient } from "./ChatThread";

describe("who the composer sends to", () => {
  it("defaults a student in their lesson to Prof AI, with their tutor as the other choice", () => {
    expect(recipients(true, true, "student")).toEqual(["ai", "tutor"]);
  });

  it("gives a tutor in their own lesson Prof AI only", () => {
    expect(recipients(true, true, "tutor")).toEqual(["ai"]);
  });

  it("defaults a tutor in a student's chat to the student, with Prof AI as the other choice", () => {
    expect(recipients(true, false, "tutor")).toEqual(["student", "ai"]);
  });

  it("has no choice in a test chat", () => {
    expect(recipients(false, false, "tutor")).toEqual(["ai"]);
  });
});

describe("each choice reaches the right person", () => {
  function reachesAi(recipient: Recipient, solving: boolean, author: "student" | "tutor") {
    const message = outgoing(recipient, solving, "is it x = -2?");
    const owner = solving ? author : "student";
    return asksAi(true, author, message.content, message.toTutor, owner);
  }

  it("sends a student's message to Prof AI or to their tutor only", () => {
    expect(reachesAi("ai", true, "student")).toBe(true);
    expect(reachesAi("tutor", true, "student")).toBe(false);
    expect(outgoing("tutor", true, "help").toTutor).toBe(true);
  });

  it("asks Prof AI for a tutor in a student's chat only when they choose it", () => {
    expect(reachesAi("student", false, "tutor")).toBe(false);
    expect(reachesAi("ai", false, "tutor")).toBe(true);
    expect(outgoing("ai", false, "@AI a hint").content).toBe("@AI a hint");
  });

  it("answers a tutor in their own lesson without @AI", () => {
    expect(outgoing("ai", true, "how do I start?").content).toBe("how do I start?");
    expect(reachesAi("ai", true, "tutor")).toBe(true);
  });
});
