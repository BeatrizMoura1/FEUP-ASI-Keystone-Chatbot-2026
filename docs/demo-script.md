# Live demo script (5 minutes)

Every question and expected answer below was run on the live site, except the unanswered-questions step (2:25),
which was added with S4 and checked on a local copy; rehearse it once on the live site. Times are a guide; the
total is 5:00.

## Before the session

- [ ] **Reset the live data** (deletes test chats, ratings and uploads; restores the accounts and the 7
      documents). Get the Neon connection string from the Neon console under Connect → Pooled connection, then run
      these one at a time:

      export DATABASE_URL='<Neon pooled connection string>'
      .venv/bin/python -c "from app.config import settings; print(settings.database_url.split('@')[-1])"
      EMPLOYEE_PASSWORD=employee123 NEWHIRE_PASSWORD=newhire123 ADMIN_PASSWORD=admin123 .venv/bin/python -m db.reset
      unset DATABASE_URL

      The second line must print the Neon host (`ep-…neon.tech/…`), not `localhost/keystone`; if it prints
      `localhost`, stop, because the reset would go to the local database. The reset logs `users: 13`.

- [ ] **Wake the site 5 minutes before:** open https://feup-asi-keystone-chatbot-2026.onrender.com (the free plan
      sleeps after 15 minutes and takes about a minute to wake up), log in as `employee1` and ask one question so
      the first connection to Gemini is made before the demo. Delete that chat afterwards.
- [ ] **Window 1 (normal):** the login page, not logged in.
- [ ] **Window 2 (private):** logged in as `admin` / `admin123`, on the Admin page.
- [ ] **File for the upload** on the Desktop, `Company_Car_Policy.txt`:

      printf 'Contoso Company Car Policy. Project / visibility tag: GENERAL.\nContoso does not offer company cars. Employees receive a mobility allowance of 150 EUR per month.\n' > ~/Desktop/Company_Car_Policy.txt

- [ ] **Accounts for the class** ready to paste in the chat at the end: `employee1` to `employee10`, each with its
      username as the password (General and Project A documents).
- [ ] Browser zoom at 125% so the class can read the screen.

## Script

| Time | Window | Do | Say |
|------|--------|----|-----|
| 0:00 | 1 | Show the login page | "Keystone answers employees' questions only from the company's own documents, names its sources, and says 'No answer found' instead of guessing. Each person only sees what they are allowed to see." |
| 0:25 | 1 | Log in as `employee` with a wrong password → error; then `employee123` | "Login with a role. A wrong password is rejected." (M4) |
| 0:45 | 1 | Ask: *How many days of annual leave can I carry over to next year?* → "5 days", source chip | "Every answer names its source document." (M1) |
| 1:05 | 1 | Click the source chip → the document opens on the right; close it | "You can check the source yourself." |
| 1:15 | 1 | Ask: *And until when can I use them?* → "31 March" | "It understands follow-up questions in the same chat." (S2) |
| 1:30 | 1 | Click thumbs up on the first answer | "Employees rate answers." (S1) |
| 1:35 | 1 | New chat: *Does Contoso offer a company car or a car allowance?* → "No answer found." | "No document covers this, so it says so instead of inventing an answer." (M2) |
| 1:55 | 1 | New chat: *What is our walk-away price for the Costa Norte offshore wind tender?* → "No answer found." | "That's in a confidential Project B document. This employee has no access, so the AI never even receives that text: the filter is in the database query." (M3) |
| 2:25 | 2 | Refresh the Admin page: point at **Unanswered questions** (both questions, by `employee`), then **Answer ratings** (the thumbs up) | "The admin sees what employees asked that the documents could not answer. The company car is a missing document. The tender is restricted on purpose." (S4, S1) |
| 2:45 | 2 | Upload `Company_Car_Policy.txt` to **General** | "So the admin adds the missing document and chooses who can see it." (M5) |
| 3:00 | 1 | Ask again in the company-car chat: *Does Contoso offer a company car or a car allowance?* → "150 EUR per month", source "Company Car Policy" | "The new document is searchable right away." (M5) |
| 3:15 | 2 | Delete "Company Car Policy" | |
| 3:25 | 1 | Ask in the same chat: *Does Contoso offer a mobility allowance?* → "No answer found." | "Deleted documents are never used again." (M5, M2) |
| 3:40 | 1 | Open DevTools → device toolbar (phone) and show the chat and the menu | "It works on a phone." |
| 4:00 | — | Show the repository on GitHub: `SPEC.md`, `CLAUDE.md`, the commit history, `docs/` | "Built with an LLM agent: the spec and the rules came first, then one flow per commit. 85 automated tests, including a permission-leak test, and a 23-step browser checklist run on desktop and phone." |
| 4:40 | — | Back to the app; paste the `employee1` to `employee10` accounts in the chat | "Ten PostgreSQL tables with primary and foreign keys, hosted on Render and Neon. You can try it now with these accounts. Questions?" |

## If something goes wrong

| Problem | What to do |
|---------|------------|
| The site is waking up (loading page) | Wait; say "free hosting sleeps when idle, this is the cold start". Next time open it earlier. |
| "The AI service failed, please try again." | Click **Retry**. Keystone already retried a brief Gemini failure twice; if it still fails, Gemini itself is down for a moment. Say "the error is handled: nothing is lost and the question stays on screen". |
| "Keystone is busy, please try again in a minute." | Click **Retry** after a few seconds; it is the free Gemini limit, and the message itself is part of the error handling. |
| An answer is worded differently from the script | Expected: the AI phrases answers freely. Point at the source chip. |
| Classmates all ask at once and answers slow down | Expected: the free Gemini plan allows about 10–15 questions a minute, and Keystone waits and retries instead of failing. Ask them to take turns. |
| Running late | Skip the follow-up question (1:15) and the phone view (3:40). |
