# Proposal: Keystone MVP for ASI Assignment 2

Author: Beatriz Moura (with Claude) · Date: 31 October 2026 · Status: proposal for review, nothing implemented yet

This document proposes how to turn the existing Keystone prototype into the Assignment 2 MVP. It lists every
requirement in the brief and what will be delivered for it, and it marks what has been checked, what is assumed
and what is still undecided. It is written so that a reviewer with no prior context can challenge it.

Source documents in this folder:

- `Assignment #2 - MVP.pdf`: the brief this proposal answers.
- `Assignment #1 - Product Specification Report.pdf`: the Assignment 1 brief.
- `Keystone Product Specification.pdf`: the Assignment 1 deliverable (user stories M1–M5, S1–S4, mockups).
- `Access to FEUP Disk Servers.pdf`: the FEUP hosting guide (SFTP to `gnomo.fe.up.pt`, `~/public_html`).
- `app/`, `static/`, `tests/`, `README.md`: the current working prototype.

---

## 1. What Assignment 2 asks for

Due 15 November 2026, 23:59 on Moodle; 5-minute live demo between 16 and 20 November. Individual.

**Deliverables (section 2 of the brief):**

1. Working main screens: core screens and the flows between them; forms save data, lists show it, errors are handled.
2. Data tables: tables with attributes, primary keys and foreign keys, implemented in the database.
3. Testing: automated tests for the main logic and critical user flows, plus a manual check of every screen.
4. LLM good practices, visible in the repository: architecture and folder structure defined before prompting,
   a `SPEC.md` based on the Assignment 1 user stories, a `CLAUDE.md` or `AGENTS.md` with project rules, the
   tests, and each change verified before it is accepted.
5. UX and UI: use the LLM to review the screens for hierarchy, contrast, spacing, consistency, accessibility and
   phone-sized behaviour, then compare the result with the Assignment 1 mockups.

**Hosting (section 3):** FEUP disk servers (Apache, PHP, PostgreSQL) are offered; hosting elsewhere is allowed
"at your own responsibility"; a working address must be provided, and the app "must still be available on the
internet and reachable by other applications" for the next assignments.

**Submission (section 4):** the link to the app and a PDF with the data tables and screenshots.

**Assessment criteria (section 6):** core features working end to end · quality and coherence of the data tables
· evidence of testing, automated and manual · LLM good practices visible in the repository · UX and UI quality ·
app online and reachable · clarity and focus of the live demo.

---

## 2. Where the project is today (checked on 28–31 October)

- **Stack:** Python 3.12+, FastAPI, SQLite (`sqlite3` standard library), plain HTML/CSS/JS frontend, Gemini
  (free tier) through `app/llm.py`, with Ollama as a local option.
- **Screens:** login, chat (sidebar with saved chats, cited answers as source chips, a drawer to read the source
  document, thumbs up/down), admin (list, upload and delete documents with a project).
- **Tables (7, in `app/db.py`):** `users`, `user_projects`, `documents`, `sessions`, `conversations`,
  `messages`, `ratings`.
- **Tests:** 32 pytest tests, all passing (`pytest -q` → `32 passed`), with a fake LLM. They cover the permission
  leak test (an employee asking about Project B gets no Project B text or citation), chat parsing, conversations,
  and history access rules.
- **Accounts:** two demo users seeded in `app/db.py`, `employee`/`employee123` (projects GENERAL and A) and
  `admin`/`admin123`. There is no reset of demo data and no account without Project A access.
- **API:** login is a session cookie only; there is no token or API-key access for other applications.
- **Secrets:** `.gitignore` already excludes `.env`, which holds the Gemini key.
- **Not present:** `SPEC.md`, `CLAUDE.md`/`AGENTS.md`, a written architecture, a git repository, a manual test
  record, a UX review record.
