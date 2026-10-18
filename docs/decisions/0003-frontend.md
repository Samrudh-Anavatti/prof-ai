# 0003: Frontend

- **Status:** accepted (2026-10-18, Sam)

## Context
Students and tutors need a web UI: assignments, answer submission, a streaming chat with the assistant, and a tutor dashboard for results, transcripts and usage. Sign-in is App Service Authentication with a session cookie ([ADR 0002](0002-auth-and-users.md)), and the API is FastAPI on one App Service B1.

## Decision
- **React + TypeScript, built with Vite**, in `web/`.
- **Served by FastAPI from the same App Service.** The build output goes to `src/prof_ai/static/` and ships with the Python package. There's one origin, so the Easy Auth cookie covers the app and the API, with no CORS and no second auth setup.
- **JSON API under `/api/`**; every other `GET` returns the app shell for client-side routing.
- **Tooling:** prettier + eslint + `tsc` in CI, vitest for tests (run by `scripts/test.sh`). Exact dependency versions and a committed lockfile.

## Alternatives considered
- **Jinja + HTMX:** Python only, with no Node toolchain. It gets awkward for a rich chat and dashboards, so rejected.
- **React on Azure Static Web Apps:** the free tier and a clean split, but a second origin means CORS and a second auth setup, which reopens ADR 0002. Rejected.

## Consequences
- **Node 22 joins the toolchain.** CI and deploy build the frontend; locally, `cd web && npm ci`.
- **The static shell (`index.html`, `/assets/*`) is served without `CurrentUser`.** Easy Auth still requires sign-in for it, and it carries no data. All data goes through `/api/*`, which always depends on `CurrentUser`. A regression test enforces this.
- **`GET /me` moved to `GET /api/me`.**
- **npm is a new supply-chain surface (R19).** Keep dependencies few and pinned.
