# Live demo script (5 minutes)

Every question and expected answer below was run on the live site. Times are a guide; the total is 5:00.

## Before the session

- [ ] **Reset the live data** (deletes test chats, ratings and uploads; restores the 3 accounts and 7 documents).
      The Neon connection string is in the Neon console under Connect → Pooled connection:

      DATABASE_URL='<Neon pooled connection string>' \
      EMPLOYEE_PASSWORD=employee123 NEWHIRE_PASSWORD=newhire123 ADMIN_PASSWORD=admin123 \
      .venv/bin/python -m db.reset

- [ ] **Wake the site 5 minutes before:** open https://feup-asi-keystone-chatbot-2026.onrender.com (the free plan
      sleeps after 15 minutes and takes about a minute to wake up).
- [ ] **Window 1 (normal):** the login page, not logged in.
- [ ] **Window 2 (private):** logged in as `admin` / `admin123`, on the Admin page.
- [ ] **File for the upload** on the Desktop, `Company_Car_Policy.txt`:

      printf 'Contoso Company Car Policy. Project / visibility tag: GENERAL.\nContoso does not offer company cars. Employees receive a mobility allowance of 150 EUR per month.\n' > ~/Desktop/Company_Car_Policy.txt

- [ ] Browser zoom at 125% so the class can read the screen.

## Script

| Time | Window | Do | Say |
|------|--------|----|-----|
| 0:00 | 1 | Show the login page | "Keystone answers employees' questions only from the company's own documents, names its sources, and says 'No answer found' instead of guessing. Each person only sees what they are allowed to see." |
| 0:30 | 1 | Log in as `employee` with a wrong password → error; then `employee123` | "Login with a role. A wrong password is rejected." (M4) |
| 0:50 | 1 | Ask: *How many days of annual leave can I carry over to next year?* → "5 days", source chip | "Every answer names its source document." (M1) |
| 1:15 | 1 | Click the source chip → the document opens on the right; close it | "You can check the source yourself." |
| 1:30 | 1 | Ask: *And until when can I use them?* → "31 March" | "It understands follow-up questions in the same chat." (S2) |
| 1:45 | 1 | Click thumbs up on the first answer | "Employees rate answers." (S1) |
| 1:55 | 1 | New chat: *What is our walk-away price for the Costa Norte offshore wind tender?* → "No answer found." | "That's in a confidential Project B document. This employee has no access, so the AI never even receives that text: the filter is in the database query." (M3) |
| 2:30 | 2 | Admin page: point at **Answer ratings** (the thumbs up from 1:45), then upload `Company_Car_Policy.txt` to **General** | "The admin sees every rating and manages the documents and who can see them." (S1, M5) |
| 3:00 | 1 | New chat: *Does Contoso offer a company car or a car allowance?* → "150 EUR per month", source "Company Car Policy" | "The new document is searchable right away." (M5) |
| 3:20 | 2 | Delete "Company Car Policy" | |
| 3:30 | 1 | Ask again in the same chat: *Does Contoso offer a mobility allowance?* → "No answer found." | "Deleted documents are never used again." (M5, M2) |
| 3:45 | 1 | Open DevTools → device toolbar (phone) and show the chat and the menu | "It works on a phone." |
| 4:10 | — | Show the repository on GitHub: `SPEC.md`, `CLAUDE.md`, the commit history, `docs/` | "Built with an LLM agent: the spec and the rules came first, then one flow per commit. 73 automated tests, including a permission-leak test, and a 22-step browser checklist run on desktop and phone." |
| 4:45 | — | Back to the app | "Ten PostgreSQL tables with primary and foreign keys, hosted on Render and Neon. Questions?" |

## If something goes wrong

| Problem | What to do |
|---------|------------|
| The site is waking up (loading page) | Wait; say "free hosting sleeps when idle, this is the cold start". Next time open it earlier. |
| "Keystone is busy, please try again in a minute." | Click **Retry** after a few seconds; it is the free Gemini limit, and the message itself is part of the error handling. |
| An answer is worded differently from the script | Expected: the AI phrases answers freely. Point at the source chip. |
| Running late | Skip the follow-up question (1:30) and the phone view (3:45). |
