import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { checkWorking, solveQuestions, type LessonOverview } from "./api";
import { LessonPanel } from "./LessonPanel";
import { Markdown } from "./Markdown";
import { progressLabel } from "./progress";
import { stepPreview, typedToLatex } from "./typedMaths";
import { filledSteps } from "./WorkingEditor";

const LESSON: LessonOverview = {
  title: "Simultaneous equations",
  topics: [],
  support: "step_by_step",
  worked_examples: [],
  questions: [{ number: "A1.1", text: "Solve $x + y = 11$, $x - y = 3$." }],
};

function panel(student: boolean, support: LessonOverview["support"] = "step_by_step"): string {
  return renderToStaticMarkup(
    createElement(LessonPanel, {
      lesson: { ...LESSON, support },
      progress: [],
      current: "A1.1",
      onSelect: () => {},
      onHelp: student ? () => {} : undefined,
      onCheck: student
        ? async () => ({ verdict: "correct" as const, correct: true, feedback: "", progress: [] })
        : undefined,
      onCheckWorking: student ? async () => ({ feedback: "", progress: [] }) : undefined,
      busy: false,
    }),
  );
}

describe("typed maths", () => {
  it.each([
    ["x^2 + 3x = 10", "x^{2} + 3x = 10"],
    ["2^(n+1)", "2^{n+1}"],
    ["3x/4 = (2x+1)/3", "\\frac{3x}{4} = \\frac{2x+1}{3}"],
    ["sqrt(10) * sqrt(x+(1))", "\\sqrt{10} \\times  \\sqrt{x+(1)}"],
    ["x <= 5, y != 2", "x \\le  5, y \\ne  2"],
    ["add them: 2x = 14", "\\text{ add them }: 2x = 14"],
    ["area = pi r^2", "\\text{ area } = \\pi  r^{2}"],
    ["20% discount", "20\\% \\text{ discount }"],
  ])("turns %s into LaTeX", (typed, latex) => {
    expect(typedToLatex(typed)).toBe(latex);
  });

  it("typesets every kind of step without KaTeX errors", () => {
    for (const step of ["x^2 + 3x/4 = sqrt(10)", "subtract (1) from (2)", "x = 7, y = 4", "£12"]) {
      const html = renderToStaticMarkup(createElement(Markdown, { text: stepPreview(step) }));
      expect(html).toContain("<math");
      expect(html).not.toContain("katex-error");
    }
  });

  it("passes steps already written as LaTeX straight through", () => {
    expect(stepPreview("$\\frac{1}{2}$")).toBe("$\\frac{1}{2}$");
    expect(filledSteps({ steps: [" x = 1 ", "", "  "], answer: "" })).toEqual(["x = 1"]);
  });
});

describe("the working editor", () => {
  it("asks students for their working and final answer", () => {
    const html = panel(true);
    expect(html).toContain("Your working");
    expect(html).toContain("Step 1: write down what the question gives you");
    expect(html).toContain("Final answer");
    expect(html).toContain("Check my working so far");
    expect(html).toContain("Submit my answer");
    expect(html).toContain("Can you explain the method?");
  });

  it("leaves the first step open for confident students", () => {
    expect(panel(true, "stretch")).not.toContain("write down what the question gives you");
  });

  it("isn't shown to tutors", () => {
    const html = panel(false);
    expect(html).not.toContain("Your working");
    expect(html).not.toContain("Submit my answer");
  });

  it("tells the tutor when a question was marked without a key", () => {
    const progress = {
      number: "A2.5",
      status: "correct" as const,
      attempts: 1,
      help_messages: 0,
      last_verdict: "correct" as const,
      unverified: true,
    };
    expect(progressLabel(progress)).toBe(
      "Correct ✓ · 1 try · 0 help messages · marked without an answer key",
    );
  });
});

describe("show your working API calls", () => {
  it("sends working checks and missing questions in the agreed shapes", async () => {
    const fetchFn = vi.fn<typeof fetch>(async () => new Response("{}"));
    await checkWorking("c1", "A1.1", ["x + y = 11"], { fetchFn });
    await solveQuestions([{ number: "A2.5", text: "Two numbers…" }], { fetchFn });
    const [[workingPath, workingInit], [solvePath, solveInit]] = fetchFn.mock.calls;
    expect(workingPath).toBe("/api/chat/conversations/c1/working");
    expect(workingInit?.body).toBe(JSON.stringify({ question: "A1.1", working: ["x + y = 11"] }));
    expect(solvePath).toBe("/api/lessons/answers");
    expect(solveInit?.body).toBe(
      JSON.stringify({ questions: [{ number: "A2.5", text: "Two numbers…" }] }),
    );
  });
});
