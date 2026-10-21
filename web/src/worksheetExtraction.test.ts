import { describe, expect, it, vi } from "vitest";

import { extractWorksheet, type Lesson } from "./api";
import { renderLesson, tidyLesson } from "./lessons";

const LESSON: Lesson = {
  title: "Simultaneous equations",
  topics: [],
  notes: "",
  material: "",
  sources: [],
  worked_examples: [{ title: "", text: "Subtract to remove $y$." }],
  questions: [
    { number: "A1.1", text: "Solve $x + y = 11$, $x - y = 3$.", answer: "$x=7$, $y=4$" },
    { number: "A1.2", text: "Two numbers sum to 26.", answer: null },
  ],
};

describe("lessons with worksheets", () => {
  it("mirror the server's lesson layer: examples and questions, never answers", () => {
    expect(renderLesson(LESSON)).toBe(
      "### Simultaneous equations\n\n" +
        "Worked examples:\n\n#### Example\nSubtract to remove $y$.\n\n" +
        "Questions for the student:\nA1.1. Solve $x + y = 11$, $x - y = 3$.\nA1.2. Two numbers sum to 26.",
    );
    expect(renderLesson(LESSON)).not.toContain("x=7");
  });

  it("tidy questions the way the server does", () => {
    const tidied = tidyLesson({
      ...LESSON,
      questions: [
        { number: " A3 ", text: " Solve it ", answer: "  " },
        { number: "A4", text: " ", answer: "1" },
      ],
    });
    expect(tidied.questions).toEqual([{ number: "A3", text: "Solve it", answer: null }]);
  });

  it("send the selected pages' text for extraction", async () => {
    const worksheet = { title: "", topics: [], worked_examples: [], questions: [] };
    const fetchFn = vi.fn<typeof fetch>(async () => new Response(JSON.stringify(worksheet)));
    await extractWorksheet("A1. Solve…", { fetchFn });
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/lessons/worksheet");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(JSON.stringify({ text: "A1. Solve…" }));
  });
});
