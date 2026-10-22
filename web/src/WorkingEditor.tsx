import { useState } from "react";

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

/** A student's working, one step per line, and their final answer. */
export function WorkingEditor({
  draft,
  onChange,
  firstStepHint,
}: {
  draft: Draft;
  onChange: (draft: Draft) => void;
  firstStepHint: string;
}) {
  const [focusStep, setFocusStep] = useState<number | null>(null);
  const { steps } = draft;

  function setStep(index: number, value: string) {
    onChange({ ...draft, steps: steps.map((s, i) => (i === index ? value : s)) });
  }

  function addStep(after: number) {
    if (steps.length >= MAX_STEPS) return;
    onChange({ ...draft, steps: [...steps.slice(0, after + 1), "", ...steps.slice(after + 1)] });
    setFocusStep(after + 1);
  }

  function removeStep(index: number) {
    const rest = steps.filter((_, i) => i !== index);
    onChange({ ...draft, steps: rest.length > 0 ? rest : [""] });
  }

  return (
    <div className="working-editor">
      <span className="working-label">Your working</span>
      <p className="muted working-hint">
        One step per line, and press Enter for the next. Type <code>^</code> for a power,{" "}
        <code>/</code> for a fraction and <code>sqrt</code> for a root. Type <code>"</code> to write
        words.
      </p>
      <ol className="working-steps">
        {steps.map((step, index) => (
          <li key={index}>
            <span className="step-number" aria-hidden="true">
              {index + 1}.
            </span>
            <StepInput
              value={step}
              label={`Step ${index + 1}`}
              placeholder={index === 0 ? firstStepHint : `Step ${index + 1}`}
              autoFocus={index === focusStep}
              onChange={(value) => setStep(index, value)}
              onEnter={() => addStep(index)}
            />
            {steps.length > 1 && (
              <button
                type="button"
                className="step-remove"
                aria-label={`Remove step ${index + 1}`}
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
        className="secondary step-add"
        disabled={steps.length >= MAX_STEPS}
        onClick={() => addStep(steps.length - 1)}
      >
        Add a step
      </button>
      <div className="final-answer">
        <span className="working-label">Final answer</span>
        <StepInput
          value={draft.answer}
          label="Final answer"
          placeholder="e.g. x = 7, y = 4"
          onChange={(answer) => onChange({ ...draft, answer })}
        />
      </div>
    </div>
  );
}
