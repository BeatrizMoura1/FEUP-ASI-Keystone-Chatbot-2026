# Manual test checklist

One row per screen and flow of the MVP, linked to the user stories in `SPEC.md`. Each row was run in a real
browser (Chromium) against the live site, https://feup-asi-keystone-chatbot-2026.onrender.com, at desktop width
(1280 × 800) and at phone width (390 × 844), on 31 October 2026, with the database reset before each run. The
last column is for the check by hand before submission.

Test accounts: `employee` / `employee123` (General + Project A), `newhire` / `newhire123` (General only),
`admin` / `admin123` (everything).

## Checklist

| ID | Story | Steps | Expected result | Desktop | Phone | Answer time (desktop / phone) | By hand |
|----|-------|-------|-----------------|---------|-------|-------------------------------|---------|
| MT-01 | M4 | Log in as `employee` with a wrong password | "Wrong username or password." | Pass | Pass | | ☐ |
| MT-02 | M4 | Log in as `employee` / `employee123` | Chat opens with "Hi employee, I'm Keystone" | Pass | Pass | | ☐ |
| MT-03 | M4 | As `employee`, open `/admin` | Sent back to the chat | Pass | Pass | | ☐ |
| MT-04 | M1 | Ask "How many days of annual leave can I carry over to next year?" | "5 days", with the Employee Handbook source chip | Pass | Pass | 1.8 s / 1.4 s | ☐ |
| MT-05 | M1, S2 | Ask "And until when can I use them?" in the same chat | "31 March" (the follow-up is understood) | Pass | Pass | 3.0 s / 2.9 s | ☐ |
| MT-06 | M1 | Click the source chip | Drawer opens with the document; headings shown without `#` | Pass | Pass | | ☐ |
| MT-07 | M3 | New chat: "What is our walk-away price for the Costa Norte offshore wind tender?" | "No answer found." plus the explanation line (Project B is hidden from `employee`) | Pass | Pass | 3.6 s / 2.1 s | ☐ |
| MT-08 | M2 | New chat: "Does Contoso offer a company car or a car allowance?" | "No answer found." | Pass | Pass | 3.7 s / 3.3 s | ☐ |
| MT-09 | S1 | Thumbs up on the leave answer | "Thanks for your feedback"; the thumb stays selected | Pass | Pass | | ☐ |
| MT-10 | S2 | Look at the chat list | 3 chats under "Today" | Pass | Pass | | ☐ |
| MT-11 | S2 | Reopen the leave chat | Both answers, their sources and the thumbs up come back | Pass | Pass | | ☐ |
| MT-12 | S2 | Delete the company-car chat (bin icon, confirm) | It disappears from the list | Pass | Pass | | ☐ |
| MT-13 | S2, M4 | Log out, log in again | Login page after logout; the 2 remaining chats are still there | Pass | Pass | | ☐ |
| MT-14 | M3 | Log in as `newhire`, ask "What settlement triggers a red alert on the Linha Verde project?" | "No answer found." (Project A is hidden from `newhire`) | Pass | Pass | 2.8 s / 1.4 s | ☐ |
| MT-15 | M5 | Log in as `admin`, open Admin | 7 documents; the project list starts on "General (everyone)" | Pass | Pass | | ☐ |
| MT-16 | M5 | Upload `Company_Car_Policy.txt` to General | "Uploaded "Company Car Policy" to GENERAL."; it appears in the list | Pass | Pass | | ☐ |
| MT-17 | M5 | Upload a `.png` file | "Error: Unsupported file type '.png'…" | Pass | Pass | | ☐ |
| MT-18 | M5 | As `employee`, ask "Does Contoso offer a company car or a car allowance?" | Answer with "150 EUR per month", source "Company Car Policy" | Pass | Pass | 2.4 s / 2.2 s | ☐ |
| MT-19 | M5 | As `admin`, delete "Company Car Policy"; as `employee`, ask "Does Contoso offer a mobility allowance?" | Removed from the list; "No answer found." | Pass | Pass | 1.1 s / 1.1 s | ☐ |
| MT-20 | S1 | As `admin`, look at Answer ratings | The thumbs up from MT-09: "1 rating · 1 helpful · 0 not helpful" | Pass | Pass | | ☐ |
| MT-21 | Errors | Go offline (DevTools → Network → Offline), ask a question; go online, click Retry | "Could not reach Keystone…" with Retry; Retry gives the cited answer | Pass | Pass | | ☐ |
| MT-22 | Errors | Go offline on the login page and log in | "Could not reach Keystone…"; the Log in button works again | Pass | Pass | | ☐ |

**Result:** 22 of 22 checks passed on desktop and on phone. The run showed one wording bug, fixed afterwards: the
ratings summary said "1 ratings" (MT-20); it now says "1 rating".

**Answer time (M1, "median under 10 s"):** 14 timed questions, from the click to the answer on screen: median
**2.3 s**, slowest 3.7 s.

## Several users at once

Six users (3 × `employee`, 2 × `newhire`, 1 × `admin`) logged in to the live site at the same time and each asked
2 questions at the same moment, 12 requests in one burst.

| Measure | Result |
|---------|--------|
| Answers | 12 of 12 answered (HTTP 200), no "Keystone is busy" errors |
| Answer time under load | median 6.4 s, slowest 7.3 s (under 10 s) |
| Permissions | `newhire` got "No answer found." for Linha Verde while `employee` got the answer; only `admin` got the Project B price |

## Not covered by this checklist

- **The "Keystone is busy" message on the live site.** It needs the Gemini free-tier limit to be reached; it is
  covered by the automated test `test_rate_limit_retries_then_returns_429`.
- **The first visit after the site has been idle.** Render's free plan takes about a minute to wake up after 15
  minutes without traffic; open the site a few minutes before a demo.
