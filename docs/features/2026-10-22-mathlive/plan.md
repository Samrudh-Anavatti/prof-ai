# Plan: MathLive maths input in the working editor

- **Owner:** punji
- **Branch:** `feat/mathlive`
- **Date:** 2026-10-22

## Goal
Students type working the way they would in Desmos: `x^2` becomes a superscript as they type, `/` makes a fraction, and phones get a maths keyboard. Today they type calculator-style text and read a preview underneath.

## Approach
- Swap `web/src/StepInput.tsx` alone, as the show-your-working handover planned. Each step and the final answer becomes a MathLive `<math-field>`, and its value is `$…$` LaTeX. `stepPreview`, the server's `normalise_answer`/`compact_maths` (which strip `$` and spacing) and the chat's Markdown already accept that.
- Read the value as `latex-expanded`, so MathLive's own macros (`\mleft`, `\mright`) don't reach KaTeX, the server or the model.
- MathLive is lazy-loaded (`import("mathlive")`) the first time a step box shows. The plain text box with its preview stays as the fallback while it loads, or if it fails to load.
- Fonts are self-hosted: a small Vite plugin copies `mathlive/fonts` to `/assets/mathlive/fonts` (and serves them in dev). `MathfieldElement.fontsDirectory` points there, and sounds are off (`soundsDirectory = null`). Nothing is loaded from a CDN.
- CSP: add `style-src-attr 'unsafe-inline'`, and only that ([ADR 0003 amendment](../../decisions/0003-frontend.md)). `test_shell_has_strict_security_headers` allows exactly that directive and still fails on any other `unsafe-inline`.
- Words in a step: type `"` to switch to text, as MathLive does. The hint says so.

## Risks
- **R18 (CSP):** loosened to inline style attributes only, as the ADR accepted. Inline scripts, `<style>` blocks and style loads from other origins stay blocked. The test pins this.
- **R19 (supply chain):** one new dependency, `mathlive@0.111.1`, pinned exactly. It has no dependencies of its own.
- **Correctness:** LaTeX is longer than typed text, so a long step can hit the server's 300-character cap. The server still enforces the cap and its message is shown. Exact-match hints (`matches_key`) already ignore `$` and spaces.
- **Cost / abuse / child safety:** no change. The server receives the same fields.

## Learning check
Lower extraneous load (L-register: cognitive load): students write maths as it looks rather than translating it into calculator syntax. Working stays step by step, so self-explanation is unchanged.

## Files / modules touched
- `web/src/StepInput.tsx`, `web/src/WorkingEditor.tsx` (hint text), `web/src/mathlive.ts` (new: loader and value conversion), `web/vite.config.ts`, `web/src/styles.css`, `web/package.json`/`package-lock.json`
- `src/prof_ai/web.py` (CSP), `tests/frontend_skeleton/test_frontend.py` (CSP assertion)

## Contracts added or changed
- A working step or final answer from the web is now `$<latex>$` when MathLive is loaded, and plain typed maths otherwise. The server accepts both.
- The CSP adds `style-src-attr 'unsafe-inline'`.

## Tests to add
- `tests/mathlive/`: the shell CSP allows inline style attributes and nothing else that's inline.
- `web/src/mathlive.test.ts`: converting between field LaTeX and stored step values, including empty values and plain typed steps from older drafts.

## Open questions
- None. The policy decision was made in the ADR 0003 amendment.