- **Hosting check:** `gnomo.fe.up.pt` has no public DNS record (checked from outside FEUP: `fe.up.pt` resolves,
  `gnomo.fe.up.pt` does not), so it is reachable only through the FEUP VPN, as the FEUP guide says. Whether PHP on
  gnomo can call the Gemini API, and the PostgreSQL account details, are **not** known.

### Assignment 1 user stories against the prototype

| ID | Story (short) | Status today | In the MVP? |
|----|---------------|--------------|-------------|
| M1 | Ask in plain language, get an answer with sources | Done | Yes |
| M2 | "No answer found" when the documents do not answer | Done | Yes |
| M3 | Only content the user may see | Done (filter in SQL) | Yes |
| M4 | Login with a role; wrong password rejected; admin pages blocked for employees | Done | Yes |
| M5 | Admin uploads and deletes documents and sets project access | Done | Yes |
| S1 | Thumbs up/down; "saved and visible to the admin" | Saved, **not visible to the admin** | Yes, add an admin ratings view |
| S2 | Chat history: create, reopen, delete | Done | Yes |
| S3 | Summarise a meeting transcript | Not built | No, deferred ("leave everything secondary for later") |
| S4 | Admin sees "No answer found" questions | Not built | Optional, only if time allows |

---

## 3. Hosting decision

### Options considered

| | A. FEUP gnomo (PHP + FEUP PostgreSQL) | B. Render + Neon (keep Python) | C. Own computer + tunnel |
|---|---|---|---|
| Code work | Rewrite the backend in PHP and the tests in PHPUnit | Port SQLite to PostgreSQL in 3 modules | Port to PostgreSQL |
| Reachable from the internet | No, VPN only (checked) | Yes, public HTTPS URL | Only while the laptop is on |
| Gemini reachable | Unknown, needs a test on gnomo | Yes (assumed, standard outbound HTTPS) | Yes |
| Depends on teachers | PostgreSQL account, outbound access | No | No |
| Cost | Free | Free tiers | Free |
| Lasts through the later assignments | Yes, while the FEUP account exists | Only if the free tiers do not expire (to check) | Only while the laptop runs |
| Main risk | Rewrite time; outbound HTTPS may be blocked | Free web service sleeps when idle, first request slow | Laptop must stay on through later assignments |

### Recommendation: B, Render (web service) + Neon (PostgreSQL)

Reasons, tied to the criteria:

- **"App online and reachable"** and "reachable by other applications": a public URL meets this without a VPN;
  gnomo does not.
- **"Core features working end to end"**: the working logic and its 32 tests are kept; the time goes into the
  graded deliverables instead of a language rewrite.
- **"Quality of the data tables"**: PostgreSQL is the database the course uses, and the port is the moment to
  fix the schema (section 4).

Facts about Render and Neon free tiers in this proposal (idle spin-down of roughly 15 minutes on Render, Neon
free tier without expiry) come from memory and **must be checked on their pricing pages** before committing.
The check must confirm that both services stay up, with the data kept, until the end of the semester, not only
until the 16–20 November demo, because the later assignments use the same address.

Option A stays the fallback if the teachers require FEUP hosting. A test page (`feup_check/check.php`) is ready to
check PHP version, extensions, sessions, outbound HTTPS to Gemini and a PostgreSQL connection on gnomo.

### Questions for the teachers (sent before building on either option)

1. Is hosting outside FEUP (Python backend on a free cloud host, PostgreSQL elsewhere) acceptable if it is
   publicly reachable?
2. If FEUP is preferred: PostgreSQL account details, and whether PHP on gnomo may make outbound HTTPS calls.
3. Is VPN-only access acceptable for "reachable by other applications" in the next assignments?
4. What will "reachable by other applications" mean in practice: calls to a JSON API, and with what kind of
   authentication? Today the API accepts only a browser session cookie.

---

## 4. Data tables

The current schema works but has three weaknesses a grader would notice: projects are free text with no table
or foreign key; cited and context documents are stored as JSON arrays in text columns (`sources_json`,
`context_document_ids_json`); and documents and sessions lack basic attributes (uploader, creation time, expiry).

