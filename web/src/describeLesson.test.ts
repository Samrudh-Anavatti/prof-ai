import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { draftLesson, type LessonDraft } from "./api";
import { DescribeLesson } from "./DescribeLesson";
import { applyDraft, DESCRIBE_CHECKLIST, type LessonFields } from "./lessons";

const EMPTY: LessonFields = { title: "", topics: "", notes: "", support: "balanced" };
const DRAFT: LessonDraft = {
  title: "Simultaneous equations",
  topics: ["Elimination", "Negative coefficients"],
  notes: "Year 9. Gets muddled with negative signs.",
  support: "step_by_step",
  unanswered: ["focus"],
};

function panel(unanswered: string[] | null): string {
  return renderToStaticMarkup(
    createElement(DescribeLesson, {
      description: "Year 9 equations",
      onChange: () => {},
      unanswered,
      busy: false,
      onDraft: () => {},
      onClose: () => {},
    }),
  );
}

describe("describe it instead", () => {
  it("posts the description to the draft endpoint", async () => {
    const fetchFn = vi.fn<typeof fetch>(async () => new Response(JSON.stringify(DRAFT)));
    expect(await draftLesson("Year 9 equations", { fetchFn })).toEqual(DRAFT);
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/lessons/describe");
    expect(init?.method).toBe("POST");
    expect(init?.body).toBe(JSON.stringify({ description: "Year 9 equations" }));
  });

  it("fills the form from a draft", () => {
    expect(applyDraft(EMPTY, DRAFT)).toEqual({
      fields: {
        title: "Simultaneous equations",
        topics: "Elimination\nNegative coefficients",
        notes: "Year 9. Gets muddled with negative signs.",
        support: "step_by_step",
      },
      unfilled: [],
    });
  });

  it("keeps what the tutor typed where the draft is empty, and flags what's still missing", () => {
    const sparse: LessonDraft = {
      title: "",
      topics: [],
      notes: "",
      support: null,
      unanswered: ["level"],
    };
    const typed = { ...EMPTY, title: "Ratios", support: "stretch" as const };
    expect(applyDraft(typed, sparse)).toEqual({
      fields: typed,
      unfilled: ["topics", "notes", "support"],
    });
  });

  it("shows the checklist and marks what the description didn't cover", () => {
    const before = panel(null);
    for (const item of DESCRIBE_CHECKLIST) {
      expect(before).toContain(item.question.replace("'", "&#x27;"));
    }
    expect(before).not.toContain("Not in your description");
    expect(before).toContain("Draft the lesson");

    const after = panel(["support"]);
    expect(after.match(/Not in your description/g)).toHaveLength(1);
    expect(after).toContain('<li class="missed">How much help should they get?');
    expect(after).toContain("Draft it again");
  });

  it("asks about the same checklist items the server knows", () => {
    expect(DESCRIBE_CHECKLIST.map((item) => item.id)).toEqual([
      "level",
      "topic",
      "covered",
      "struggles",
      "support",
      "focus",
    ]);
  });
});
