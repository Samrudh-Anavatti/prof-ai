<div align="center">

# 🎓 Prof AI

**Your tutor, between lessons.**

An AI-assisted tutoring platform for grades 6–12, built *around* a human tutor rather than replacing one.

[![CI](https://github.com/Samrudh-Anavatti/prof-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/Samrudh-Anavatti/prof-ai/actions/workflows/ci.yml)
[![Deploy](https://github.com/Samrudh-Anavatti/prof-ai/actions/workflows/deploy.yml/badge.svg)](https://github.com/Samrudh-Anavatti/prof-ai/actions/workflows/deploy.yml)

[**Open the app**](https://prof-ai.azurewebsites.net) · [Feature index](docs/features/INDEX.md) · [Vision](docs/product/vision.md) · [Architecture](docs/product/architecture.md) · [Risks](docs/product/risks.md) · [CLAUDE.md](CLAUDE.md)

</div>

> [!WARNING]
> **Proof of concept: not for real students yet.** Only invited tutors and synthetic test accounts should use it. The guard pipeline, parental consent, a retention policy and a decision on data residency (R16) must land first. See [Open items](#-open-items).

## Contents

- [The idea](#-the-idea)
- [Where we are](#-where-we-are)
- [🆕 Latest](#-latest)
- [Links](#-links)
- [Azure architecture](#-azure-architecture)
- [How a chat turn works](#-how-a-chat-turn-works)
- [Decisions and direction](#-decisions-and-direction)
- [Open items](#-open-items)
- [Run it locally](#-run-it-locally)
- [Tutor CLI](#-tutor-cli)
- [Repo tour](#-repo-tour)
- [How we work](#-how-we-work)

---

## 💡 The idea

A tutor teaches a live lesson and assigns a chapter and questions. During the week, each student works on the platform:

```
  Teach ──► Assign ──► Practise ──► Mark ──► Re-explain ──► Review
 (tutor)   (tutor)    (student)   (software    (student's     (tutor sees
                                   + AI)       guarded AI)    everything)
```

The student's assistant **coaches rather than hands over answers**, stays **grounded in the tutor's own content**, and is **heavily guarded**. The tutor sees results, transcripts, flags and usage before the next lesson. First users: Sam and Punjy as tutors, with 5–6 students each. More in [vision.md](docs/product/vision.md).

## 📍 Where we are

| | Area | State |
|---|------|-------|
| ✅ | **Infra**: App Service, Foundry, Cosmos, Blob, Key Vault, budget alerts, all in Bicep | Live |
| ✅ | **Sign-in**: Entra External ID with email-code sign-up; only invited emails get in; per-request account locks | Live |
| ✅ | **Content store**: upload textbooks with `prof content add-book` | Live (CLI) |
| ✅ | **Web app**: React SPA served by FastAPI on one origin, strict CSP | Live |
| ✅ | **Tutor chat with Luna**: streamed replies, transcripts, per-user budgets and kill switch | Live |
| ✅ | **Per-user AI configuration**: tutor teaching style + per-user profile in the system prompt | Live |
| ✅ | **Teaching style editor** in the web UI for tutors | Live |
| ✅ | **Users admin page**: invite, lock, unlock and delete; admins manage everyone | Live |
| ✅ | **Context budget**: capped prompt layers under a 256k ceiling, rolling summaries, dollar budgets ([ADR 0005](docs/decisions/0005-models-and-context-budget.md)) | Live after merge |
| 🔜 | **Lessons and shared chats**: tutor-created chats per lesson (5 per student), tutor and student in one chat, `@AI` to call Luna | Next |
| 🔜 | **Knowledge graph**: chapter extraction and curricula, filling the 64k reference layer | Planned |
| 🔜 | **Guard pipeline**: Prompt Shields, topic checks, safeguarding flags, auto-lock | Required before real students |
| ⬜ | Assignments, marking, tutor dashboard | Phase 1, later |

The live list is [docs/features/INDEX.md](docs/features/INDEX.md).

## 🆕 Latest

> Whoever merges a feature updates this section (rule in [CLAUDE.md](CLAUDE.md)), so the other person can see what changed at a glance.

### Context budget, conversation memory and dollar budgets · 2026-10-19 · Sam

The prompt is now a measured, capped thing, ready for lessons and the knowledge graph to plug into ([ADR 0005](docs/decisions/0005-models-and-context-budget.md)):

- **Every chat call is built by one assembler** from capped layers, under a **256k ceiling** (Luna's window is ~922k):

  | Layer | Cap (est. tokens) |
  |---|---|
  | Base prompt | 2k |
  | Teaching style | 3k |
  | **Lesson** (feature b) | **64k** |
  | Profile | 3k |
  | Conversation summary | 4k |
  | Recent messages | 32k |
  | **Reference material** (knowledge graph) | **64k** |
  | New message | 3k |
  | Safety reminder | 0.5k |
  | Output reserve | 8k |

  - **Order:** stable layers come first, so Luna's prompt cache works. In a live test, 2,449 of 2,510 input tokens were cached on the second call, and it cost 5× less.
  - **A safety reminder now comes last**, as well as the base prompt first.
- **Long chats remember:**
  - history is the newest messages that fit in 32k, not the last 20;
  - older messages are folded into a rolling summary, which tutors see in `prof chats show`.
- **Budgets are in dollars**, from real prices including cached input:
  - $0.50 per student a day and $1.50 a day for everyone (`CHAT_DAILY_USER_USD` / `CHAT_DAILY_GLOBAL_USD`);
  - **tutors are unlimited per user** but count towards the global cap.
- **Every reply records what Luna was sent** (size per layer, cached tokens, cost); see `prof chats show`.
- **Next:** lessons and tutor-created chats (5 per student), then the shared tutor–student chat with `@AI`.

📄 [ADR 0005](docs/decisions/0005-models-and-context-budget.md) · [plan](docs/features/2026-10-19-context-budget/plan.md) · [handover](docs/features/2026-10-19-context-budget/handover.md)

<details>
<summary><b>Earlier features</b></summary>

| Date | Feature | Owner | Docs |
|------|---------|-------|------|
| 2026-10-18 | **Users admin page**: invite, lock, unlock and delete at `/users`; email-code sign-up ([create-account link](https://prof-ai.azurewebsites.net/.auth/login/aad?prompt=create&post_login_redirect_uri=/)) | Sam | [handover](docs/features/2026-10-18-user-admin/handover.md) |
| 2026-10-18 | **Teaching style editor**: edit and try your teaching style in the web app | Sam | [handover](docs/features/2026-10-18-teaching-style-editor/handover.md) |
| 2026-10-18 | **Tutor chat PoC**: chat with Luna, per-user profiles, budgets, transcripts CLI | Sam | [handover](docs/features/2026-10-18-tutor-chat/handover.md) |
| 2026-10-18 | **Frontend skeleton**: React SPA served by FastAPI | Sam | [handover](docs/features/2026-10-18-frontend-skeleton/handover.md) |
| 2026-10-14 | **Auth**: invite-only sign-in, users, locks | Sam | [handover](docs/features/2026-10-14-auth/handover.md) |
| 2026-10-14 | **Content store**: upload textbooks | Sam | [handover](docs/features/2026-10-14-content-store/handover.md) |
| 2026-10-14 | **App skeleton and Azure infra** | Sam | [handover](docs/features/2026-10-14-app-skeleton-infra/handover.md) |

</details>

## 🔗 Links

**App and code**

| What | Link |
|------|------|
| Live app | https://prof-ai.azurewebsites.net |
| Health check (no sign-in) | https://prof-ai.azurewebsites.net/healthz |
| Teaching style editor (tutors) | https://prof-ai.azurewebsites.net/teaching-style |
| Users admin (tutors) | https://prof-ai.azurewebsites.net/users |
| **Create-account link for invited people** | https://prof-ai.azurewebsites.net/.auth/login/aad?prompt=create&post_login_redirect_uri=/ |
| Repository | https://github.com/Samrudh-Anavatti/prof-ai |
| Pull requests | https://github.com/Samrudh-Anavatti/prof-ai/pulls |
| CI / deploy runs | https://github.com/Samrudh-Anavatti/prof-ai/actions |

**Azure** (resource group `rg-prof-ai`, UK South, "Subscription 1"; sign in with your workforce account)

| What | Link |
|------|------|
| Resource group | [rg-prof-ai](https://portal.azure.com/#resource/subscriptions/7dc9c954-db74-400c-8314-862146e62259/resourceGroups/rg-prof-ai/overview) |
| App Service | [prof-ai](https://portal.azure.com/#resource/subscriptions/7dc9c954-db74-400c-8314-862146e62259/resourceGroups/rg-prof-ai/providers/Microsoft.Web/sites/prof-ai/appServices) · [log stream](https://portal.azure.com/#resource/subscriptions/7dc9c954-db74-400c-8314-862146e62259/resourceGroups/rg-prof-ai/providers/Microsoft.Web/sites/prof-ai/logStream) · [configuration](https://portal.azure.com/#resource/subscriptions/7dc9c954-db74-400c-8314-862146e62259/resourceGroups/rg-prof-ai/providers/Microsoft.Web/sites/prof-ai/environmentVariablesAppSettings) (`CHAT_ENABLED` kill switch lives here) |
| Microsoft Foundry | [foundry-prof-ai](https://portal.azure.com/#resource/subscriptions/7dc9c954-db74-400c-8314-862146e62259/resourceGroups/rg-prof-ai/providers/Microsoft.CognitiveServices/accounts/foundry-prof-ai/overview) · [Foundry portal](https://ai.azure.com) |
| Cosmos DB | [cosmos-prof-ai](https://portal.azure.com/#resource/subscriptions/7dc9c954-db74-400c-8314-862146e62259/resourceGroups/rg-prof-ai/providers/Microsoft.DocumentDB/databaseAccounts/cosmos-prof-ai/dataExplorer) (Data Explorer) |
| Blob storage | [stprofaicjzzqh](https://portal.azure.com/#resource/subscriptions/7dc9c954-db74-400c-8314-862146e62259/resourceGroups/rg-prof-ai/providers/Microsoft.Storage/storageAccounts/stprofaicjzzqh/containersList) (containers) |
| Key Vault | [kv-prof-ai-cjzzqh](https://portal.azure.com/#resource/subscriptions/7dc9c954-db74-400c-8314-862146e62259/resourceGroups/rg-prof-ai/providers/Microsoft.KeyVault/vaults/kv-prof-ai-cjzzqh/secrets) |
| Application Insights | [appi-prof-ai](https://portal.azure.com/#resource/subscriptions/7dc9c954-db74-400c-8314-862146e62259/resourceGroups/rg-prof-ai/providers/Microsoft.Insights/components/appi-prof-ai/overview) |
| Budgets (£50/month alert) | [Cost Management budgets](https://portal.azure.com/#view/Microsoft_Azure_CostManagement/Menu/~/budgets) |
| Entra External ID (student and tutor accounts) | [profai.onmicrosoft.com](https://entra.microsoft.com/profai.onmicrosoft.com) (use this tenant-scoped URL; the plain one shows a 401) |

**Docs**

| What | Link |
|------|------|
| Feature index (read first) | [docs/features/INDEX.md](docs/features/INDEX.md) |
| Vision, architecture, risk register | [vision](docs/product/vision.md) · [architecture](docs/product/architecture.md) · [risks](docs/product/risks.md) |
| Decisions (ADRs) | [0001 stack](docs/decisions/0001-stack.md) · [0002 auth](docs/decisions/0002-auth-and-users.md) · [0003 frontend](docs/decisions/0003-frontend.md) · [0004 invites](docs/decisions/0004-invites-and-sign-up.md) |
| Agent and contributor rules | [CLAUDE.md](CLAUDE.md) |

## ☁️ Azure architecture

Everything lives in **`rg-prof-ai`** (UK South), defined in [`infra/main.bicep`](infra/main.bicep), tagged `project=prof-ai`, `owner=sam|punjy`. **No keys anywhere**: services talk with managed identities, deploys use GitHub OIDC, and local dev uses your `az login`. The only secret (Easy Auth's client secret) sits in Key Vault.

```mermaid
flowchart LR
    subgraph People["👥 People"]
        S["🧒 Student<br/>browser"]
        T["🧑‍🏫 Tutor<br/>browser"]
        CLI["⌨️ Tutor CLI<br/>prof … (az login)"]
    end

    subgraph Identity["🔐 Identity (separate tenant)"]
        EXT["Entra External ID<br/>profai.onmicrosoft.com<br/>invite-only, sign-up off"]
    end

    subgraph GH["🐙 GitHub"]
        GHA["Actions<br/>CI + deploy on master"]
    end

    subgraph RG["☁️ Azure · rg-prof-ai · UK South"]
        direction LR
        subgraph Web["App Service plan B1 (Linux)"]
            EA["Easy Auth<br/>sign-in gate"]
            APP["prof-ai web app<br/>FastAPI API + React SPA<br/>budgets · locks · rate limits"]
        end
        FDY["Microsoft Foundry<br/>gpt-5.6-luna<br/>+ content filters"]
        COS[("Cosmos DB serverless<br/>users · audit<br/>conversations · usage")]
        BLOB[("Blob storage<br/>sources · content<br/>answer-keys · profiles")]
        KV["Key Vault<br/>auth client secret"]
        MON["App Insights<br/>+ Log Analytics"]
        DEP["Deploy identity<br/>(user-assigned)"]
        BUD["Budget<br/>£50/month alerts"]
    end

    S -- HTTPS --> EA
    T -- HTTPS --> EA
    EA -. "OIDC sign-in" .-> EXT
    EA -- "signed-in requests<br/>X-MS-CLIENT-PRINCIPAL" --> APP
    APP -- "chat, streamed<br/>(managed identity)" --> FDY
    APP -- "users, chats, usage<br/>(managed identity)" --> COS
    APP -- "reads content & profiles,<br/>writes teaching styles" --> BLOB
    EA -. reads secret .-> KV
    APP -. telemetry .-> MON
    CLI -- "upload books, set profiles" --> BLOB
    CLI -- "invites, locks, transcripts" --> COS
    CLI -- "disable / delete accounts (Graph)" --> EXT
    GHA -- "OIDC, no secrets" --> DEP
    DEP -- "deploys the app" --> APP
```

### What each service does

| Service | Resource | Role in Prof AI | Who can reach it | Approx. cost |
|---------|----------|-----------------|------------------|--------------|
| **App Service** (Linux B1) | `prof-ai` on `plan-prof-ai` | Runs one FastAPI app that serves both the JSON API (`/api/*`) and the built React app. Owns every rule: sign-in check, account locks, budgets, rate limits and every model call. The browser never talks to a model directly. | The public internet, but only through Easy Auth | ~£10/month fixed |
| **Easy Auth** (App Service Authentication) | config on `prof-ai` | Forces sign-in on every path except `/healthz` and hands the app a trusted identity header. | n/a | free |
| **Entra External ID** | `profai.onmicrosoft.com` | Holds student and tutor accounts in a tenant **separate** from the one that controls Azure, so a child's account has no reach into infra. Anyone can sign up with an email code, but the app only admits emails a tutor invited ([ADR 0004](docs/decisions/0004-invites-and-sign-up.md)). The web app never calls Graph. | Tutors (admin) via CLI/portal | free at our scale |
| **Microsoft Foundry** | `foundry-prof-ai`, deployment `gpt-5.6-luna` (GlobalStandard, 10k TPM) | The tutor model ("Luna"). Content filters (DefaultV2) run on input and output. Key auth is disabled. | App and tutors (Entra role) | pay per token |
| **Cosmos DB** (serverless) | `cosmos-prof-ai`, database `prof-ai` | App data: `users` (role, status, tutor), `audit` (locks, unlocks, style edits), `conversations` (messages, tokens, flags), `usage` (tokens per user per UTC day). Entra-only, with continuous 7-day backup. | App and tutors (data role) | ~£0 at our scale |
| **Blob storage** | `stprofaicjzzqh` | The content store: `sources/` (original PDFs, tutors only), `content/` (manifests and extracted chapters, app reads), `answer-keys/` (marking only), `profiles/` (per-user markdown injected into the prompt). No public access, no shared keys, 14-day soft delete. | See the access table below | pennies |
| **Key Vault** | `kv-prof-ai-cjzzqh` | Holds the Easy Auth client secret (expires **2027-04-16**; rotate with `scripts/rotate_auth_secret.py`). RBAC, with purge protection. | App reads; tutors manage | pennies |
| **App Insights + Log Analytics** | `appi-prof-ai`, `log-prof-ai` | Request telemetry and logs. 30-day retention with a 0.5 GB/day cap. | Tutors | capped |
| **Deploy identity** | `id-prof-ai-deploy` | GitHub Actions logs in through OIDC (trusted for `master` only) and deploys the app. No publish profile; FTP and basic auth are off. | GitHub `master` | free |
| **Budget** | `prof-ai-monthly` | Emails at 50% and 90% actual, and 100% forecast, of £50/month. | n/a | free |

### Who can touch what

Least privilege, enforced by Azure RBAC rather than by prompts:

| Identity | Foundry | Cosmos | `content` | `profiles` | `sources`, `answer-keys` | Key Vault |
|----------|---------|--------|-----------|------------|--------------------------|-----------|
| Web app (managed identity) | OpenAI user | data contributor | **read** | **read + write**¹ | ✖ none | secrets user |
| Tutors (`tutorPrincipalIds`, `az login`) | OpenAI user | data contributor | read + write | read + write | read + write | secrets officer |
| GitHub deploy identity | ✖ | ✖ | ✖ | ✖ | ✖ | ✖ (website contributor on the app only) |
| Students | Only through the app's API, scoped to their own data | | | | | |

¹ The app writes only `profiles/<signed-in tutor>/teaching-style.md`, through the tutor-only API. A student's `profile.md` stays CLI-only.

## 💬 How a chat turn works

```mermaid
sequenceDiagram
    autonumber
    actor U as Student / tutor
    participant EA as Easy Auth
    participant API as FastAPI · ChatService
    participant B as Blob · profiles
    participant C as Cosmos
    participant L as Foundry · Luna

    U->>EA: POST /api/chat/conversations/{id}/messages
    EA->>API: request + signed-in identity
    API->>C: user exists, not locked?
    API->>API: kill switch · ≤2,000 chars · 10/min · one reply in flight
    API->>C: today's spend under $0.50 (students) and $1.50 (everyone)?
    API->>B: teaching-style.md (tutor) + profile.md (user)
    API->>API: assemble capped layers (ADR 0005), summary, history window ≤32k
    API->>L: system prompt + history + message + safety reminder (max 4,000 output tokens)
    L-->>API: streamed text (or content-filter hit)
    API-->>U: server-sent events: delta… then done
    API->>C: save the turn + cost + context ledger (only once complete)
    API->>L: if old messages piled up: fold them into the summary
```

**The system prompt is layered**, and you can always see the result with `prof profiles show <email>` or on the Teaching style page:

1. **Base tutor prompt**, in the repo ([`tutor.md`](src/prof_ai/chat/prompts/tutor.md)): coach rather than give answers, stay on school topics, no personal details, distress → trusted adult and Childline.
2. **The tutor's teaching style**: `profiles/<tutor-id>/teaching-style.md`. A student gets their tutor's style, so Sam's and Punjy's students get different behaviour.
3. **The user's profile**: `profiles/<user-id>/profile.md`.
4. **Lesson material** (feature b) and the **conversation summary**, then the history, the new message with any **reference material**, and a closing safety reminder. Caps and order: [ADR 0005](docs/decisions/0005-models-and-context-budget.md).

## 🧭 Decisions and direction

### Decided

| ADR | Decision | Why |
|-----|----------|-----|
| [0001](docs/decisions/0001-stack.md) | **Python 3.11 + FastAPI on App Service B1**, Foundry `gpt-5.6-luna`, Blob, Bicep, GitHub Actions; managed identity everywhere | Fast, cheap (~£10/month fixed), a path the team knows, and no keys next to a public repo |
| [0002](docs/decisions/0002-auth-and-users.md) | **Entra External ID** (separate tenant) + **Easy Auth**; invite-only; **Cosmos DB serverless** for app data | Children's accounts kept away from the Azure tenant; locks checked on every request; ~£0 vs ~£12/month for Postgres |
| [0003](docs/decisions/0003-frontend.md) | **React + TypeScript (Vite)**, built into the Python package and served by FastAPI from one origin | One cookie covers the app and API, with no CORS and no second auth setup; strict CSP |
| [0004](docs/decisions/0004-invites-and-sign-up.md) | **Email-code sign-up, gated by invites in the app**; the first sign-in links the invite by its verified email | No passwords or reset step for new users, and no Graph rights for the web app |
| *(in feature plans)* | **A content store in Blob, not a search index**: chapter-in-context first, lazy extraction | A student only needs the chapter they're on, so an always-on search cluster would be wasted money |
| *(in feature plans)* | **Per-user AI configuration as markdown files in Blob**, layered after the base prompt | Easy for tutors to read and edit; safety rules always come first |
| *(in feature plans)* | **Hard budgets in the app**: per-user and global daily caps, input and output caps, kill switch | Cost risk (R3) is controlled before the model is called, not after the bill |
| [0005](docs/decisions/0005-models-and-context-budget.md) | **Frontier models (Luna default, Foundry-hosted preferred); every prompt layer capped under a 256k ceiling; dollar budgets; tutor-created shared chats with `@AI`** | Lessons and the knowledge graph get a fixed, enforced 64k each; caching and model choice show up in the budget; Ollama Cloud rejected for student data |

### Direction

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Repo, docs, Azure, stack ADR | ✅ done |
| 1 (MVP) | Sign-in ✅ · chat with per-user config ✅ · **knowledge base and context injection** 🔜 · **guard pipeline** 🔜 · assignments and typed answers · deterministic and AI marking with tutor override · tutor review (results, transcripts, usage) | in progress |
| 2 | Photo upload of handwritten working, question generation from mistakes, diagrams | later |
| 3 | Whiteboard, self-service tutor UI, more tutors, parent view | later |

### Still to decide (future ADRs)

- **Agent framework** for the grounded student agent: Microsoft Agent Framework, or a plain Foundry tool loop.
- **Marking model** and whether a larger model is needed for edge cases.
- **Rate limiting at scale**: stay in-app (Cosmos-backed) or move to API Management's token-limit policies.
- **Data residency**: a regional or data-zone deployment instead of GlobalStandard (R16).

## 🚧 Open items

**Before any real student** (blocking)

- [ ] **Guard pipeline** (R1, R2, R11): Prompt Shields, topic relevance, an immediate tutor flag on self-harm categories, auto-lock. A stricter custom content filter for ages 11–18.
- [ ] **Data residency** (R16): GlobalStandard may process prompts outside the UK.
- [ ] **Children's data** (R10): jurisdiction, parental consent, privacy notice, retention policy for transcripts.
- [ ] **Safeguarding process**: agree the escalation steps and resources between Sam and Punjy.

**Decisions for Sam**

- [ ] **Session length**: Easy Auth's default is 8 hours. Shorter for students?

**Setup and housekeeping**

- [ ] **Punjy's access**: invite Punjy as a tutor at `/users` (and `prof users set-admin` if Punjy should manage everyone); for Azure and CLI access, add Punjy to the workforce tenant and `tutorPrincipalIds`.
- [ ] **Roll out invites** (after merging the users admin page): run `scripts/setup_external_id.py` (opens sign-up and adds the email claim), `prof users set-admin` yourself, then test an invite end to end.
- [ ] **Rotate the auth secret by 2027-04-16** (`scripts/rotate_auth_secret.py`).
- [ ] **Verify live**: Easy Auth returns 401 rather than 302 to `fetch` when a session expires; replies stream word by word on App Service.

**Known limitations**

- The rate limiter is in memory (one B1 instance); it resets on restart.
- Content-filtered and failed turns don't count towards budgets (the rate limit bounds them).
- Luna's cached-input price is assumed at 10% of input until it shows on the bill.
- Chat renders plain text only: no Markdown or maths yet.
- Chapter detection needs PDF bookmarks; there's no command to edit chapters yet.
- No monthly caps yet (daily dollar caps plus the Azure budget alert).
- Luna makes mistakes (a wrong 7 × 8 hint in testing), so tutors should read transcripts (R6).

## 🛠️ Run it locally

Needs Python 3.11, Node 22 and the Azure CLI (`az login`, with your object ID in `tutorPrincipalIds`).

```bash
git clone https://github.com/Samrudh-Anavatti/prof-ai.git && cd prof-ai
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # .venv/bin/python on macOS/Linux
cp .env.example .env                                           # fill in endpoints + DEV_USER_ID
(cd web && npm ci)
bash scripts/test.sh                                           # pytest + vitest, offline
.venv/Scripts/python -m uvicorn prof_ai.main:app --app-dir src --reload --env-file .env
(cd web && npm run dev)                                        # http://localhost:5173, proxies /api
```

- `DEV_USER_ID` is your External ID object ID (from `prof users list`). It lets you skip sign-in locally and is refused anywhere else.
- Local chat calls the real Luna with your `az login`, so **it costs real tokens**.
- Infra changes: `bash scripts/deploy-infra.sh --what-if`, review, then run without the flag.

## ⌨️ Tutor CLI

The CLI lives in the virtual environment. Run it as `.venv/Scripts/prof …` from the repo root (`.venv\Scripts\prof …` in PowerShell), or activate the venv first and use plain `prof`.

| Task | Command |
|------|---------|
| Invite a student (or use `/users`) | `prof users add --email alex@example.com --name Alex --role student --tutor <tutor email>` |
| List users | `prof users list` |
| Lock / unlock | `prof users lock alex@example.com --reason "…"` · `prof users unlock alex@example.com` |
| Delete someone and their data | `prof users remove alex@example.com` (also deletes their sign-in account) |
| Make a tutor an admin | `prof users set-admin you@example.com` (`--revoke` to undo) |
| Set what the AI knows about someone | `prof profiles set alex@example.com --profile alex.md` |
| Set your teaching style (or use the web page) | `prof profiles set you@example.com --teaching-style style.md` |
| See the exact system prompt | `prof profiles show alex@example.com` |
| Read transcripts | `prof chats list alex@example.com` · `prof chats show alex@example.com <id>` |
| Upload a textbook | `prof content add-book book.pdf --slug maths-9-core --title "Maths 9" --subject maths --grades 9 --licence-type licensed` |
| Browse content | `prof content list` · `prof content show maths-9-core` |

## 🗂️ Repo tour

```
src/prof_ai/
  main.py              app factory: /api router, /healthz, frontend mount
  auth.py              CurrentUser / require_role: sign-in, invite and lock checks
  web.py               serves the React shell with a strict CSP
  chat/                ChatService (all model calls), Foundry client, prompts, Cosmos store, limits
  profiles/            per-user markdown store + the teaching-style API
  users/               user model, invites, the /api/users admin API, Cosmos repository
  content/             Blob content store, PDF manifests
  cli.py               the `prof` tutor CLI
web/src/               React app: App, ChatPage, TeachingStylePage, UsersPage, API client, SSE parser
tests/<feature>/       shared regression suite, one folder per feature
infra/                 main.bicep + main.bicepparam
docs/                  product drafts, ADRs, one folder per feature (plan + handover)
scripts/               test.sh, deploy-infra.sh, External ID setup, secret rotation
```

## 🤝 How we work

Sam and Punjy each drive a coding agent, on their own time. [CLAUDE.md](CLAUDE.md) and `docs/features/` keep the two agents in sync:

1. **Risk-first plan** before code: `docs/features/<date>-<slug>/plan.md`, checked against the [risk register](docs/product/risks.md).
2. Build on `<owner>/<slug>`, with tests in `tests/<slug>/`.
3. **Handover** before merging: what was built, contracts, gotchas, and what the other person needs to do.
4. **Update the [🆕 Latest](#-latest) section of this README** and the INDEX row.
5. Green suite (`bash scripts/test.sh`), then a PR to `master`. Merging deploys.

**Never weaken someone else's test.** The repo is **public**: no real student data, no secrets, no textbooks.

**Team:** Sam ([@Samrudh-Anavatti](https://github.com/Samrudh-Anavatti)) · Punjy · **License:** [MIT](LICENSE)