### Proposed schema (PostgreSQL, 10 tables)

| Table | Columns | Keys | User story |
|-------|---------|------|------------|
| `projects` | id, code (GENERAL/A/B), name | PK id; UNIQUE code | M3, M5 |
| `users` | id, username, password_hash, role (`employee`/`admin`), created_at | PK id; UNIQUE username; CHECK role | M4 |
| `user_projects` | user_id, project_id | PK (user_id, project_id); FK → users, projects | M3 |
| `documents` | id, name, content, project_id, uploaded_by, created_at, deleted_at | PK id; UNIQUE name among non-deleted rows (partial index `WHERE deleted_at IS NULL`); FK project_id → projects, uploaded_by → users | M1, M5 |
| `sessions` | token, user_id, created_at, expires_at | PK token; FK → users | M4 |
| `conversations` | id, user_id, title, created_at, updated_at | PK id; FK → users | S2 |
| `messages` | id, conversation_id, role (`user`/`assistant`), content, created_at | PK id; FK → conversations ON DELETE CASCADE | S2 |
| `message_sources` | message_id, document_id | PK (both); FK → messages (CASCADE), documents | M1 (citations) |
| `message_context_documents` | message_id, document_id | PK (both); FK → messages (CASCADE), documents | M3 (re-check of saved answers) |
| `ratings` | id, message_id, user_id, is_positive, question, answer, created_at | PK id; UNIQUE message_id; FK → messages (SET NULL), users | S1 |

Design choices to review:

- **Soft delete for documents (`deleted_at`).** Today, a saved answer that cites a deleted document is hidden.
  With real foreign keys, a hard delete would either be blocked or remove the citation rows and lose that
  information. Marking the document as deleted keeps the foreign keys valid, and every query filters
  `deleted_at IS NULL`, which meets M5 ("deleted ones never appear in answers"). A plain `UNIQUE (name)` would
  then block re-uploading a deleted document under the same name, so uniqueness is a partial index:
  `CREATE UNIQUE INDEX documents_name_active ON documents (name) WHERE deleted_at IS NULL`.
- **`ratings` keeps a copy of the question and answer.** This is deliberate denormalisation: when a chat is
  deleted, `message_id` becomes NULL but the rating stays for the admin to analyse (S1, and the risk slide's
  "admin reviews thumbs-down ratings").
- **Timestamps** become `TIMESTAMPTZ` instead of text.

Deliverables: `schema.sql` (creates the tables), a seed step (test accounts from section 6.1, projects, the 7
sample documents), a reset step that restores that seed data, and an ER diagram for the PDF.

---

## 5. Architecture and folder structure (written before any MVP prompt)

```
Browser ──HTTPS──► FastAPI on Render ──► Neon PostgreSQL
                        │
                        └──► Gemini API (key in Render environment variables)
```

```
app/
  config.py         settings from environment variables (DATABASE_URL, GEMINI_API_KEY, GEMINI_MODEL, ...)
  db.py             PostgreSQL connection (psycopg 3), schema creation, test accounts
  documents.py      text extraction, seeding, permission-filtered queries
  llm.py            generate(): the single LLM entry point, 429 retry
  chat.py           prompt building and JSON parsing
  auth.py           login, session cookie, admin check
  conversations.py  chats, messages, ratings
  main.py           FastAPI routes
db/schema.sql       tables, keys, constraints
db/reset.py         drops the data and re-seeds test accounts, projects and sample documents
static/             HTML/CSS/JS screens (login, chat, admin)
tests/              pytest, fake LLM, real PostgreSQL test database
docs/               manual test checklist, UX review, screenshots, demo script
SPEC.md             user stories, acceptance criteria, scope, data tables
CLAUDE.md           project rules for the LLM agent
README.md           setup, run, deploy
```

