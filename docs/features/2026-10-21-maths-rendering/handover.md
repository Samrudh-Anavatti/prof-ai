# Handover: Maths and Markdown in Prof AI's replies

- **Owner:** punji
- **PR:** see the PR for `feat/maths-rendering`
- **Merged:** pending

## What was built
As planned, plus two things found while building:
- **`Markdown` component** (`web/src/Markdown.tsx`) renders Prof AI's messages and its streaming reply. It uses `react-markdown`, `remark-math` and `rehype-katex`, with KaTeX writing **MathML only**. People's messages stay plain text.
- **`normaliseMaths`:** `remark-math` only treats `$$` on lines of their own as display maths. Models also write `\(…\)`, `\[…\]` and one-line `$$…$$`, so these are rewritten first.
- **Readability:** inline maths uses `math-style: normal`, so fractions are full size rather than tiny, and display equations sit centred on their own line. I checked this in a browser.
- **KaTeX pinned to 0.18.11** with an npm `overrides` entry. `rehype-katex` 7.0.1 pulls in KaTeX 0.16, which has a low-severity advisory (GHSA-238p-pmpm-9mq7: prototype pollution bypassing `trust`, which we don't use). `npm audit --omit=dev` now reports 0 vulnerabilities.
- **Base prompt:** "Write in plain text" is now "Write in simple Markdown … maths in LaTeX between single dollar signs … money with £ or in words … Don't use HTML, tables or images."

## How to run / use it
Nothing to set up. Ask Prof AI a maths question in any chat; replies show typeset maths.

## Contracts other code can rely on
- `Markdown({ text })`, `normaliseMaths(text)` and `safeUrl(url)` in `web/src/Markdown.tsx`.
- Prof AI's replies are Markdown with `$…$` / `$$…$$` LaTeX. Anything that shows a reply outside the chat (for example a future tutor transcript view) should render it with `Markdown`.

## Tests added
- `web/src/mathsRendering.test.ts`: inline and display LaTeX become MathML; the other delimiter styles are normalised; Markdown lists and bold render; raw HTML shows as text; images and `javascript:` links are dropped; only http(s) and mailto links survive.
- `tests/maths_rendering/`: the base prompt asks for Markdown with LaTeX and still forbids HTML and `$` for money.

## Known issues / TODOs
- The base prompt changed, so `prof eval dilution` should be re-run when convenient. It was skipped for the proof of concept.
- `prof chats show` prints the raw Markdown and LaTeX, which is fine for a terminal.
- A model that ignores the prompt and writes `$5` for money would show "5" in maths style. The prompt asks for £, which suits UK students.
- The app bundle grew from about 252 KB to 647 KB (78 KB to 197 KB gzipped), mostly KaTeX. Fine for now; if load time matters later, lazy-load `Markdown` so only the chat page pays for it.

## For the other dev
- Show Prof AI's text with `Markdown`, never with `dangerouslySetInnerHTML` (still lint-banned).
- New npm dependencies: `react-markdown`, `remark-math`, `rehype-katex` (exact versions), plus a `katex` override in `web/package.json`.
