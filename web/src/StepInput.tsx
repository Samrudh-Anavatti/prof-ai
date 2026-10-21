import { type KeyboardEvent } from "react";

import { Markdown } from "./Markdown";
import { stepPreview } from "./typedMaths";

export const MAX_STEP_CHARS = 300;

export interface StepInputProps {
  value: string;
  onChange: (value: string) => void;
  label: string;
  onEnter?: () => void;
  placeholder?: string;
  autoFocus?: boolean;
}

/**
 * One line of a student's working, typed as plain maths with a typeset preview underneath.
 * It's the only place a step is entered, so a maths editor such as MathLive can replace it;
 * MathLive needs `style-src-attr 'unsafe-inline'` in the CSP (show-your-working handover).
 */
export function StepInput({
  value,
  onChange,
  label,
  onEnter,
  placeholder,
  autoFocus,
}: StepInputProps) {
  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && onEnter) {
      event.preventDefault();
      onEnter();
    }
  }

  return (
    <div className="step-input">
      <input
        aria-label={label}
        value={value}
        maxLength={MAX_STEP_CHARS}
        placeholder={placeholder}
        autoFocus={autoFocus}
        autoComplete="off"
        spellCheck={false}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={onKeyDown}
      />
      {value.trim() && (
        <div className="step-preview" aria-hidden="true">
          <Markdown text={stepPreview(value)} />
        </div>
      )}
    </div>
  );
}
