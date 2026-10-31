# Keystone MVP: Specification

Keystone is a secure AI assistant that answers employees' questions from their company's own documents, names
the documents each answer comes from, and says "No answer found." when the documents do not contain the answer.
The worked example is Contoso, a fictional 120-person engineering consultancy.

This file is the source of scope for the Assignment 2 MVP. It is based on the Assignment 1 user stories
(`Keystone Product Specification.pdf`, slides 12 and 13) and was written before any MVP change to the code.
Anything not listed here is not built.

---

## 1. Scope

| ID | User story | In the MVP |
|----|------------|------------|
| M1 | As an employee, I ask a question in plain language and get an answer with its source documents. | Yes |
| M2 | As an employee, I am told when the documents do not contain the answer, so I am not misled. | Yes |
| M3 | As an employee, I only receive answers from content I am allowed to see. | Yes |
| M4 | As a user, I log in with a role (employee or admin) so access is controlled. | Yes |
| M5 | As an admin, I upload and delete documents and choose which team or project can see them. | Yes |
| S1 | Rate answers with thumbs up or down. | Yes |
| S2 | Chat history: create, reopen, delete chats. | Yes |
| S3 | Summarise an uploaded meeting transcript. | No |
| S4 | Admin sees questions answered with "No answer found". | Only if time allows |

Not in the MVP: meeting summaries (S3), live connectors (Slack, Teams, Outlook, drive sync), audit dashboard,
user management screens, other languages, API access for other applications (waits for the next assignment).

---

## 2. Acceptance criteria

Each criterion comes from Assignment 1 and is checked by an automated test, by the manual checklist
(`docs/manual-tests.md`), or by both.

| ID | Acceptance criterion (Assignment 1) | Automated test | Manual check |
|----|-------------------------------------|----------------|--------------|
| M1 | Median answer time under 10 s; every answer lists at least 1 source document. | Every answer other than "No answer found." has at least one source | Answer time of each question recorded; median under 10 s |
| M2 | If no relevant passage exists, the app shows "No answer found" and invents nothing. | A reply without permitted sources becomes "No answer found." | Company-car question returns "No answer found." |
| M3 | A test user without access to a restricted project never gets text or citations from it. | `employee` asking about Project B gets no Project B text or citation; `newhire` gets none from Project A | Same questions asked on the live site |
| M4 | A wrong password is rejected; admin pages are blocked for employees. | Wrong password returns 401; employee on admin routes gets 403; logout ends the session | Wrong password shows an error; `/admin` redirects an employee |
| M5 | A new document is searchable right after upload; deleted ones never appear in answers. | Uploaded document reaches the prompt; deleted document never does; a deleted name can be uploaded again | Upload, ask, delete, ask again |
| S1 | Rating is saved and visible to the admin. | Rating saved; admin ratings list shows it; employee cannot read it | Rate as employee, see it as admin |
| S2 | Chats persist after logout; deleted chats disappear. | Chat listed after logout and login; deleted chat returns 404 | Reopen and delete a chat |

---

## 3. Users and test accounts

| Account | Role | Projects | Purpose |
|---------|------|----------|---------|
| `employee` | employee | GENERAL, A | Main demo account; cannot see Project B |
| `newhire` | employee | GENERAL | Cannot see Project A or B, so M3 can be seen from both sides |
| `admin` | admin | all | Document management and ratings |

Passwords come from the environment variables `EMPLOYEE_PASSWORD`, `NEWHIRE_PASSWORD` and `ADMIN_PASSWORD`.
They are given to testers in the Moodle PDF and in class, never on the public login page or in git.

---

## 4. Screens and flows

| Screen | Who | What it does |
|--------|-----|--------------|
| Login | everyone | Username and password; wrong password shows an error; employees go to Chat, admins can open Admin |
| Chat | employee, admin | Sidebar with saved chats (new, reopen, delete); question box; cited answer with source chips; drawer to read a source; thumbs up/down; logout |
| Admin: Documents | admin | List of documents with project; upload a txt/md/pdf file to a project; delete a document |
| Admin: Ratings | admin | List of ratings: question, answer, thumbs up/down, user, date; newest first |

Flows:

1. Employee: log in → ask → read the cited answer or "No answer found." → open a source → rate → new chat or
   reopen an old one → log out.
2. Admin: log in → upload a document to a project → the next question from a permitted employee can cite it →
   delete it → it is never cited again → read the ratings.

### Errors the user sees

| Situation | Message |
|-----------|---------|
| Wrong username or password | "Wrong username or password" |
| Empty or too long question | The send button stays disabled; the box stops at 2000 characters |
| Gemini rate limit after the retries | "Keystone is busy, please try again in a minute."; the question stays on screen with a Retry button |
| Gemini fails, times out or cannot be reached | "The AI service failed, please try again."; the question stays on screen with a Retry button |
| The browser cannot reach Keystone | "Could not reach Keystone. Check your internet connection and retry." |
| The database cannot be reached | "Keystone cannot reach its database right now, please try again in a minute." (login shows "Keystone is unavailable right now") |
| Any other server error | "Something went wrong on our side, please try again."; the details go only to the server log |
| Unsupported or empty upload | "Unsupported file type…" or "No text could be extracted…" |
| Session expired or not logged in | Redirect to Login |
| Chat or document that does not exist or is not the user's | "Not found" |
| Employee opens an admin page | Redirect to Chat |

Every screen works at phone width (360 px) as well as on a desktop.

---

## 5. Data tables (PostgreSQL)

