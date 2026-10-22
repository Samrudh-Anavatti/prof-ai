import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { draftFirstSteps, type Attempt, type LessonOverview } from "./api";
import { LessonPanel } from "./LessonPanel";
import { isWord, MATHS_KEYS, mathsTail } from "./lineModes";
import { studentStatus } from "./progress";
import { lineKey } from "./StepInput";
import { answerOf, filledSteps, WorkingEditor, type Draft } from "./WorkingEditor";
import { attemptMarkdown, checkLabel, checkPlan, stuckMessage, workingPrompt } from "./workspace";

const LESSON: LessonOverview = {
  title: "Quadratics",
  topics: [],
  support: "step_by_step",
  worked_examples: [],
  questions: [
    { number: "1", text: "Solve $x^2 + 5x + 6 = 0$." },
    { number: "2", text: "Solve $x^2 - 9 = 0$." },
  ],
  first_steps: { "1": "$x^2 + 5x + 6 = (x + \\square)(x + \\square)$" },
};

const ATTEMPT: Attempt = {
  question: "1",
  working: ["(x+2)(x+3) = 0", "$x + 2 = 0$"],
  answer: "x = -2 or x = -3",
  verdict: "slip",
  correct: false,
  verified: true,
  at: "2026-10-22T09:00:00Z",
};

function editor(draft: Draft, givenStep?: string): string {
  return renderToStaticMarkup(
    createElement(WorkingEditor, {
      draft,
      onChange: () => {},
      givenStep,
      firstPlaceholder: "",
      onSubmit: () => {},
    }),
  );
}

function panel(
  lesson: LessonOverview,
  { student = true, attempts = [] as Attempt[] } = {},
): string {
  return renderToStaticMarkup(
    createElement(LessonPanel, {
      lesson,
      progress: [],
      attempts,
      current: "1",
      onSelect: () => {},
      onStuck: student ? () => {} : undefined,
      onCheck: student
        ? async () => ({ verdict: "correct" as const, correct: true, feedback: "", progress: [] })
        : undefined,
      onCheckWorking: student ? async () => ({ feedback: "", progress: [] }) : undefined,
      busy: false,
    }),
  );
}

describe("the check button", () => {
  it("hints while the answer line is empty and marks once it isn't", () => {
    expect(checkPlan(["x = 1"], "")).toEqual({ kind: "check_working" });
    expect(checkPlan(["x = 1"], "x = 1")).toEqual({ kind: "submit" });
    expect(checkPlan([], "x = 1")).toEqual({ kind: "submit" });
    expect(checkPlan([], "  ")).toEqual({
      kind: "problem",
      message: "Write a line of working first.",
    });
  });

  it("keeps the Submit my answer label that Prof AI's prompt names", () => {
    expect(checkLabel("")).toBe("Check my working");
    expect(checkLabel(" x = 1 ")).toBe("Submit my answer");
  });
});

describe("I'm stuck", () => {
  it("sends the working so far, or asks how to start", () => {
    expect(stuckMessage([])).toBe("I'm stuck. How do I start?");
    expect(stuckMessage(["x^2 = 9", "x = 3"])).toBe(
      "I'm stuck. Here's my working so far:\n\n1. x^2 = 9\n2. x = 3",
    );
  });

  it("numbers the working as the student sees it, from the given first step", () => {
    expect(stuckMessage([], "$x^2 = 9$")).toBe("I'm stuck. How do I carry on from the first step?");
    expect(stuckMessage(["x = 3"], "$x^2 = 9$")).toBe(
      "I'm stuck. Here's my working so far:\n\n1. $x^2 = 9$\n2. x = 3",
    );
  });
});

describe("working prompts by support level", () => {
  it("fades from a given first step to a blank page", () => {
    expect(workingPrompt("step_by_step", true)).toEqual({
      hint: "We've started it for you. Carry on, one step per line.",
      firstPlaceholder: "Next step",
    });
    expect(workingPrompt("step_by_step", false).firstPlaceholder).toBe(
      "What the question gives you",
    );
    expect(workingPrompt("balanced", false)).toEqual({
      hint: "One step per line.",
      firstPlaceholder: "Start with what you know",
    });
    expect(workingPrompt("stretch", false)).toEqual({
      hint: "Set out your working however makes sense to you.",
      firstPlaceholder: "",
    });
  });
});

describe("what students see of their progress", () => {
  it("shows no counts of tries or help", () => {
    expect(studentStatus(undefined)).toBe("Not started");
    const base = { number: "1", attempts: 3, help_messages: 4 };
    expect(studentStatus({ ...base, status: "not_started" })).toBe("Not started");
    expect(studentStatus({ ...base, status: "working" })).toBe("Started");
    expect(studentStatus({ ...base, status: "correct" })).toBe("Done ✓");
  });
});

describe("keys on a line of working", () => {
  const key = (k: string, mods: { ctrlKey?: boolean; metaKey?: boolean } = {}) => ({
    key: k,
    ctrlKey: false,
    metaKey: false,
    ...mods,
  });

  it("adds, submits and removes lines", () => {
    expect(lineKey(key("Enter"), false)).toBe("next");
    expect(lineKey(key("Enter", { ctrlKey: true }), false)).toBe("submit");
    expect(lineKey(key("Enter", { metaKey: true }), true)).toBe("submit");
    expect(lineKey(key("Backspace"), true)).toBe("remove");
    expect(lineKey(key("Backspace"), false)).toBeNull();
    expect(lineKey(key("a"), true)).toBeNull();
  });
});

