# Plan: Frontend skeleton (React SPA served by FastAPI)

- **Owner:** sam
- **Branch:** `sam/frontend-skeleton`
- **Date:** 2026-10-18

## Goal
Choose the frontend ([ADR 0003](../../decisions/0003-frontend.md)) and ship the smallest working version of it: a React + TypeScript app built with Vite, served by FastAPI from the same App Service, behind the existing sign-in. Signed-in users see who they are; uninvited, locked or signed-out users see a clear message. Assignments and the student/tutor views build on this next.

## Approach
- **`web/`**: Vite + React + TypeScript. `npm run build` writes to `src/prof_ai/static/` (gitignored), which ships inside the Python package. No router or UI library yet; add them when a feature needs them.
- **One origin.** FastAPI serves:
  - `/api/*`: JSON. Every route depends on `CurrentUser` / `require_role`. Unknown `/api/*` paths return a JSON 404, never the app shell.
  - `/assets/*`: Vite's hashed bundles through `StaticFiles` (no path traversal; long cache).
  - Every other `GET`: `index.html` (client-side routes), `no-cache`. If the frontend isn't built, a small fallback page says so.
- **`GET /me` moves to `GET /api/me`** (same response shape) so app routes and API routes can't collide.
- **The static shell is exempt from `CurrentUser`.** Easy Auth still requires sign-in for it, and it carries no user data. This lets the app render a friendly "not invited" or "locked" message from `/api/me`'s 403 instead of a raw JSON page. CLAUDE.md's endpoint rule is updated to say so.
- **API client** (`web/src/api.ts`): sends `X-Requested-With: XMLHttpRequest` and uses `redirect: "manual"`, so an expired session comes back as a 401 or an opaque redirect instead of a cross-origin redirect that `fetch` can't follow. On either, it sends the browser to `/.auth/login/aad?post_login_redirect_uri=<current path>`.
- **Security headers** on every response: a strict CSP (`default-src 'self'`, no inline script, `frame-ancestors 'none'`), `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin`.
- **Local dev:** uvicorn on :8000 with `DEV_USER_ID`, plus `npm run dev` (Vite on :5173, proxying `/api` to :8000). Or `npm run build` and use :8000 alone.
- **CI/deploy:** set up Node 22, `npm ci`, prettier check, eslint, `tsc`, then the tests. Deploy builds the frontend before staging the package.

## Risks
- **Abuse / XSS (new R18):** React escapes output by default. The CSP blocks inline and third-party scripts. Never use `dangerouslySetInnerHTML`; this is enforced with an eslint rule.
- **Supply chain (new R19):** npm dependencies run at build time. Controls: exact versions, a committed lockfile, `npm ci` only, a minimal dependency list, nothing loaded from a CDN at runtime.
- **R8 (cross-student data):** no new data is exposed. A regression test checks that every `/api` route depends on `current_user`, so a new route can't skip auth by accident.
- **Cost:** none. It's static files on the existing B1; there are no new Azure resources.
- **Data:** the browser holds only `/api/me`'s response in memory; nothing goes into `localStorage`.
- **Child safety:** no new surface. The chat comes later, through the guard pipeline.
- **Failure:** if the user store is down, `/api/me` returns 503 and the app shows "Prof AI is unavailable, try again later". If the frontend isn't built, the fallback page shows instead of an error, and `/healthz` is unaffected.

## Files / modules touched
- `docs/decisions/0003-frontend.md` (new), `docs/product/architecture.md`, `docs/product/risks.md`, `CLAUDE.md`
- `src/prof_ai/main.py`, `src/prof_ai/web.py` (new: shell and static serving, security headers)
- `web/` (new)
- `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `.gitignore`, `pyproject.toml` (package data)
- `tests/frontend_skeleton/` (new); `tests/auth/test_auth.py` and `tests/app_skeleton/test_app.py` updated for `/api/me` and the new shell

## Contracts added or changed
- `GET /me` → **`GET /api/me`**, same shape `{id, email, display_name, role, status}` and the same 401/403/503 behaviour.
- All JSON endpoints live under `/api/`. Non-API `GET`s return the app shell.
- The frontend build output goes to `src/prof_ai/static/` (`index.html` + `assets/`).

## Tests to add
- Python (`tests/frontend_skeleton/`): the shell is served for client routes, `/api/*` 404s are JSON, assets are served and traversal is refused, the fallback works when unbuilt, security headers are present, and every `/api` route depends on `current_user`.
- Web (vitest, `web/src/*.test.ts`): the API client redirects to sign-in on 401 or an opaque redirect, returns `/api/me` data, and surfaces 403/503 messages.

## Open questions
- Easy Auth returns 401 instead of 302 for `X-Requested-With: XMLHttpRequest`. That needs verifying live after deploy; the client handles both either way.
