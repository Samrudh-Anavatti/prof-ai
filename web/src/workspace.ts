import type { Attempt, SupportLevel } from "./api";

/** What Submit my answer sends: the last line is the answer, and the lines before it the
 * working. null when nothing is written. */
export function submission(lines: string[]): { working: string[]; answer: string } | null {
  if (lines.length === 0) return null;
  return { working: lines.slice(0, -1), answer: lines[lines.length - 1] };
}

/** The message I'm stuck sends, with the working so far so Prof AI hints at the right step.
 * A first step the student was given is line 1, as on their screen. */
export function stuckMessage(steps: string[], given?: string): string {
  if (steps.length === 0) {
    return given
      ? "I'm stuck. How do I carry on from the first step?"
      : "I'm stuck. How do I start?";
  }
  const lines = (given ? [given, ...steps] : steps)
    .map((step, index) => `${index + 1}. ${step}`)
    .join("\n");
  return `I'm stuck. Here's my working so far:\n\n${lines}`;
}

/** The line above the working, and the first empty line's placeholder, for a support level. */
export function workingPrompt(
  support: SupportLevel | undefined,
  given: boolean,
): { hint: string; firstPlaceholder: string } {
  if (support === "stretch") {
    return { hint: "Set out your working however makes sense to you.", firstPlaceholder: "" };
  }
  if (support === "step_by_step") {
    return given
      ? {
          hint: "We've started it for you. Carry on, one step per line.",
          firstPlaceholder: "Next step",
        }
      : {
          hint: "One step per line. Start by writing down what the question gives you.",
          firstPlaceholder: "What the question gives you",
        };
  }
  return { hint: "One step per line.", firstPlaceholder: "Start with what you know" };
}

/** A submitted attempt as Markdown, the way the chat shows a submission: typed steps in code,
 * maths-field steps as maths. */
export function attemptMarkdown(attempt: Pick<Attempt, "working" | "answer">): string {
  const lines = attempt.working.map(
    (step, index) =>
      `${index + 1}. ${step.includes("$") ? step : `\`${step.replace(/`/g, "'")}\``}`,
  );
  return [...lines, "", `**Answer:** ${attempt.answer}`].join("\n");
}
