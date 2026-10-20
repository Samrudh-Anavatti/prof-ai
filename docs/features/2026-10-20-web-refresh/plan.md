# Plan: Web app visual refresh

- **Owner:** sam
- **Branch:** `sam/web-refresh`
- **Date:** 2026-10-20

## Goal
Make the web app feel friendly, calm and easy to read for students aged 11–18 and their tutors, without changing what any page does. This is a first pass with creative freedom; Sam will ask for changes after.

## Approach
Work inside the existing stack (React + plain CSS in `web/src/styles.css`). No framework or CSS library.

- **Type:** self-host Lexend (variable), a typeface designed for reading ease, via `@fontsource-variable/lexend`. Larger base size (17px), 1.6 line height, lines capped near 65 characters, tabular numbers for counts.
- **Colour:** keep the existing brand (navy + amber mortarboard). One accent (amber), one warm grey family, tinted shadows, a faint exercise-book dot grid on the page background. Dark mode becomes a tinted navy rather than grey.
- **Chat:** author avatars (rounded-square initials; the logo for Prof AI), clearer bubbles for "me", the other person and Prof AI, a typing indicator, gentle message entry animation, lesson banner with topic chips, and starter prompts from the lesson topics that fill the composer (never auto-send).
- **Navigation:** pill-style tabs with a clear current page, account chip with initials, skip-to-content link.
- **Lists and forms (Lessons, Users, Teaching style):** cards with clear hierarchy, status badges with a dot, consistent inputs, visible focus rings, hover and pressed states on every button, skeleton loading instead of "Loading…".
- **Motion:** transform/opacity only, all disabled under `prefers-reduced-motion`.

## Risks
- **R19 (supply chain):** one new runtime dependency (`@fontsource-variable/lexend`, font files + CSS only, no JS), pinned exactly, lockfile committed, `npm ci`. Alternative was a Google Fonts link, rejected: it breaks the strict CSP and sends students' IPs to a third party.
- **R18 (XSS):** no `dangerouslySetInnerHTML`; messages stay plain React text. CSP unchanged: fonts and the dot grid are same-origin or CSS-only.
- **Correctness:** visual only. Starter prompts only fill the textarea; sending still goes through the same `send` path, so the `@AI` rule and server caps are untouched.
- **Child safety / readability:** WCAG AA contrast for text in both themes; focus rings for keyboard users; reduced-motion respected; not childish for older students.
- **Data:** avatars use initials from names already shown; nothing new is fetched or stored.
- **Cost:** none.

## Files / modules touched
- `web/src/styles.css` (most of the change), `web/src/main.tsx` (font import), `web/index.html` (meta)
- `web/src/App.tsx`, `ChatPage.tsx`, `ChatThread.tsx`, `TutorChatPage.tsx`, `LessonsPage.tsx`, `UsersPage.tsx`, `TeachingStylePage.tsx`, `Logo.tsx` (markup and class names only)
- New: `web/src/Avatar.tsx`
- `web/package.json`, `web/package-lock.json`

## Contracts added or changed
None for the backend. Exported pure helpers from `ChatThread.tsx`: `initials(name)` and `starterPrompts(lesson, shared)`.

## Tests to add
`web/src/webRefresh.test.ts`: `initials` (one name, two names, empty, extra spaces) and `starterPrompts` (shared chats get `@AI` so the AI is asked; at most three; empty without topics; non-shared chats have no mention).

## Open questions
- Do we want to replace the remaining `window.confirm` / `window.prompt` (delete, lock reason) with inline confirmations? Left for a follow-up so this stays visual.