Port details: `?` placeholders become `%s`; `lastrowid` becomes `INSERT … RETURNING id`; SQLite `PRAGMA` and the
`ALTER TABLE` migrations in `init_db` are removed (fresh schema); the JSON-array columns become the junction
tables; Ollama is kept as a local-only option or removed (to decide).

`CLAUDE.md` will hold these project rules for the LLM agent:

- the stack (FastAPI, psycopg 3, PostgreSQL, plain HTML/CSS/JS) and the folder layout above; no new libraries or
  folders without asking;
- one flow at a time, in the order of section 7; `SPEC.md` is the source of scope, and nothing outside it is
  built;
- every change passes `pytest` before it is accepted, and is checked by hand in the browser;
- permissions are filtered in SQL before any text reaches the LLM; the Project B leak test must always pass;
- all LLM calls go through `app/llm.py`; secrets come only from environment variables, never from code or git;
- every screen works at phone width and shows a clear message for each error.

---

## 6. Plan for each deliverable

| Brief item | What will be delivered | Evidence for the grader |
|---|---|---|
| Working main screens | Login, chat, admin (documents + new ratings view), all on PostgreSQL; clear errors for wrong password, empty question, LLM failure or rate limit, bad upload, no access | Live app + screenshots in the PDF |
| Data tables | Schema in section 4, implemented in Neon | `db/schema.sql`, ER diagram in the PDF |
| Automated tests | Existing 32 tests ported to PostgreSQL; new tests for login/logout, admin upload/delete (M5: searchable right after upload, never after delete; re-upload of a deleted name works), admin-only access, ratings visible to the admin, every answer other than "No answer found" has at least one source (M1), error cases | `tests/`, a recorded `pytest` run |
| Manual tests | A checklist with one row per screen and flow, phone and desktop, result and screenshot; the answer time of each question is recorded, and the median must be under 10 s (M1) | `docs/manual-tests.md` |
| LLM good practices | `SPEC.md` and `CLAUDE.md` written first; one flow at a time; each change run through the tests and checked by hand before it is accepted | The files themselves, and a git history with one commit per flow, in a repository the teachers can open |
| UX and UI | LLM review of each screen on the six points in the brief; fixes applied; comparison with Assignment 1 slides 8–10 | `docs/ux-review.md` with findings, changes, and before/after screenshots (phone and desktop) |
| Hosting | Render web service + Neon database; test accounts from section 6.1; secrets only in Render environment variables | The URL |
| Access for testers | Test accounts, a reset step, and a clear "busy, try again" message when many people ask at once (section 6.1) | Classmates and teachers log in and test on their own |
| Submission | PDF: app link, repository link, test accounts, data tables + ER diagram, screenshots of every screen | The PDF |
| Live demo | Written 5-minute script with realistic data, rehearsed on the hosted app | `docs/demo-script.md` |

### 6.1 Access for classmates and teachers

The class and the teachers must be able to open the URL, log in and test without help.

| Account | Role | Projects | What it lets a tester see |
|---------|------|----------|---------------------------|
| `employee` | employee | GENERAL, A | Cited answers, chat history, ratings; "No answer found" for Project B (M3) |
| `newhire` | employee | GENERAL only | "No answer found" for Project A questions too, so M3 can be seen from both sides |
| `admin` | admin | all | Document upload and delete, ratings view |

- **Passwords:** new passwords, not the current `employee123`/`admin123`, set from environment variables and
  given only in the Moodle PDF and in class. They are not shown on the public login page.
- **Admin access for classmates:** to decide (section 9). If they get it, they can delete the sample documents.
- **Reset:** `db/reset.py` restores the test accounts, projects and the 7 sample documents. It is run after
  class testing and on the morning of the demo.
- **Many testers at once:** the Gemini free tier has a per-minute request limit. When it is reached after the
  retry in `llm.py`, the chat shows "Keystone is busy, please try again in a minute" instead of a failure, and
  the question is not lost from the input box.
