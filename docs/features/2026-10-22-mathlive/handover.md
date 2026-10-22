# Handover: MathLive maths input in the working editor

- **Owner:** punji
- **PR:** see the PR for `feat/mathlive`
- **Merged:** 2026-10-22

## What was built
As planned, plus four things testing turned up:
- **`StepInput.tsx` is a MathLive maths field.** Each working step and the final answer is one. The value is `$…$` LaTeX, read with `latex-expanded` so MathLive's own macros never leave the browser.
  - MathLive is lazy-loaded on first use, into its own 220 KB gzipped chunk.
  - The old typed input with its preview stays as the fallback while MathLive loads, or if it fails to load.
  - Once MathLive has loaded, new steps start as maths fields (`loadedMathLive`). Without that, each new step flashed the fallback and lost focus on Enter.
- **Words:**
  - MathLive turns `or` into ∨. `or` and `and` are now inline shortcuts for upright words (`\:\mathrm{or}\:`), so the field stays in maths mode.
  - `"` toggles text mode. MathLive's built-in binding only covers US layouts, so we handle `event.key === '"'` ourselves, and Shift+2 works on UK keyboards. A `"` keybinding in MathLive's own table is rejected as ambiguous, so don't add one there.
  - `smartMode` is off: in testing it dropped characters ("2x + 3" lost the x, the + and the 3).
- **Fonts:** a small plugin in `web/vite.config.ts` (`mathliveFonts`) copies `node_modules/mathlive/fonts` to `/assets/mathlive/fonts` at build time and serves them in dev. `MathfieldElement.fontsDirectory` points there. MathLive's default is a CDN, which the CSP blocks. Sounds are off.
- **CSP:** `style-src-attr 'unsafe-inline'` is added in `prof_ai.web`. `test_shell_has_strict_security_headers` now ignores only that directive when it checks for `unsafe-inline`, as the ADR 0003 amendment said it would. `tests/mathlive/` pins every other directive.
- **Exact matching (`chat.checking.normalise_answer`):** it now also drops `\:` and unwraps `\text{…}`/`\mathrm{…}`. So `$x=2\:\mathrm{or}\:x=3$` matches a key of `x = 2 or x = 3`, and the "answer right, working missing" upgrade still works for MathLive answers.
- **Types:** `@types/node` was added as a pinned dev dependency, for `vite.config.ts` only (`/// <reference types="node" />`). `src/` still doesn't get Node globals.

## How to run / use it
- Open a lesson with questions as a student, or a lesson you set up for yourself.
- Click a step and type `(x-2)(x-3)=0`, press Enter, type `x=2 or x=3`, then *Submit my answer*.
- On a phone, tapping a step opens MathLive's maths keyboard.
- The tutor's view and Prof AI see the steps as typeset maths.

## Contracts other code can rely on
- Working steps and final answers from the web are `$<latex>$` when MathLive has loaded, and plain typed maths otherwise. The server accepts both.
- `web/src/mathlive.ts`: `loadMathLive()`, `loadedMathLive()`, `fieldLatex(step)`, `stepValue(latex)`, `placeholderLatex(text)`, `FONTS_DIRECTORY`.
- The CSP's only `unsafe-inline` is `style-src-attr`.

## Tests added
- `tests/mathlive/`:
  - the shell's CSP allows inline style attributes and nothing else that's inline or unsafe;
  - fonts are served from our own `/assets/mathlive/fonts`;
  - MathLive-style answers (`\:\mathrm{or}\:`, `\text{ or }`, `\left(…\right)`, `\text{ km}`) match typed keys, and `and` still doesn't match `or`.
- `web/src/mathlive.test.ts`: value round trips, empty fields, conversion of plain typed working, and placeholder escaping.
- Changed, as the ADR planned: `test_shell_has_strict_security_headers` ignores the `style-src-attr` directive. Its other assertions are unchanged.

## Known issues / TODOs
- **Not tried on the live app or a real phone.** I checked it in a local harness: the real `ChatThread` and lesson panel, built with the production Vite config and served by `prof_ai.web.mount_frontend`, so the browser enforced the exact CSP. Results:
  - the fields loaded, and the KaTeX fonts loaded from `/assets`;
  - typing, Enter for a new step, `or`, fractions, roots and *Submit my answer* worked;
  - the payload was `$…$` LaTeX;
  - at phone width, the maths keyboard opened, styled, with no CSP violations.
- **Not verified:** a real `"` keypress. The test tool can only fake it, and the toggle worked with a synthetic event.
- **Answers that differ only in notation** go to the model rather than the exact-match shortcut, for example `\frac34` against a key of `3/4`. The model still marks them; only the "answer right, working missing" upgrade misses them.
- **Long steps:** LaTeX is longer than typed text, so a long step can hit the server's 300-character cap sooner. The server's message is shown.
- **`npm audit`** reports a high-severity issue in `vite` 8.3.0–8.3.2 (`launch-editor`, a dev-server-only dependency). It was there before this branch; bump Vite separately.

## For the other dev
- Sam: as agreed in the ADR 0003 amendment, the CSP now carries `style-src-attr 'unsafe-inline'`. I changed one line of your `test_shell_has_strict_security_headers` so it ignores that directive alone; everything else in it is unchanged. `tests/mathlive/` checks the rest of the policy directive by directive.
