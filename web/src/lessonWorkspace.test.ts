import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { draftFirstSteps, type Attempt, type LessonOverview } from "./api";
import { LessonPanel } from "./LessonPanel";
import { studentStatus } from "./progress";
import { lineKey } from "./StepInput";
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
