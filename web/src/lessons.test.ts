import { describe, expect, it, vi } from "vitest";

import {
  createStudentChat,
  deleteStudentChat,
  extractPdf,
  listStudentChats,
  type ExtractedPage,
  type Lesson,
} from "./api";
import {
  estimateTokens,
  lessonTokens,
  pagesText,
  renderLesson,
  tidyLesson,
  toBase64,
} from "./lessons";

const LESSON: Lesson = {
  title: "Ratios",
  topics: ["Simplifying", "Sharing"],
  notes: "Mixes up order.",
  material: "A ratio compares quantities. £5 ÷ 2",
  sources: [],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("lesson meter", () => {
  it("renders a lesson exactly as the server does", () => {
    // Copied from prof_ai.lessons.rules.render_lesson for the same lesson; the server enforces
    // the cap on this text, so the meter must count the same thing.
    expect(renderLesson(LESSON)).toBe(
      "### Ratios\n\nTopics: Simplifying; Sharing\n\nWhat the tutor wants this chat to focus on:\nMixes up order.\n\nLesson material:\n\nA ratio compares quantities. £5 ÷ 2",
    );
    expect(lessonTokens(LESSON)).toBe(53);
  });

  it("counts UTF-8 bytes like the server", () => {
    expect(estimateTokens("abc")).toBe(1);
    expect(estimateTokens("abcd")).toBe(2);
    expect(estimateTokens("ééé")).toBe(2);
  });

  it("tidies blank topics and whitespace the way the server will", () => {
    const tidy = tidyLesson({ ...LESSON, title: " Ratios ", topics: ["a", " ", " b "] });
    expect(tidy.title).toBe("Ratios");
    expect(tidy.topics).toEqual(["a", "b"]);
  });

  it("joins only the picked pages that have text", () => {
    const pages: ExtractedPage[] = [
      { number: 1, text: "One", tokens: 1 },
      { number: 2, text: "", tokens: 0 },
      { number: 3, text: "Three", tokens: 2 },
    ];
    expect(pagesText(pages, new Set([1, 2, 3]))).toBe("One\n\nThree");
    expect(pagesText(pages, new Set([3]))).toBe("Three");
  });

  it("base64-encodes bytes for the upload", () => {
    expect(toBase64(new TextEncoder().encode("%PDF-1.4"))).toBe("JVBERi0xLjQ=");
  });
});

describe("lesson API", () => {
  it("creates a chat for a student with the lesson and licence flag", async () => {
    const fetchFn = vi.fn<typeof fetch>(async () => jsonResponse(201, { id: "c1" }));
    await createStudentChat("alex id", LESSON, true, { fetchFn });
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/students/alex%20id/chats");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(init?.body as string)).toEqual({ lesson: LESSON, licence_confirmed: true });
  });

  it("lists a student's chats", async () => {
    const body = { chats: [], max_chats: 5, max_lesson_tokens: 12000 };
    const fetchFn = vi.fn<typeof fetch>(async () => jsonResponse(200, body));
    await expect(listStudentChats("alex", { fetchFn })).resolves.toEqual(body);
    expect(fetchFn.mock.calls[0][0]).toBe("/api/students/alex/chats");
  });

  it("deletes a chat and surfaces the five-chat limit", async () => {
    const deleted = vi.fn<typeof fetch>(async () => new Response(null, { status: 204 }));
    await deleteStudentChat("alex", "c/1", { fetchFn: deleted });
    expect(deleted.mock.calls[0][0]).toBe("/api/students/alex/chats/c%2F1");

    const full = vi.fn<typeof fetch>(async () =>
      jsonResponse(409, { detail: "Alex already has 5 chats. Delete one first." }),
    );
    await expect(createStudentChat("alex", LESSON, true, { fetchFn: full })).rejects.toMatchObject({
      status: 409,
      message: "Alex already has 5 chats. Delete one first.",
    });
  });

  it("uploads a PDF as base64 JSON", async () => {
    const fetchFn = vi.fn<typeof fetch>(async () =>
      jsonResponse(200, { pages: [], max_lesson_tokens: 12000 }),
    );
    await extractPdf("chapter.pdf", "JVBERi0xLjQ=", { fetchFn });
    const [path, init] = fetchFn.mock.calls[0];
    expect(path).toBe("/api/lessons/extract");
    expect(JSON.parse(init?.body as string)).toEqual({
      filename: "chapter.pdf",
      pdf_base64: "JVBERi0xLjQ=",
    });
  });
});
