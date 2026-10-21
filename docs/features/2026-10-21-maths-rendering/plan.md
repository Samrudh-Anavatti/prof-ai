# Plan: Maths and Markdown in Prof AI's replies

- **Owner:** punji
- **Branch:** `feat/maths-rendering`
- **Date:** 2026-10-21

## Goal
Prof AI's replies show real maths (fractions, powers, roots, equations) and simple formatting (bold, lists, numbered steps) instead of plain text like `3/4` or `x^2`. It's a maths tutor, and worksheets extracted in a later phase will be full of maths.

## Approach
- **Render Prof AI's replies as Markdown** with `react-markdown`, `remark-math` and `rehype-katex` (pinned exact). Only Prof AI's messages are rendered this way; people's messages stay plain text, so a student typing `$5` sees `$5`.
- **KaTeX outputs MathML only** (`output: "mathml"`), which every current browser draws natively. That means no KaTeX stylesheet, no web fonts and no inline styles, so the strict CSP (`style-src 'self'`) stays as it is.
- **Safe by default:** `react-markdown` doesn't render raw HTML (no `rehype-raw`), so `dangerouslySetInnerHTML` stays banned. Images are dropped. Links can only be `http(s)`/`mailto`, and they open in a new tab with `rel="noreferrer"`.
- **Prompt:** "Write in plain text" becomes "Write in simple Markdown, with maths in LaTeX between `$…$`". Money is written in words or with £, so `$` means maths.
- Streaming replies render as they arrive.

## Learning check
- **L8 Manageable load:** properly set maths is easier to read than `(3x+2)/(x-1)`, so students spend less effort decoding notation.

## Risks
- **R18 (XSS):** model output is untrusted. No raw HTML, images dropped, links restricted, and the CSP is unchanged. Tested.
- **R19 (supply chain):** three new npm packages (plus their unified/micromark dependencies), pinned exact, installed with `npm ci`, all from established projects (remark/rehype, KaTeX).
- **R22 (dilution):** the base prompt's formatting line changes. It doesn't touch the safety rules; the eval should be re-run when convenient.
- **Correctness:** a stray `$` could turn text into maths. The prompt avoids `$` for money, and the student's own messages aren't parsed.

## Files / modules touched
- `web/package.json`, `web/package-lock.json`, new `web/src/Markdown.tsx`, `web/src/ChatThread.tsx`, `web/src/styles.css`
- `src/prof_ai/chat/prompts/tutor.md`
- Docs: README, INDEX, learning-science table

## Contracts added or changed
- `Markdown` component (`web/src/Markdown.tsx`): renders a Prof AI reply.
- Prof AI's replies are Markdown with `$…$` / `$$…$$` LaTeX.

## Tests to add
`web/src/mathsRendering.test.ts`: inline and display maths become MathML; Markdown lists and bold render; raw HTML is shown as text, not run; images are dropped; `javascript:` links are removed. `tests/maths_rendering/`: the base prompt asks for Markdown with LaTeX and still forbids HTML.

## Open questions
- None.
