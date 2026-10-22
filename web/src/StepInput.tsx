import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { MathfieldElement } from "mathlive";

import { Markdown } from "./Markdown";
import { fieldLatex, loadedMathLive, loadMathLive, placeholderLatex, stepValue } from "./mathlive";
import { stepPreview } from "./typedMaths";

export const MAX_STEP_CHARS = 300;
// MathLive turns "or" into ∨; students mean the word. \mathrm keeps the field in maths mode.
const WORD_SHORTCUTS = { or: String.raw`\:\mathrm{or}\:`, and: String.raw`\:\mathrm{and}\:` };

export interface StepInputProps {
  value: string;
  onChange: (value: string) => void;
  label: string;
  onEnter?: () => void;
  placeholder?: string;
  autoFocus?: boolean;
}

/**
 * One line of a student's working: a MathLive maths field once it has loaded, typed as plain
 * maths with a typeset preview until then (or if it can't load).
 */
export function StepInput(props: StepInputProps) {
  const [mathField, setMathField] = useState(loadedMathLive);

  useEffect(() => {
    if (mathField) return;
    let current = true;
    loadMathLive()
      .then((element) => current && setMathField(() => element))
      .catch(() => undefined);
    return () => {
      current = false;
    };
  }, [mathField]);

  return mathField ? <MathStep {...props} element={mathField} /> : <TypedStep {...props} />;
}

function MathStep({
  value,
  onChange,
  label,
  onEnter,
  placeholder,
  autoFocus,
  element,
}: StepInputProps & { element: typeof MathfieldElement }) {
  const host = useRef<HTMLDivElement>(null);
  const field = useRef<MathfieldElement | null>(null);
  const handlers = useRef({ onChange, onEnter });

  useEffect(() => {
    handlers.current = { onChange, onEnter };
  });

  // Created by hand rather than as JSX, so React never reconciles MathLive's own DOM.
  useEffect(() => {
    const mf = new element();
    // MathLive's options can only be read once the field is in the page.
    host.current?.appendChild(mf);
    field.current = mf;
    mf.setAttribute("aria-label", label);
    mf.smartFence = true;
    mf.inlineShortcuts = { ...mf.inlineShortcuts, ...WORD_SHORTCUTS };
    mf.setValue(fieldLatex(value), { silenceNotifications: true });
    const onInput = () => handlers.current.onChange(stepValue(mf.getValue("latex-expanded")));
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      // MathLive only maps " to words on US layouts; a UK keyboard types it with Shift+2.
      if (event.key === '"')
        mf.executeCommand(["switchMode", mf.mode === "text" ? "math" : "text"]);
      else if (event.key === "Enter" && handlers.current.onEnter) handlers.current.onEnter();
      else return;
      event.preventDefault();
      event.stopPropagation();
    };
    mf.addEventListener("input", onInput);
    mf.addEventListener("keydown", onKeyDown, { capture: true });
    if (autoFocus) mf.focus();
    return () => {
      mf.removeEventListener("input", onInput);
      mf.removeEventListener("keydown", onKeyDown, { capture: true });
      mf.remove();
      field.current = null;
    };
    // The field is made once; later value and placeholder changes are applied below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [element]);

  useEffect(() => {
    const mf = field.current;
    const latex = fieldLatex(value);
    if (mf && mf.getValue("latex-expanded") !== latex) {
      mf.setValue(latex, { silenceNotifications: true });
    }
  }, [value]);

  useEffect(() => {
    field.current?.setAttribute("aria-label", label);
    if (field.current) field.current.placeholder = placeholder ? placeholderLatex(placeholder) : "";
  }, [label, placeholder]);

  return <div ref={host} className="step-input maths" />;
}

function TypedStep({ value, onChange, label, onEnter, placeholder, autoFocus }: StepInputProps) {
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
