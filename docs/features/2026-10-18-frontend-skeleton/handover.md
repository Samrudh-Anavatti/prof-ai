# Handover: Frontend skeleton (React SPA served by FastAPI)

- **Owner:** sam
- **PR:** <link>
- **Merged:** 2026-10-18

## What was built
- **[ADR 0003](../../decisions/0003-frontend.md):** React + TypeScript (Vite), served by FastAPI from the same App Service.
- **`web/`**: a Vite app.
  - `src/api.ts` is the API client: `getJson`, `getMe`, `ApiError`, `signInUrl`.
  - `src/App.tsx` is a home page that shows "Hi, <name>" and a role-specific line, with a sign-out link and a friendly message for 403 (not invited / locked) or 5xx.
  - It has no router or UI library yet.
- **`prof_ai.web.mount_frontend`** serves:
  - `/assets/*` from the build, with an immutable cache.
  - `index.html` for every other non-API `GET` (`no-cache`, strict CSP).
  - A fallback page when the frontend isn't built.
  - `nosniff` and `Referrer-Policy: same-origin` on every response.
- **`GET /me` is now `GET /api/me`.** API routes are built in `create_api_router()` in `main.py`.
- **CI** runs `npm ci`, `npm run lint` (eslint + prettier), `npm run build` (tsc + vite) and the tests. **Deploy** builds the frontend before staging and refuses to deploy without `index.html`.
- **Dependencies** are pinned exactly and were resolved with `npm install --before=2026-10-04`. Versions: React 19.3, Vite 8.3, TypeScript 6.0, Vitest 5.0, ESLint 10. `npm audit` is clean.

**Differences from the plan:**
- **No `pyproject.toml` change.** Deploy copies `src/` as-is, so `static/` ships without package-data config.
- **The auth regression test is behavioural.** It calls every `/api` operation in the OpenAPI schema without sign-in and expects 401. This FastAPI version nests included routers in private classes, so walking dependencies would be brittle.
- **Reserved paths.** Besides `api/` and `assets/`, the shell also refuses `docs/…` and any path whose last segment contains a dot (`/favicon.ico`, `/openapi.json`). Those get a JSON 404, so the API docs stay hidden in production and missing files don't come back as HTML.

## How to run / use it
```bash
cd web && npm ci
npm run dev        # Vite on :5173; proxies /api to uvicorn on :8000 (set DEV_USER_ID in .env)
npm run build      # writes src/prof_ai/static/; then uvicorn on :8000 serves the app alone
npm run format     # prettier --write
npm run lint       # eslint + prettier --check
```
`bash scripts/test.sh` runs pytest and then `npm test` in `web/`, so `npm ci` must have been run.

## Contracts other code can rely on
- **All JSON endpoints go under `/api/`** (add them in `create_api_router()` or include another `APIRouter` with prefix `/api`). Each must depend on `CurrentUser` / `require_role`; `tests/frontend_skeleton` fails otherwise.
- **`GET /api/me`** returns `{id, email, display_name, role, status}` with the same 401/403/503 behaviour as before.
- **Error shape:** FastAPI's `{"detail": "<message>"}`. The client shows `detail` for 4xx responses; for 5xx and network failures it shows a generic "unavailable" message.
- **Frontend calls go through `getJson` in `web/src/api.ts`.** It sends `X-Requested-With: XMLHttpRequest` and uses `redirect: "manual"`, and on a 401 or a sign-in redirect it sends the browser to `/.auth/login/aad?post_login_redirect_uri=<current path>`.
- **The CSP allows only same-origin scripts, styles, images (plus `data:`) and fetches.** Fonts or images from a CDN need a CSP change in `prof_ai/web.py` and a risk note.

## Tests added
- **`tests/frontend_skeleton/`** (15 tests):
  - the shell for client routes
  - JSON 404s for unknown `/api`, asset and file paths
  - the asset cache header
  - path traversal refused
  - CSP and security headers
  - the fallback when unbuilt
  - API docs hidden in production
  - every `/api` operation requires sign-in
- **`web/src/api.test.ts`** (6 tests):
  - `/api/me` data and headers
  - redirect to sign-in on a 401 or an opaque redirect
  - the 403 message surfaced
  - 5xx and network failures shown generically
  - the sign-in return URL
- **`tests/auth/test_auth.py`:** paths changed from `/me` to `/api/me`. The assertions are unchanged.

## Known issues / TODOs
- **Not yet verified live:** whether Easy Auth returns 401 (rather than 302) to `fetch` with `X-Requested-With`. The client handles both. Check after deploy by letting a session expire, or by deleting the `AppServiceAuthSession` cookie and reloading.
- **No redirect-loop guard.** If the app ever returned 401 to a signed-in browser (for example, platform auth off in production), the page would bounce to sign-in repeatedly. That can't happen with the current config.
- **No frontend component tests yet** (no jsdom or testing-library). Add them when views have real logic.

## For the other dev
Install Node 22 and run `cd web && npm ci` before `scripts/test.sh`. Keep npm dependencies minimal and exact-pinned (`npm install --save-exact`), and say why in your plan when you add one.
