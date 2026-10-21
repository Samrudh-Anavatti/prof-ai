import type { QuestionOverview, QuestionProgress } from "./api";

export const HELP_PROMPTS = [
  "What is this question asking?",
  "Give me a hint for the next step.",
  "Can you check my working so far?",
];

export function progressOf(
  progress: QuestionProgress[],
  number: string,
): QuestionProgress | undefined {
  return progress.find((p) => p.number === number);
}

/** The first question not yet answered correctly, or the last one when all are done. */
export function nextQuestion(
  questions: QuestionOverview[],
  progress: QuestionProgress[],
): string | null {
  const open = questions.find((q) => progressOf(progress, q.number)?.status !== "correct");
  return (open ?? questions.at(-1))?.number ?? null;
}

export function progressLabel(progress: QuestionProgress | undefined): string {
  if (!progress || progress.status === "not_started") return "Not started";
  const tries = `${progress.attempts} ${progress.attempts === 1 ? "try" : "tries"}`;
  const help = `${progress.help_messages} help ${progress.help_messages === 1 ? "message" : "messages"}`;
  if (progress.status === "correct") return `Correct ✓ · ${tries} · ${help}`;
  return `${tries} · ${help}`;
}

export function doneCount(progress: QuestionProgress[]): number {
  return progress.filter((p) => p.status === "correct").length;
}
