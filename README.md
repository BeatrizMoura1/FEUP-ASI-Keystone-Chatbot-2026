# Keystone: Contoso knowledge assistant

A university prototype of a company knowledge chatbot (the "Knowledge Finder" brief) for a fictional engineering
consultancy, Contoso Engineering Consultants. Employees ask questions in plain language and get
answers based **only** on company documents, with citations. If the answer isn't in the documents, the bot
replies "No answer found."

## How it works

1. `python -m db.reset` creates the PostgreSQL tables (`db/schema.sql`) and loads every `.txt` / `.md` / `.pdf`
   in `.docs/`. The project is read from the `Project / visibility tag:` line (GENERAL, A or B).
2. When a user asks a question, the documents they may see are selected **in the SQL query**
   (`documents JOIN user_projects`, deleted documents excluded). Admins see all documents.
3. The full text of those documents and the question go into one prompt (no embeddings or vector database).
   The model must reply with JSON: `{"answer": "...", "sources": ["doc name", ...]}`.
4. The reply is parsed safely. Any cited source the user can't see is dropped, and a reply that is malformed or
   cites no permitted document becomes "No answer found.", so every answer shown has at least one source.

## Chat history

Every question and answer is saved per user in PostgreSQL (`conversations` and `messages` tables), so your chats
are still there the next time you log in.

- A new chat is created when you send its first question, and its title is that question.
- The sidebar lists your chats (Today / Yesterday / Previous 7 days / Older). Use **New chat** to start a
  fresh one, and the bin icon to delete one (its messages are deleted; ratings are kept for analysis).
- Thumbs up/down are linked to the answer, so they show again when you reopen a chat, and you can change them.
- Users only ever see their own chats: every conversation query filters on the logged-in user's id.
- **Follow-up questions work**: the last `CHAT_HISTORY_MESSAGES` messages of the chat (default 6, i.e. 3
  questions and answers) are sent with each new question, so "what actions does *she* have?" is understood.
  The model is told the history is only for understanding the question, never a source: facts must still come
  from the documents, with citations. Set `CHAT_HISTORY_MESSAGES=0` to turn this off.
- **Saved answers follow your current access.** Each saved answer records the documents it cited and every
  document that was in its prompt. Every time a chat is opened (and before history is sent to the model) the
  server checks them against what you can see *now*:
  - an answer that cites a document you can no longer see, or that was deleted, is replaced on the server by
    "This answer is no longer available…", so its text never reaches the browser or the next prompt;
  - an answer is never saved without citations (it becomes "No answer found." first), so this check always
    has the cited documents to go on;
  - if your access comes back, the answer reappears.

## Project structure

```
app/
  config.py      settings read from the environment or .env (pydantic-settings)
  db.py          PostgreSQL connection (psycopg 3), password hashing
  documents.py   text extraction (txt/md/pdf), permission-filtered queries, soft delete
  llm.py         generate(): the single LLM entry point (Gemini), 429 retry
  chat.py        prompt building and JSON parsing
  auth.py        login, session cookie with expiry, admin check
  conversations.py  saved chats: list, open, save question/answer, delete, rate
  main.py        FastAPI routes
db/
  schema.sql     tables, keys, constraints
  reset.py       recreates the tables and seeds projects, test accounts and sample documents
static/          plain HTML/CSS/JS (chat, login, admin)
tests/           pytest tests on a local PostgreSQL test database (no real LLM calls)
.docs/           seed documents (the document name is the file name with underscores as spaces)
```

## Setup

Requires Python 3.12+ and PostgreSQL.

```bash
brew install postgresql@17 && brew services start postgresql@17
createdb keystone && createdb keystone_test

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then set your Gemini key and the three test account passwords
python -m db.reset          # creates the tables, test accounts and sample documents
```

`.env`:

