# Keystone: Contoso knowledge assistant

A university prototype of a company knowledge chatbot (the "Knowledge Finder" brief) for a fictional engineering
consultancy, Contoso Engineering Consultants. Employees ask questions in plain language and get
answers based **only** on company documents, with citations. If the answer isn't in the documents, the bot
replies "No answer found."

## How it works

1. At startup, every `.txt` / `.md` / `.pdf` in `.docs/` is loaded into SQLite (only if the database has no
   documents yet). The project is read from the `Project / visibility tag:` line (GENERAL, A or B).
2. When a user asks a question, the documents they may see are selected **in the SQL query**
   (`documents JOIN user_projects`). Admins see all documents.
3. The full text of those documents and the question go into one prompt (no embeddings or vector database).
   The model must reply with JSON: `{"answer": "...", "sources": ["doc name", ...]}`.
4. The reply is parsed safely. Malformed JSON falls back to the raw text, and any cited source the user can't
   see is dropped.

## Chat history

Every question and answer is saved per user in SQLite (`conversations` and `messages` tables), so your chats
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
  - an answer with no citations (other than "No answer found.") is hidden if *any* document from its prompt is
    no longer visible, because it could contain text from any of them;
  - if your access comes back, the answer reappears.
  This relies on the model citing the documents it used, which the system prompt requires.

## Project structure

```
app/
  config.py      settings read from .env (pydantic-settings)
  db.py          SQLite schema, demo users, password hashing
  documents.py   text extraction (txt/md/pdf), seeding, permission-filtered queries
  llm.py         generate(): the single LLM entry point (Gemini or Ollama), 429 retry
  chat.py        prompt building and JSON parsing
  auth.py        login, session cookie, admin check
  conversations.py  saved chats: list, open, save question/answer, delete, rate
  main.py        FastAPI routes
static/          plain HTML/CSS/JS (chat, login, admin)
tests/           pytest tests (no real LLM calls)
.docs/           seed documents (the document name is the file name with underscores as spaces)
```

## Setup

Requires Python 3.12+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then put your Gemini key in .env
```

`.env`:

```
LLM_PROVIDER=gemini
GEMINI_API_KEY=<your key from https://aistudio.google.com/apikey>
GEMINI_MODEL=gemini-3.5-flash-lite
```

Optional local model (no API key, no internet):

```bash
# install Ollama from https://ollama.com, then:
ollama pull llama3.2
```

```
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
OLLAMA_URL=http://localhost:11434
```

## Run

```bash
uvicorn app.main:app --reload
```

Open http://localhost:8000.

| User       | Password      | Can see                       |
|------------|---------------|-------------------------------|
| `employee` | `employee123` | GENERAL + Project A documents |
| `admin`    | `admin123`    | everything + `/admin` page    |

To reset the database (and reload documents from `.docs/`), stop the server and delete `knowledge_finder.db`.

## Sample documents

| Document | Project | Visible to |
|----------|---------|------------|
| Employee Handbook Leave and Hybrid Work | GENERAL | everyone |
| Quality Procedure Deliverable Review and Document Control | GENERAL | everyone |
| Site Health and Safety Rules (`.txt`) | GENERAL | everyone |
| IT Security and AI Tools Policy | GENERAL | everyone |
| Project A Linha Verde Metro Extension Execution Plan | A | employee, admin |
| Project A Design Review Minutes 2026-09-24 | A | employee, admin |
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

## Swapping the LLM provider

All LLM calls go through `generate(system_prompt, user_prompt)` in `app/llm.py`. To add a provider, write
a `_call_<provider>()` function and select it there.