describe("the workspace", () => {
  it("starts the working from the given first step at step by step", () => {
    const html = panel(LESSON);
    expect(html).toContain("Started for you");
    expect(html).toContain("Given first step: ");
    expect(html).toContain("We&#x27;ve started it for you.");
    expect(html).toContain('aria-label="Step 2"');
  });

  it("gives no first step at other levels", () => {
    const html = panel({ ...LESSON, support: "balanced", first_steps: undefined });
    expect(html).not.toContain("Started for you");
    expect(html).toContain('aria-label="Step 1"');
    expect(html).toContain('placeholder="Start with what you know"');
  });

  it("shows tutors the student's attempts, newest first, instead of the working", () => {
    const later = {
      ...ATTEMPT,
      verdict: "correct" as const,
      correct: true,
      at: "2026-10-22T10:00:00Z",
    };
    const html = panel(LESSON, { student: false, attempts: [ATTEMPT, later] });
    expect(html).not.toContain("Your working");
    expect(html).toContain("Submitted answers (2)");
    expect(html.indexOf("Correct ✓")).toBeLessThan(html.indexOf("Nearly: check your steps"));
    expect(html).toContain('class="attempt correct"');
    expect(html).toContain('class="attempt not-yet"');
  });

  it("tells tutors when a question has no answers yet", () => {
    const html = panel(LESSON, { student: false, attempts: [{ ...ATTEMPT, question: "2" }] });
    expect(html).toContain("No answers submitted for this question yet.");
  });

  it("writes an attempt the way the chat shows a submission", () => {
    expect(attemptMarkdown(ATTEMPT)).toBe(
      "1. `(x+2)(x+3) = 0`\n2. $x + 2 = 0$\n\n**Answer:** x = -2 or x = -3",
    );
  });
});

describe("drafting first steps", () => {
  it("sends the questions in the agreed shape", async () => {
    const fetchFn = vi.fn<typeof fetch>(async () => new Response('{"first_steps": []}'));
    await draftFirstSteps([{ number: "1", text: "Solve $x^2 = 9$.", answer: "x = ±3" }], {
      fetchFn,
    });
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/lessons/first-steps");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(
      JSON.stringify({ questions: [{ number: "1", text: "Solve $x^2 = 9$.", answer: "x = ±3" }] }),
    );
  });
});

describe("words and maths on a line", () => {
  it("treats words as words, and short letter runs and function names as maths", () => {
    expect(isWord("need")).toBe(true);
    expect(isWord("so")).toBe(true);
    expect(isWord("xy")).toBe(false);
    expect(isWord("x")).toBe(false);
    expect(isWord("sin")).toBe(false);
    expect(isWord("since")).toBe(true);
  });

  it("finds the maths a student typed among words when they type a maths key", () => {
    expect(MATHS_KEYS.has("^")).toBe(true);
    expect(MATHS_KEYS.has("-")).toBe(false);
    expect(mathsTail("so x ")).toEqual({ from: 3, maths: "x" });
    expect(mathsTail("add to 4 and 5")).toEqual({ from: 13, maths: "5" });
    expect(mathsTail("(x")).toEqual({ from: 0, maths: "(x" });
    expect(mathsTail("x - 3 ")).toEqual({ from: 0, maths: "x - 3" });
    expect(mathsTail("sqrt(49)")).toEqual({ from: 0, maths: "sqrt(49)" });
    expect(mathsTail("I need two numbers")).toEqual({ from: 18, maths: "" });
  });
});

describe("marking a line as the answer", () => {
  const draft: Draft = { steps: ["x^2 = 9", " ", "x = 3"], answerLine: 2 };

  it("sends the marked line as the answer and the other lines as working", () => {
    expect(answerOf(draft)).toBe("x = 3");
    expect(filledSteps(draft)).toEqual(["x^2 = 9"]);
    expect(answerOf({ ...draft, answerLine: null })).toBe("");
    expect(filledSteps({ ...draft, answerLine: null })).toEqual(["x^2 = 9", "x = 3"]);
  });

  it("labels the marked line Answer, and every line can be marked", () => {
    const html = editor(draft);
    expect(html).toContain('class="working-line answer-line"');
    expect(html).toContain(">Answer</span>");
    expect(html).toContain('aria-label="Step 3, your answer"');
    expect(html.match(/class="mark-answer"/g)).toHaveLength(3);
    expect(html).toContain('aria-pressed="true" aria-label="Step 3 is my answer"');
  });

  it("never offers the given first step as the answer", () => {
    const html = editor({ steps: [""], answerLine: null }, "$x^2 = 9$");
    expect(html.match(/class="mark-answer"/g)).toHaveLength(1);
    expect(html).toContain('aria-label="Step 2 is my answer"');
  });

  it("tells students they can write words and mark their answer", () => {
    expect(panel(LESSON)).toContain(
      "Write in words or maths, and tick ✓ the line with your answer.",
    );
  });
});
