import { useState } from "react";

import { Markdown } from "./Markdown";
import { StepInput } from "./StepInput";

export const MAX_STEPS = 30;

export interface Draft {
  steps: string[];
  answer: string;
}

export const EMPTY_DRAFT: Draft = { steps: [""], answer: "" };

/** The steps that count: non-empty lines, as the server tidies them. */
export function filledSteps(draft: Draft): string[] {
  return draft.steps.map((s) => s.trim()).filter(Boolean);
}

type Line = number | "answer";

/** A student's working on ruled lines: the line they were given, if any, their own steps, and
 * their answer as the last line. Enter adds a line, Backspace on an empty one removes it, and the
 * arrow keys move between lines. */
export function WorkingEditor({
  draft,
  onChange,
  givenStep,
  firstPlaceholder,
  onSubmit,
}: {
  draft: Draft;
  onChange: (draft: Draft) => void;
  givenStep?: string;
  firstPlaceholder: string;
  onSubmit: () => void;
}) {
  const [focus, setFocus] = useState<{ line: Line; token: number } | null>(null);
  const { steps } = draft;
  const offset = givenStep ? 1 : 0;

  function focusLine(line: Line) {
    setFocus((current) => ({ line, token: (current?.token ?? 0) + 1 }));
  }

  function tokenFor(line: Line): number | undefined {
    return focus?.line === line ? focus.token : undefined;
  }

  function setStep(index: number, value: string) {
    onChange({ ...draft, steps: steps.map((s, i) => (i === index ? value : s)) });
  }

  function addStep(after: number) {
    if (steps.length >= MAX_STEPS) return;
    onChange({ ...draft, steps: [...steps.slice(0, after + 1), "", ...steps.slice(after + 1)] });
    focusLine(after + 1);
  }

  function removeStep(index: number) {
    onChange({ ...draft, steps: steps.filter((_, i) => i !== index) });
    focusLine(Math.max(0, index - 1));
  }

  return (
    <div className="working">
      <ol className="working-lines">
        {givenStep && (
          <li className="working-line given">
            <span className="line-number" aria-hidden="true">
              1
            </span>
            <div className="given-step">
              <span className="visually-hidden">Given first step: </span>
              <Markdown text={givenStep} />
            </div>
            <span className="given-tag">Started for you</span>
          </li>
        )}
        {steps.map((step, index) => (
          <li key={index} className="working-line">
            <span className="line-number" aria-hidden="true">
              {index + offset + 1}
            </span>
            <StepInput
              value={step}
              label={`Step ${index + offset + 1}`}
              placeholder={index === 0 ? firstPlaceholder : undefined}
              focusToken={tokenFor(index)}
              onChange={(value) => setStep(index, value)}
              onEnter={() => addStep(index)}
              onSubmit={onSubmit}
              onRemove={steps.length > 1 ? () => removeStep(index) : undefined}
              onMoveUp={index > 0 ? () => focusLine(index - 1) : undefined}
              onMoveDown={() => focusLine(index + 1 < steps.length ? index + 1 : "answer")}
            />
            {steps.length > 1 && (
              <button
                type="button"
                className="line-remove"
                aria-label={`Remove step ${index + offset + 1}`}
                onClick={() => removeStep(index)}
              >
                ×
              </button>
            )}
          </li>
        ))}
      </ol>
      <button
        type="button"
        className="add-line"
        disabled={steps.length >= MAX_STEPS}
        onClick={() => addStep(steps.length - 1)}
      >
        <span aria-hidden="true">+</span> Add a line
      </button>
      <div className="working-line answer-line">
        <span className="answer-label" aria-hidden="true">
          Answer
        </span>
        <StepInput
          value={draft.answer}
          label="Answer"
          placeholder="Your final answer"
          focusToken={tokenFor("answer")}
          onChange={(answer) => onChange({ ...draft, answer })}
          onEnter={onSubmit}
          onSubmit={onSubmit}
          onMoveUp={() => focusLine(steps.length - 1)}
        />
      </div>
    </div>
  );
}
