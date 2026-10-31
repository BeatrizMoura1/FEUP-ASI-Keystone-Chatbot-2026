# Keystone: rules for the LLM agent

Keystone is a university project (ASI, Assignment 2 MVP). `SPEC.md` is the source of scope: read it before any
change, and build nothing it does not list. This project follows its own style below, not any company
standard.

## Way of working

- One flow at a time, in the build order of `SPEC.md` section 7. Stop after each step and wait for a go.
- Explain the change and the files it touches before writing code. Raise any new library, folder, table or
  pattern first; do not add one silently.
- Every change passes `pytest` before it is shown, and is checked by hand in the browser when it touches a
  screen. Report failures as they are, with the output.
- No git commit, push or deploy without an explicit go for that action.
- Keep diffs small and limited to the step.

## Stack and structure

- Python 3.12, FastAPI, psycopg 3, PostgreSQL, plain HTML/CSS/JS, Gemini. No ORM, no frontend framework, no
  vector database.
- Follow the folder structure in `SPEC.md` section 6. Routes live in `app/routes/`, one module per area (pages,
  account, chat, admin); `app/main.py` only creates the app. Logic stays in the module that owns it.
- Database changes go into `db/schema.sql`; seed data and test accounts go into `db/reset.py`.

## Security and permissions

- The documents a user may see are filtered in SQL before any text reaches the LLM. Never filter after the
  LLM call.
- The Project B leak test (`tests/test_permissions.py`) must always pass.
- Every query that reads documents filters `deleted_at IS NULL`.
- Every chat, message and rating query filters on the logged-in user's id, except the admin ratings view.
- Secrets (Gemini key, database URL, test account passwords) come only from environment variables, never from
  code, tests or git. `.env` stays in `.gitignore`.
- SQL uses parameters (`%s`), never string formatting with user input.

## LLM calls

- All LLM calls go through `generate()` in `app/llm.py`.
- Answers come only from the documents in the prompt, with the documents cited; otherwise "No answer found.".
- Tests never call Gemini; they replace `generate` with a fake.

## Code style (as in the existing code)

- Settings live only in `app/config.py` (pydantic-settings `Settings`, one `Field` with an `alias` per
  variable); never read environment variables elsewhere.
- NumPy-style docstrings on every function, with `Parameters`, `Returns` and `Raises` where they apply.
- Type hints on every function; modern typing (`list[str]`, `X | None`).
- Descriptive names (`document_text`, `allowed_document_ids`), no one-letter names.
- Logging through `logging.getLogger("knowledge_finder")`, never `print`. Log failures with context.
- Errors returned to the browser are short, plain messages; details go to the log.

## Tests

- pytest, with fixtures in `tests/conftest.py` and a fake LLM; run with `pytest -q`.
- Tests run against a local PostgreSQL test database, never against Neon.
- Every acceptance criterion in `SPEC.md` section 2 marked "Automated test" has a test.

## UI

- Every screen works at phone width (360 px) and on a desktop.
- Check hierarchy, contrast, spacing, consistency and accessibility (labels, focus, keyboard use) on every
  screen change.
- Every error a user can cause shows a clear message from `SPEC.md` section 4.