| Table | Columns | Keys and constraints | User story |
|-------|---------|----------------------|------------|
| `projects` | id, code (GENERAL/A/B), name | PK id; UNIQUE code | M3, M5 |
| `users` | id, username, password_hash, role, created_at | PK id; UNIQUE username; CHECK role IN ('employee', 'admin') | M4 |
| `user_projects` | user_id, project_id | PK (user_id, project_id); FK → users, projects | M3 |
| `documents` | id, name, content, project_id, uploaded_by, created_at, deleted_at | PK id; UNIQUE name WHERE deleted_at IS NULL; FK project_id → projects, uploaded_by → users | M1, M5 |
| `sessions` | token, user_id, created_at, expires_at | PK token; FK → users | M4 |
| `conversations` | id, user_id, title, created_at, updated_at | PK id; FK → users | S2 |
| `messages` | id, conversation_id, role, content, created_at | PK id; FK → conversations ON DELETE CASCADE; CHECK role IN ('user', 'assistant') | S2 |
| `message_sources` | message_id, document_id | PK (message_id, document_id); FK → messages ON DELETE CASCADE, documents | M1 |
| `message_context_documents` | message_id, document_id | PK (message_id, document_id); FK → messages ON DELETE CASCADE, documents | M3 |
| `ratings` | id, message_id, user_id, is_positive, question, answer, created_at | PK id; UNIQUE message_id; FK message_id → messages ON DELETE SET NULL, user_id → users | S1 |

Rules:

- Admins see every project; `user_projects` is used only for employees.
- Documents are soft-deleted (`deleted_at` set). Every query that reads documents filters
  `deleted_at IS NULL`, so a deleted document is never sent to the LLM or cited, while citation rows stay valid.
- `message_sources` holds the documents an answer cites. `message_context_documents` holds every document that
  was in the prompt. A saved answer is hidden when the user can no longer see a document it cites, or, for an
  answer without citations, any document from its prompt.
- `ratings` keeps a copy of the question and answer, so a rating stays readable for the admin after its chat is
  deleted (`message_id` becomes NULL).
- All timestamps are `TIMESTAMPTZ`.
- Deleting a user deletes their project links, sessions, chats and ratings. The app has no screen that deletes
  users; this only keeps the keys valid.
- Two indexes support the most frequent reads: a user's chats by last update, and a chat's messages in order.

---

## 6. Architecture

```
Browser ──HTTPS──► FastAPI on Render ──► Neon PostgreSQL
                        │
                        └──► Gemini API
```

- **Stack:** Python 3.12, FastAPI, psycopg 3, PostgreSQL, plain HTML/CSS/JS, Gemini free tier. No frontend
  framework, no ORM, no vector database.
- **Answering:** the documents the user may see are selected in SQL; their full text, the question and the
  recent chat history go into one prompt; the model replies with JSON `{"answer", "sources"}`; sources the user
  cannot see are dropped, and a reply without permitted sources becomes "No answer found.".
- **Hosting:** Render web service (deploys from the GitHub repository) and a Neon PostgreSQL database.
  Secrets live only in Render environment variables.
- **Tests:** pytest against a local PostgreSQL test database, with a fake LLM; no test calls Gemini.

### Folder structure

```
app/
  config.py         settings from environment variables
  db.py             PostgreSQL connection (psycopg 3), schema creation, password hashing
  documents.py      text extraction, seeding, permission-filtered queries, soft delete
  llm.py            generate(): the single LLM entry point (Gemini), 429 retry
  chat.py           prompt building and JSON parsing
  auth.py           login, session cookie, admin check
  conversations.py  chats, messages, ratings
  main.py           FastAPI routes
db/
  schema.sql        tables, keys, constraints
  reset.py          drops the data and re-seeds test accounts, projects and sample documents
static/             HTML/CSS/JS screens (login, chat, admin)
tests/              pytest, fake LLM, local PostgreSQL test database
docs/               manual test checklist, UX review, screenshots, demo script
.docs/              the 7 sample documents
SPEC.md             this file
CLAUDE.md           project rules for the LLM agent
README.md           setup, run, test, deploy
```

### Environment variables

| Variable | Used for |
|----------|----------|
| `DATABASE_URL` | PostgreSQL connection string (Neon in production, local PostgreSQL in development) |
| `GEMINI_API_KEY` | Gemini API key |
| `GEMINI_MODEL` | Gemini model name |
| `LLM_MAX_RETRIES`, `LLM_RETRY_WAIT_SECONDS` | Retries after a Gemini rate limit |
| `CHAT_HISTORY_MESSAGES` | Earlier messages sent with each question (0 turns follow-ups off) |
| `DOCS_DIR` | Folder of sample documents used by the seed and reset |
| `EMPLOYEE_PASSWORD`, `NEWHIRE_PASSWORD`, `ADMIN_PASSWORD` | Test account passwords |

---

## 7. Build order

One flow at a time; each step ends with `pytest` passing and a check in the browser.

1. `SPEC.md` and `CLAUDE.md` (this step).
2. `db/schema.sql` and `db/reset.py`.
3. Port to PostgreSQL: connection and login; documents; chats and messages. The existing tests pass again.
4. Missing automated tests from section 2.
5. First deploy to Render and Neon.
6. Admin ratings screen (S1).
7. Error handling, including the "busy" message.
8. UX review on hierarchy, contrast, spacing, consistency, accessibility and phone width; comparison with the
   Assignment 1 mockups.
9. Manual test checklist with answer times; classmates test the live site.
10. Submission PDF, screenshots, demo script, rehearsal.
