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
  placeholder?: string;
  /** Enter. */
  onEnter?: () => void;
  /** Ctrl or ⌘ with Enter. */
  onSubmit?: () => void;
  /** Backspace on an empty line. */
  onRemove?: () => void;
  onMoveUp?: () => void;
  onMoveDown?: () => void;
  /** The line takes focus whenever this changes. */
  focusToken?: number;
}

export type LineKey = "next" | "submit" | "remove";

/** The keys every line of working shares. Arrows differ: inside a maths field they move
 * between a fraction's parts, so MathLive reports when they leave the field instead. */
export function lineKey(
  event: { key: string; ctrlKey: boolean; metaKey: boolean },
  empty: boolean,
): LineKey | null {
  if (event.key === "Enter") return event.ctrlKey || event.metaKey ? "submit" : "next";
  if (event.key === "Backspace" && empty) return "remove";
  return null;
}

function handlerFor(key: LineKey | null, props: StepInputProps): (() => void) | undefined {
  if (key === "next") return props.onEnter;
  if (key === "submit") return props.onSubmit;
  if (key === "remove") return props.onRemove;
  return undefined;
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

function MathStep(props: StepInputProps & { element: typeof MathfieldElement }) {
  const { value, label, placeholder, focusToken, element } = props;
  const host = useRef<HTMLDivElement>(null);
  const field = useRef<MathfieldElement | null>(null);
  const latest = useRef(props);

  useEffect(() => {
    latest.current = props;
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
    const onInput = () => latest.current.onChange(stepValue(mf.getValue("latex-expanded")));
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      // MathLive only maps " to words on US layouts; a UK keyboard types it with Shift+2.
      if (event.key === '"') {
        mf.executeCommand(["switchMode", mf.mode === "text" ? "math" : "text"]);
      } else {
        const run = handlerFor(
          lineKey(event, !mf.getValue("latex-expanded").trim()),
          latest.current,
        );
        if (!run) return;
        run();
      }
      event.preventDefault();
      event.stopPropagation();
    };
    const onMoveOut = (event: Event) => {
      const { direction } = (event as CustomEvent<{ direction: string }>).detail;
      const run =
        direction === "upward"
          ? latest.current.onMoveUp
          : direction === "downward"
            ? latest.current.onMoveDown
            : undefined;
      if (!run) return;
      event.preventDefault();
      run();
    };
    mf.addEventListener("input", onInput);
    mf.addEventListener("keydown", onKeyDown, { capture: true });
    mf.addEventListener("move-out", onMoveOut);
    return () => {
      mf.removeEventListener("input", onInput);
      mf.removeEventListener("keydown", onKeyDown, { capture: true });
      mf.removeEventListener("move-out", onMoveOut);
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

  useEffect(() => {
    if (focusToken !== undefined) field.current?.focus();
  }, [focusToken]);

  return <div ref={host} className="step-input maths" />;
}

function TypedStep(props: StepInputProps) {
  const { value, onChange, label, placeholder, focusToken } = props;
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (focusToken !== undefined) input.current?.focus();
  }, [focusToken]);

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    const run =
      event.key === "ArrowUp"
        ? props.onMoveUp
        : event.key === "ArrowDown"
          ? props.onMoveDown
          : handlerFor(lineKey(event, !value.trim()), props);
    if (!run) return;
    event.preventDefault();
    run();
  }

  return (
    <div className="step-input">
      <input
        ref={input}
        aria-label={label}
        value={value}
        maxLength={MAX_STEP_CHARS}
        placeholder={placeholder}
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
