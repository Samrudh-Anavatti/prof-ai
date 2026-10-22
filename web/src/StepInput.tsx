import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import type { MathfieldElement } from "mathlive";

import { isWord, MATHS_KEYS, mathsTail } from "./lineModes";
import { Markdown } from "./Markdown";
import { fieldLatex, loadedMathLive, loadMathLive, placeholderLatex, stepValue } from "./mathlive";
import { stepPreview, typedToLatex } from "./typedMaths";

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
  onFocus?: () => void;
  /** Maths fields only: whether the caret is in words or maths. */
  onModeChange?: (mode: LineMode) => void;
  /** Maths fields only: switches to words or maths at the caret whenever its token changes. */
  modeRequest?: { mode: LineMode; token: number };
}

export type LineMode = "text" | "math";

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

/** The text run the caret is in, from where it starts, as plain text. */
function wordsBeforeCaret(mf: MathfieldElement): { start: number; text: string } {
  let start = mf.position;
  while (start > 0 && mf.getValue(start - 1, start, "latex-expanded").startsWith("\\text")) {
    start--;
  }
  return { start, text: mf.getValue(start, mf.position, "plain-text") };
}

/** Typed among words, a maths key turns the maths just before it into maths, and the key then
 * works as it does in maths: ^ makes a power of it, / a fraction. */
function wordsToMaths(mf: MathfieldElement) {
  const { start, text } = wordsBeforeCaret(mf);
  const tail = mathsTail(text);
  if (tail.maths) {
    mf.selection = { ranges: [[start + tail.from, mf.position]] };
    mf.insert(typedToLatex(tail.maths), {
      mode: "math",
      insertionMode: "replaceSelection",
      selectionMode: "after",
    });
  }
  mf.mode = "math";
}

/** A word typed in maths, from start to the caret, back as words. MathLive may have turned
 * some of its letters into symbols (since into sin), so the letters typed are used. */
function mathsToWords(mf: MathfieldElement, start: number, letters: string) {
  const space = start > 0 ? " " : "";
  mf.selection = { ranges: [[start, mf.position]] };
  mf.insert(`${space}${letters} `, {
    mode: "text",
    insertionMode: "replaceSelection",
    selectionMode: "after",
  });
  mf.mode = "text";
}

function MathStep(props: StepInputProps & { element: typeof MathfieldElement }) {
  const { value, label, placeholder, focusToken, modeRequest, element } = props;
  const host = useRef<HTMLDivElement>(null);
  const field = useRef<MathfieldElement | null>(null);
  const latest = useRef(props);
  // The student picked words or maths for this empty line, so it doesn't go back to words.
  const picked = useRef(false);

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
    // Letters typed in maths since the last other key, and where they start.
    let word: { start: number; letters: string } | null = null;
    const empty = () => !mf.getValue("latex-expanded").trim();
    // A line starts in words; maths keys switch it to maths.
    const wordsIfEmpty = () => {
      if (empty() && !picked.current) mf.mode = "text";
    };
    wordsIfEmpty();
    const onInput = () => {
      if (!empty()) picked.current = false;
      wordsIfEmpty();
      latest.current.onChange(stepValue(mf.getValue("latex-expanded")));
    };
    const onFocusIn = () => {
      wordsIfEmpty();
      latest.current.onFocus?.();
      latest.current.onModeChange?.(mf.mode === "text" ? "text" : "math");
    };
    const onModeChange = () => {
      if (mf.hasFocus()) latest.current.onModeChange?.(mf.mode === "text" ? "text" : "math");
    };
    const stop = (event: Event) => {
      event.preventDefault();
      event.stopPropagation();
    };
    const onKeyDown = (event: globalThis.KeyboardEvent) => {
      // MathLive only maps " to words on US layouts; a UK keyboard types it with Shift+2.
      if (event.key === '"') {
        word = null;
        picked.current = empty();
        mf.executeCommand(["switchMode", mf.mode === "text" ? "math" : "text"]);
        return stop(event);
      }
      const run = handlerFor(lineKey(event, empty()), latest.current);
      if (run) {
        run();
        return stop(event);
      }
      if (event.ctrlKey || event.metaKey || event.altKey) return;
      if (event.key.length === 1) wordsIfEmpty();
      if (mf.mode === "text") {
        if (MATHS_KEYS.has(event.key)) wordsToMaths(mf);
        return;
      }
      if (event.key === " " && word && isWord(word.letters)) {
        mathsToWords(mf, word.start, word.letters);
        word = null;
        return stop(event);
      }
      if (/^[A-Za-z]$/.test(event.key)) {
        word ??= { start: mf.position, letters: "" };
        word.letters += event.key;
      } else if (event.key !== "Shift") {
        word = null;
      }
    };
    const forgetWord = () => {
      word = null;
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
    mf.addEventListener("focusin", onFocusIn);
    mf.addEventListener("mode-change", onModeChange);
    mf.addEventListener("pointerdown", forgetWord);
    mf.addEventListener("keydown", onKeyDown, { capture: true });
    mf.addEventListener("move-out", onMoveOut);
    return () => {
      mf.removeEventListener("input", onInput);
      mf.removeEventListener("focusin", onFocusIn);
      mf.removeEventListener("mode-change", onModeChange);
      mf.removeEventListener("pointerdown", forgetWord);
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
      if (!latex) mf.mode = "text";
    }
  }, [value]);

  useEffect(() => {
    field.current?.setAttribute("aria-label", label);
    if (field.current) field.current.placeholder = placeholder ? placeholderLatex(placeholder) : "";
  }, [label, placeholder]);

  useEffect(() => {
    if (focusToken !== undefined) field.current?.focus();
  }, [focusToken]);

  const requestToken = modeRequest?.token;
  useEffect(() => {
    const mf = field.current;
    if (!mf || !modeRequest) return;
    picked.current = !mf.getValue("latex-expanded").trim();
    mf.focus();
    mf.executeCommand(["switchMode", modeRequest.mode]);
    // The request is acted on once, when its token changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [requestToken]);

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