```
GEMINI_API_KEY=<your key from https://aistudio.google.com/apikey>
GEMINI_MODEL=gemini-3.5-flash-lite
DATABASE_URL=postgresql://localhost/keystone
EMPLOYEE_PASSWORD=...
NEWHIRE_PASSWORD=...
ADMIN_PASSWORD=...
```

## Run

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000.

| User       | Password             | Can see                       |
|------------|----------------------|-------------------------------|
| `employee` | `EMPLOYEE_PASSWORD`  | GENERAL + Project A documents |
| `newhire`  | `NEWHIRE_PASSWORD`   | GENERAL documents only        |
| `admin`    | `ADMIN_PASSWORD`     | everything + `/admin` page    |

To reset the database (delete all chats, ratings and uploads, and reload the documents from `.docs/`), run
`python -m db.reset`.

## Deploy (Render + Neon)

The app runs as a free Render web service and keeps its data in a free Neon PostgreSQL database. Render
has no shell on the free plan, so the database is created and seeded from your own computer.

1. **Neon:** create a project (Postgres 17, region AWS Europe Central 1 / Frankfurt) and copy the **pooled**
   connection string.
2. **Seed Neon** from this folder, with the passwords testers will use:

   ```bash
   DATABASE_URL='<Neon connection string>' \
   EMPLOYEE_PASSWORD='...' NEWHIRE_PASSWORD='...' ADMIN_PASSWORD='...' \
   python -m db.reset
   ```

   Run the same command again to reset the live data (for example after class testing).
3. **Render:** New → Web Service → this repository, branch `main`, region Frankfurt, runtime Python, instance
   type Free.
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - Environment variables: `DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`
   - The Python version comes from `.python-version`.

Every push to `main` redeploys. A free service sleeps after 15 minutes without traffic and takes about a
minute to wake up, so open the site a few minutes before a demo.

## Sample documents

| Document | Project | Visible to |
|----------|---------|------------|
| Employee Handbook Leave and Hybrid Work | GENERAL | everyone |
| Quality Procedure Deliverable Review and Document Control | GENERAL | everyone |
| Site Health and Safety Rules (`.txt`) | GENERAL | everyone |
| IT Security and AI Tools Policy | GENERAL | everyone |
| Project A Linha Verde Metro Extension Execution Plan | A | employee, admin (not newhire) |
| Project A Design Review Minutes 2026-09-24 | A | employee, admin (not newhire) |
| Project B Offshore Wind Tender Bid Strategy CONFIDENTIAL | B | admin only |

## Demo questions

Log in as `employee`. These are different from the example questions on the welcome screen.

1. *How many days of annual leave can I carry over to next year, and until when can I use them?*
   → 5 days, to be used by 31 March (Employee Handbook).
2. *What settlement triggers a red alert on the Linha Verde project, and who has to be notified?*
   → above 20 mm or a crack wider than 2 mm; the Project Director and Eng. Paulo Mendes within 2 hours.
3. *I am visiting the Linha Verde site next week. Which timesheet code do I use, and what do I need to do in
   SafeSite before and during the visit?* → LVM-500, plus the SafeSite booking and check-in rules. This one
   combines two documents.
4. *Does Contoso offer a company car or a car allowance?* → **No answer found.**
5. *What is our walk-away price for the Costa Norte offshore wind tender?* → **blocked**: the employee gets
   "No answer found."; `admin` gets 5.9 million EUR from the Project B document.

## Tests

```bash
pip install -r requirements-tests.txt
pytest
```

`tests/test_permissions.py` logs in as `employee`, asks about the Project B bid price, and checks that no
Project B text or citation appears in the response. It uses a fake LLM that echoes back the whole prompt it
received, so any leaked document would show up. No API key is needed.

The tests use the local database in `TEST_DATABASE_URL` (default `postgresql://localhost/keystone_test`) and
reset it before every test, with the test passwords `employee123`, `newhire123` and `admin123`.

## Swapping the LLM provider

All LLM calls go through `generate(system_prompt, user_prompt)` in `app/llm.py`. To change provider, replace
`_call_gemini()` there.
