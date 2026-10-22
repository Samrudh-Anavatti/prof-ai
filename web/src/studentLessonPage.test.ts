import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import {
  checkAnswer,
  sendMessage,
  sendStudentChatMessage,
  type LessonOverview,
  type QuestionProgress,
} from "./api";
import { LessonPanel } from "./LessonPanel";
import { doneCount, nextQuestion, progressLabel } from "./progress";

const QUESTIONS = [
  { number: "A1.1", text: "Solve $x + y = 11$." },
  { number: "A1.2", text: "Solve $2x + y = 13$." },
];

function progress(number: string, status: QuestionProgress["status"], attempts = 0, help = 0) {
  return { number, status, attempts, help_messages: help };
}

function panel(lesson: LessonOverview, student: boolean): string {
  return renderToStaticMarkup(
    createElement(LessonPanel, {
      lesson,
      progress: [progress("A1.1", "correct", 2, 1)],
      current: "A1.2",
      onSelect: () => {},
      onStuck: student ? () => {} : undefined,
      onCheck: student
        ? async () => ({ verdict: "correct" as const, correct: true, feedback: "", progress: [] })
        : undefined,
      busy: false,
    }),
  );
}

describe("question progress", () => {
  it("opens the first question not yet correct", () => {
    expect(nextQuestion(QUESTIONS, [progress("A1.1", "correct")])).toBe("A1.2");
    expect(nextQuestion(QUESTIONS, [])).toBe("A1.1");
    const allDone = [progress("A1.1", "correct"), progress("A1.2", "correct")];
    expect(nextQuestion(QUESTIONS, allDone)).toBe("A1.2");
    expect(nextQuestion([], [])).toBeNull();
  });

  it("describes progress in words", () => {
    expect(progressLabel(undefined)).toBe("Not started");
    expect(progressLabel(progress("A1.1", "working", 1, 3))).toBe("1 try · 3 help messages");
    expect(progressLabel(progress("A1.1", "correct", 2, 1))).toBe(
      "Correct ✓ · 2 tries · 1 help message",
    );
    expect(doneCount([progress("A1.1", "correct"), progress("A1.2", "working")])).toBe(1);
  });
});

describe("the lesson panel", () => {
  const lesson: LessonOverview = {
    title: "Simultaneous equations",
    topics: [],
    support: "step_by_step",
    worked_examples: [{ title: "Elimination", text: "Subtract to remove $y$." }],
    questions: QUESTIONS,
  };

  it("leads with the worked example at step by step and shows the current question", () => {
    const html = panel(lesson, true);
    expect(html).toContain('<details class="worked-examples" open="">');
    expect(html).toContain("Question A1.2");
    expect(html).toContain("1 of 2 done");
    expect(html).toContain('<li class="strip-correct">');
    expect(html).toContain("Check my working");
    expect(html).toContain("I&#x27;m stuck");
  });

  it("folds the worked example away for confident students", () => {
    expect(panel({ ...lesson, support: "stretch" }, true)).toContain(
      '<details class="worked-examples">',
    );
  });

  it("shows tutors progress without help buttons or an answer box", () => {
    const html = panel(lesson, false);
    expect(html).not.toContain("Your working");
    expect(html).not.toContain("Check my working");
    expect(html).not.toContain("I&#x27;m stuck");
    expect(html).toContain("1 of 2 done");
  });
});

describe("lesson page API calls", () => {
  it("tags messages with their question and checks answers", async () => {
    const fetchFn = vi.fn<typeof fetch>(
      async () =>
        new Response('event: done\ndata: {"title": "", "ai": true}\n\n', {
          headers: { "Content-Type": "text/event-stream" },
        }),
    );
    await sendMessage("c1", "hint?", { onDelta: () => {} }, { fetchFn }, false, "A1.2");
    await sendStudentChatMessage(
      "alex",
      "c1",
      "look at A1.2",
      { onDelta: () => {} },
      { fetchFn },
      "A1.2",
    );
    const bodies = fetchFn.mock.calls.map(([, init]) => init?.body);
    expect(bodies).toEqual([
      JSON.stringify({ content: "hint?", question: "A1.2" }),
      JSON.stringify({ content: "look at A1.2", question: "A1.2" }),
    ]);

    const json = vi.fn<typeof fetch>(async () => new Response("{}"));
    await checkAnswer("c1", "A1.2", ["2x = 10"], "x = 5", { fetchFn: json });
    const [path, init] = json.mock.calls[0];
    expect(path).toBe("/api/chat/conversations/c1/check");
    expect(init?.body).toBe(
      JSON.stringify({ question: "A1.2", working: ["2x = 10"], answer: "x = 5" }),
    );
  });
});
