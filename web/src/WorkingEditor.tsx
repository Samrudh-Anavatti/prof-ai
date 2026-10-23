import { useState, type MouseEvent } from "react";

import { Markdown } from "./Markdown";
import { StepInput, type LineMode } from "./StepInput";

export const MAX_STEPS = 30;

export interface Draft {
  steps: string[];
}

export const EMPTY_DRAFT: Draft = { steps: [""] };

/** The lines that count: non-empty ones, as the server tidies them. */
export function filledSteps(draft: Draft): string[] {
  return draft.steps.map((s) => s.trim()).filter(Boolean);
}

const MODE_LABELS: Record<LineMode, string> = { text: "Words", math: "Maths" };

// Keeps the caret in the line while a button below it is pressed.
function keepFocus(event: MouseEvent) {
  event.preventDefault();
}

/** A student's working on ruled lines: the line they were given, if any, then their own, the
 * last of which is their answer. Enter adds a line, Backspace on an empty one removes it, and the
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
  const [focus, setFocus] = useState<{ line: number; token: number } | null>(null);
  const [active, setActive] = useState<{ line: number; mode: LineMode | null }>({
    line: 0,
    mode: null,
  });
  const [modeRequest, setModeRequest] = useState<{
    line: number;
    mode: LineMode;
    token: number;
  } | null>(null);
  const { steps } = draft;
  const offset = givenStep ? 1 : 0;

  function focusLine(line: number) {
    setFocus((current) => ({ line, token: (current?.token ?? 0) + 1 }));
  }

  function setStep(index: number, value: string) {
    onChange({ ...draft, steps: steps.map((s, i) => (i === index ? value : s)) });
  }

  function addStep(after: number) {
    if (steps.length >= MAX_STEPS) return;
    onChange({ steps: [...steps.slice(0, after + 1), "", ...steps.slice(after + 1)] });
    focusLine(after + 1);
  }

  function removeStep(index: number) {
    onChange({ steps: steps.filter((_, i) => i !== index) });
    focusLine(Math.max(0, index - 1));
  }

  function switchMode(mode: LineMode) {
    setModeRequest((current) => ({ line: active.line, mode, token: (current?.token ?? 0) + 1 }));
  }

  return (
    <div className="working-sheet">
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
        {steps.map((step, index) => {
          const number = index + offset + 1;
          return (
            <li key={index} className="working-line">
              <span className="line-number" aria-hidden="true">
                {number}
              </span>
              <StepInput
                value={step}
                label={`Step ${number}`}
                placeholder={index === 0 ? firstPlaceholder : undefined}
                focusToken={focus?.line === index ? focus.token : undefined}
                onChange={(value) => setStep(index, value)}
                onEnter={() => addStep(index)}
                onSubmit={onSubmit}
                onRemove={steps.length > 1 ? () => removeStep(index) : undefined}
                onMoveUp={index > 0 ? () => focusLine(index - 1) : undefined}
                onMoveDown={index + 1 < steps.length ? () => focusLine(index + 1) : undefined}
                onFocus={() => setActive((current) => ({ ...current, line: index }))}
                onModeChange={(mode) => setActive({ line: index, mode })}
                modeRequest={modeRequest?.line === index ? modeRequest : undefined}
              />
              {steps.length > 1 && (
                <button
                  type="button"
                  className="line-remove"
                  aria-label={`Remove step ${number}`}
                  onClick={() => removeStep(index)}
                >
                  ×
                </button>
              )}
            </li>
          );
        })}
      </ol>
      <div className="working-foot">
        <button
          type="button"
          className="add-line"
          disabled={steps.length >= MAX_STEPS}
          onClick={() => addStep(steps.length - 1)}
        >
          <span aria-hidden="true">+</span> Add a line
        </button>
        {active.mode && (
          <div className="line-mode" role="group" aria-label="Write in words or maths">
            {(["text", "math"] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                aria-pressed={active.mode === mode}
                onMouseDown={keepFocus}
                onClick={() => switchMode(mode)}
              >
                {MODE_LABELS[mode]}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
