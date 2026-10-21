import type {
  ExtractedPage,
  Lesson,
  LessonDraft,
  ModelList,
  ModelOption,
  SupportLevel,
} from "./api";

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

/** What a good description covers; ids match prof_ai.lessons.describe.CHECKLIST. */
export const DESCRIBE_CHECKLIST: { id: string; question: string }[] = [
  { id: "level", question: "Who is it for? (year group or level)" },
  { id: "topic", question: "What's the topic?" },
  { id: "covered", question: "What have they already covered?" },
  { id: "struggles", question: "What do they find hard?" },
  { id: "support", question: "How much help should they get?" },
  { id: "focus", question: "What should Prof AI focus on or avoid?" },
];

export interface LessonFields {
  title: string;
  /** One per line, as in the form. */
  topics: string;
  notes: string;
  support: SupportLevel;
}

export type DraftField = keyof LessonFields;

/** Fills the form from a draft, keeping any field the draft left empty, and lists those. */
export function applyDraft(
  fields: LessonFields,
  draft: LessonDraft,
): { fields: LessonFields; unfilled: DraftField[] } {
  const next: LessonFields = {
    title: draft.title || fields.title,
    topics: draft.topics.length > 0 ? draft.topics.join("\n") : fields.topics,
    notes: draft.notes || fields.notes,
    support: draft.support ?? fields.support,
  };
  const unfilled: DraftField[] = [];
  if (!next.title.trim()) unfilled.push("title");
  if (!next.topics.trim()) unfilled.push("topics");
  if (!next.notes.trim()) unfilled.push("notes");
  if (draft.support === null) unfilled.push("support");
  return { fields: next, unfilled };
}

/** Mirrors ChatService.check_model: a student's chat needs an approved model. */
export function modelAllowed(model: ModelOption, forStudent: boolean): boolean {
  return !forStudent || model.approved_for_student_conversations;
}

/** The tutor's preferred model if it's allowed here, otherwise the default. */
export function initialModel(list: ModelList, forStudent: boolean): string {
  const preferred = list.models.find((m) => m.id === list.preferred);
  return preferred && modelAllowed(preferred, forStudent) ? preferred.id : list.default;
}

export function modelSummary(model: ModelOption): string {
  const cost =
    model.typical_message_usd < 0.01
      ? `about ${(model.typical_message_usd * 100).toFixed(2)}¢ a message`
      : `about $${model.typical_message_usd.toFixed(3)} a message`;
  return `${cost} · ${model.notes}`;
}

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
    worked_examples: (lesson.worked_examples ?? [])
      .map((e) => ({ title: e.title.trim(), text: e.text.trim() }))
      .filter((e) => e.text),
    questions: (lesson.questions ?? [])
      .map((q) => ({
        number: q.number.trim(),
        text: q.text.trim(),
        answer: q.answer?.trim() || null,
      }))
      .filter((q) => q.text),
  };
}

/** Mirrors prof_ai.lessons.rules.render_lesson: the text the server measures against the cap. */
export function renderLesson(lesson: Lesson): string {
  const parts = [`### ${lesson.title}`];
  if (lesson.topics.length) parts.push(`Topics: ${lesson.topics.join("; ")}`);
  if (lesson.notes) parts.push(`What the tutor wants this chat to focus on:\n${lesson.notes}`);
  if (lesson.material) parts.push(`Lesson material:\n\n${lesson.material}`);
  const examples = lesson.worked_examples ?? [];
  if (examples.length) {
    const text = examples.map((e) => `#### ${e.title || "Example"}\n${e.text}`).join("\n\n");
    parts.push(`Worked examples:\n\n${text}`);
  }
  const questions = lesson.questions ?? [];
  if (questions.length) {
    parts.push(
      `Questions for the student:\n${questions.map((q) => `${q.number}. ${q.text}`).join("\n")}`,
    );
  }
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
