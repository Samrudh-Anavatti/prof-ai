import type { Attempt, SupportLevel } from "./api";

export type CheckPlan =
  { kind: "check_working" } | { kind: "submit" } | { kind: "problem"; message: string };

/** What the one check button does: a hint while the answer line is empty, marking once it isn't.
 * An answer with no working goes to the server, which asks for the steps without a model call. */
export function checkPlan(steps: string[], answer: string): CheckPlan {
  if (answer.trim()) return { kind: "submit" };
  if (steps.length === 0) return { kind: "problem", message: "Write a line of working first." };
  return { kind: "check_working" };
}

export function checkLabel(answer: string): string {
  return answer.trim() ? "Submit my answer" : "Check my working";
}

/** The message I'm stuck sends, with the working so far so Prof AI hints at the right step. */
export function stuckMessage(steps: string[]): string {
  if (steps.length === 0) return "I'm stuck. How do I start?";
  const lines = steps.map((step, index) => `${index + 1}. ${step}`).join("\n");
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
