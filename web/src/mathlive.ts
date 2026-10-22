import type { MathfieldElement } from "mathlive";

import { typedToLatex } from "./typedMaths";

/** Copied there by the mathlive-fonts plugin in vite.config.ts; the CSP allows no font CDN. */
export const FONTS_DIRECTORY = "/assets/mathlive/fonts";

let loading: Promise<typeof MathfieldElement> | null = null;
let loaded: typeof MathfieldElement | null = null;

/** MathLive, loaded once on first use so only pages with a working editor pay for it. */
export function loadMathLive(): Promise<typeof MathfieldElement> {
  loading ??= import("mathlive").then(({ MathfieldElement }) => {
    MathfieldElement.fontsDirectory = FONTS_DIRECTORY;
    MathfieldElement.soundsDirectory = null;
    loaded = MathfieldElement;
    return MathfieldElement;
  });
  return loading;
}

/** MathLive if it has already loaded, so a new step can start as a maths field. */
export function loadedMathLive(): typeof MathfieldElement | null {
  return loaded;
}

/** A stored step as the LaTeX a maths field edits: $…$ unwraps, typed maths converts. */
export function fieldLatex(step: string): string {
  const trimmed = step.trim();
  const wrapped = /^\$([\s\S]*)\$$/.exec(trimmed);
  return wrapped ? wrapped[1].trim() : typedToLatex(trimmed);
}

/** A maths field's LaTeX as a stored step, in $…$ so the chat and server read it as maths. */
export function stepValue(latex: string): string {
  const trimmed = latex.trim();
  return trimmed ? `$${trimmed}$` : "";
}

/** Plain placeholder text as LaTeX, since a maths field's placeholder is LaTeX. */
export function placeholderLatex(text: string): string {
  return `\\text{${text.replace(/[\\{}]/g, "")}}`;
}