- **API for later assignments:** FastAPI already publishes the API description at `/docs`. Token or API-key
  access for other applications is not built now; it waits for the teachers' answer to question 4 in section 3.

### 6.2 Demo script outline (5 minutes)

Prepare a short `.txt` document on the desktop for step 7 before the session.

1. Log in as `employee`: wrong password first (error shown), then correct.
2. Ask the leave carry-over question: answer + source chip; open the source.
3. Ask a follow-up ("and until when?"), showing chat context. This is the step to drop if Gemini is slow.
4. Ask the Project B walk-away price: "No answer found." (permissions, M3).
5. Ask about a company car: "No answer found." (M2).
6. Rate an answer; log out.
7. Log in as `admin`: see the rating (S1); upload a new document to GENERAL.
8. Back as `employee`: ask about the new document and get it cited (M5); reopen an old chat (S2).

---

## 7. Order of work and timeline (15 days to the deadline)

| Days | Work |
|------|------|
| 31 Oct – 2 Nov | Email teachers; create the GitHub repository and give the teachers access; write `SPEC.md`, `CLAUDE.md`, architecture; `db/schema.sql`; check Render and Neon terms; create Render and Neon accounts |
| 3 – 6 Nov | Port to PostgreSQL; port and extend tests; test accounts and `db/reset.py`; first deploy to Render |
| 7 – 8 Nov | Admin ratings view (S1); error handling pass, including the "busy" message |
| 9 – 11 Nov | UX review and fixes; manual test checklist with answer times; ask two or three classmates to test the hosted app |
| 12 – 14 Nov | PDF, screenshots, demo script, rehearsal on the hosted app; reset the data |
| 15 Nov | Submit (buffer day) |

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| Teachers require FEUP hosting | Option A fallback; `check.php` ready; ask early |
| Render cold start during the demo | Open the app a few minutes before presenting |
| Gemini free-tier rate limit during the demo | Retry already in `llm.py`; no load before the demo; friendly error message |
| Many classmates testing at once hit the Gemini rate limit | "Busy, try again" message (section 6.1); retry in `llm.py` |
| Testers delete or change the sample data before the demo | `db/reset.py` run after testing and on the demo morning; admin access decided in section 9 |
| Free-tier terms differ from what is assumed here, or expire before the later assignments | Check Render and Neon pricing pages before setting up, including how long the free tier lasts |
| Later assignments need another application to call the API, and it only accepts a browser cookie | Ask the teachers (section 3, question 4); add token access when that assignment needs it |
| Tests need a PostgreSQL instance | Local PostgreSQL (Homebrew or Postgres.app) or a separate Neon branch for tests (to decide) |
| "Architecture before prompting" when a prototype already exists | State it honestly: the prototype was the Assignment 1 proof of concept; `SPEC.md`, `CLAUDE.md` and the architecture are written before the MVP changes |

---

## 9. Open decisions

1. Hosting: B (Render + Neon) as recommended, or A (FEUP) after the teachers answer?
2. Git: Render deploys from a git repository, and the brief grades practices "visible in the repository", so the
   history is evidence and the repository is created before the first MVP change. Public, or private with the
   teachers invited?
3. Soft delete for documents (`deleted_at`): accept?
4. Tests against local PostgreSQL or a Neon test branch?
5. Ollama: keep as a local option or remove?
6. S4 ("No answer found" list for the admin): include if time allows, or leave out?
7. Classmates: give them the `admin` password so they can test upload and delete (and rely on the reset), or
   only the two employee accounts?

## 10. Questions for the reviewer

- Does the plan cover every item and criterion of the Assignment 2 brief? Is anything missing or misread?
- Is option B a sound choice against the criteria, or does the brief's wording favour FEUP hosting?
- Is the schema in section 4 coherent and well normalised for the grader? Is the soft-delete choice right?
- Is the scope (M1–M5, S1, S2; S3 deferred) right for "a small product that works and looks good"?
- Is the timeline realistic for an individual student?
