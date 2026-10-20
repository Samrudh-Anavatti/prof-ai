# Handover: Web app visual refresh

- **Owner:** sam
- **PR:** not opened yet (first pass awaiting Sam's review)
- **Merged:** —

## What was built
A visual refresh of the whole web app for students aged 11–18 and their tutors. Behaviour, endpoints and data are unchanged.

- **Type:** Lexend (variable, self-hosted via `@fontsource-variable/lexend@5.3.0`, imported in `web/src/main.tsx`), 17px base, 1.6 line height, balanced headings, tabular numbers for counts.
- **Colour:** the existing navy + amber brand, reorganised as tokens on `:root` in `web/src/styles.css`, with a warm cream page and a faint dot grid. Dark mode uses a tinted navy. Status colours (success, danger) are tokens too.
- **Shell:** pill-style nav with a filled current page, an account chip with initials, a skip-to-content link, and a single `<main id="content">` in `App.tsx`. The pages' own `<main>` became `<section>`.
- **Chat:** avatars (rounded-square initials; the logo for Prof AI), bubbles for me, the other person (amber) and Prof AI (white), a three-dot typing indicator, a gentle message fade-in, a lesson card with topic chips, and **starter prompts** in empty chats. Starters only fill the composer and never send. In lesson chats they start with `@AI`, so they ask Prof AI. Students see them in lesson chats; tutors see them only in their test chats.
- **Lessons and Users:** rows on one card with an aligned grid, avatars on user rows, status badges with a dot (`.status-badge`, replacing `.pill`), a dashed empty state, and consistent inputs and file picker.
- **States:** skeleton loaders (`Skeleton.tsx`) replace "Loading…"; every button has hover, pressed and `:focus-visible` states; all motion is off under `prefers-reduced-motion`.
- **Mobile:** nav scrolls sideways under the logo, the composer buttons sit in a row under the text box, and user rows stack.
- `index.html` gained a description and light/dark `theme-color`.

Differences from the plan: `initials` lives in `Avatar.tsx` rather than `ChatThread.tsx`. `starterPrompts` takes the lesson (or `null`) rather than `(lesson, shared)`, since a chat is shared exactly when it has a lesson.

## How to run / use it
Nothing new: `npm run dev` in `web/`, or `npm run build` and use :8000. To review the UI without Azure, I ran Vite against a throwaway Node mock of the `/api` routes (synthetic data) and took screenshots with headless Chrome. It isn't committed; say if you want it under `scripts/`.

## Contracts other code can rely on
- `web/src/Avatar.tsx`: `initials(name)` and `<Avatar name tone="ai" | "tutor" | "student" />`.
- `web/src/ChatThread.tsx`: `starterPrompts(lesson: LessonOverview | null): string[]` (at most 3; `@AI`-prefixed when there's a lesson).
- `web/src/Skeleton.tsx`: `<PageSkeleton label? />`.
- `web/src/Logo.tsx`: also exports `LogoMark`.
- CSS conventions in `styles.css`: use the tokens (`--surface`, `--brand-soft`, `--r-md`, `--shadow-sm`, `--z-*` …) rather than raw colours, radii or z-indexes. Chat content is centred with `--column`: direct children of `.chat` are capped to it, while `.thread` spans full width (so its scrollbar sits at the edge) and pads itself.

## Tests added
`web/src/webRefresh.test.ts` (vitest; frontend tests live next to the code per CLAUDE.md): `initials` edge cases, and `starterPrompts` (topic prompts ask Prof AI via `asksAi`, capped at 3, fall back to the lesson title, and there's no mention outside lesson chats).

## Known issues / TODOs
- Lock reasons and delete confirmations still use `window.prompt` / `window.confirm`. Inline confirmations would fit the new look; left out to keep this pass visual.
- Bubbles still render plain text (no Markdown or maths). That's the next readability win for maths and science, but it needs a safe renderer (no `dangerouslySetInnerHTML`, R18).
- On narrow screens the nav scrolls sideways with no fade hint at the edge.

## For the other dev
- One new npm dependency (fonts and CSS only, no JS, no install scripts, OFL licence), pinned exactly. Run `npm ci` after pulling.
- The CSP is unchanged: the fonts are bundled into `/assets` (same origin). Don't swap them for a Google Fonts link; the CSP blocks it, and it would send students' IPs to Google.
- If you add a page, render it as a `<section>` (the shell owns `<main>`), use `<PageSkeleton />` while loading, and reuse `.admin-page`, `.invite-form`, `.user-list`/`.user-row`, `.status-badge`, and `.primary`/`.secondary`/`.danger`.
