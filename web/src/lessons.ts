import type { ExtractedPage, Lesson, SupportLevel } from "./api";

export const MAX_PDF_BYTES = 10 * 1024 * 1024;

export const SUPPORT_LEVELS: { value: SupportLevel; label: string; hint: string }[] = [
  {
    value: "step_by_step",
    label: "Step by step",
    hint: "New to the topic: a worked example first, then one small step at a time.",
  },
  {
    value: "balanced",
    label: "Balanced",
    hint: "Knows some of it: tries first, gets a hint when stuck.",
  },
  {
    value: "stretch",
    label: "Stretch",
    hint: "Confident: straight to the questions, short hints and harder 'why' questions.",
  },
];

export function supportLevel(level: SupportLevel): (typeof SUPPORT_LEVELS)[number] {
  return SUPPORT_LEVELS.find((l) => l.value === level) ?? SUPPORT_LEVELS[1];
}

/** Mirrors prof_ai.chat.context.estimate_tokens: UTF-8 bytes ÷ 3, rounded up. */
export function estimateTokens(text: string): number {
  return Math.ceil(new TextEncoder().encode(text).length / 3);
}

/** Mirrors validate_lesson's tidying, so the meter counts what the server will save. */
export function tidyLesson(lesson: Lesson): Lesson {
  return {
    ...lesson,
    title: lesson.title.trim(),
    topics: lesson.topics.map((t) => t.trim()).filter(Boolean),
    notes: lesson.notes.trim(),
    material: lesson.material.trim(),
  };
}

/** Mirrors prof_ai.lessons.rules.render_lesson: the text the server measures against the cap. */
export function renderLesson(lesson: Lesson): string {
  const parts = [`### ${lesson.title}`];
  if (lesson.topics.length) parts.push(`Topics: ${lesson.topics.join("; ")}`);
  if (lesson.notes) parts.push(`What the tutor wants this chat to focus on:\n${lesson.notes}`);
  if (lesson.material) parts.push(`Lesson material:\n\n${lesson.material}`);
  return parts.join("\n\n");
}

export function lessonTokens(lesson: Lesson): number {
  return estimateTokens(renderLesson(tidyLesson(lesson)));
}

export function pagesText(pages: ExtractedPage[], selected: ReadonlySet<number>): string {
  return pages
    .filter((p) => selected.has(p.number) && p.text)
    .map((p) => p.text)
    .join("\n\n");
}

export function toBase64(bytes: Uint8Array): string {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}
