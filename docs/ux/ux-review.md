# UX and UI review

This review covers the six points in the Assignment 2 brief: hierarchy, contrast, spacing, consistency,
accessibility and behaviour on a phone-sized screen. It covers every screen (login, chat, source drawer, admin
documents, admin ratings) in light and dark mode at desktop width (1280 × 800) and at phone width (390 × 844).

## Method

1. Screenshots of every screen were taken with a headless Chromium browser against the running app, with real
   Gemini answers: `before/` holds the screens before the review, `after/` the same screens after the fixes.
2. The LLM agent (Claude) reviewed each screenshot against the six points.
3. Colour contrast was measured, not estimated: each text and background pair was checked against the WCAG 2.1 AA
   minimum of 4.5:1 for normal text.
4. Each fix was applied, the automated tests were run (73 passed), and the screenshots were taken again.

## Findings and changes

| # | Point                   | Finding (before)                                                                                                                       | Change (after)                                                                                                  | Screens                                              |
| - | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| 1 | Phone, consistency      | At phone width the admin tables were wider than the screen: document names wrapped one letter per line and the page scrolled sideways. | Below 640 px each document and each rating becomes a card, with a small label above every value.                | `08-admin-phone`                                   |
| 2 | Contrast, accessibility | Dark mode: white text on the Log in, Upload and send buttons was 3.16:1.                                                               | Buttons use a darker blue in dark mode: 5.90:1.                                                                 | `01-login-desktop-dark`, `08-admin-desktop-dark` |
| 3 | Contrast                | Light mode: grey table headers were 4.28:1 and the "Project A" badge 4.48:1.                                                           | Grey text darkened slightly (4.74:1 on the table header); badge text uses a darker blue (5.82:1).               | `08-admin-desktop`                                 |
| 4 | Accessibility           | Moving through the page with the Tab key had no consistent visible focus on buttons, chips and links.                                  | Every focusable element shows the same blue focus ring.                                                         | all                                                  |
| 5 | Hierarchy               | The source drawer showed raw Markdown (`#`, `##`), so the document's headings did not stand out.                                   | Headings are shown as bold headings without the `#` signs.                                                    | `07-chat-source-drawer-*`                          |
| 6 | Hierarchy, behaviour    | "No answer found." gave no reason and no next step.                                                                                    | A short line below it explains that the accessible documents do not cover the question and suggests what to do. | `05-chat-no-answer-*`                              |

Checked and left unchanged:

- **Hierarchy:** one clear main action per screen (Log in, the question box, Upload); answers, sources and ratings
  read top to bottom in that order.
- **Spacing:** consistent card padding (20 px) and gaps between messages on every screen.
- **Consistency:** the same card, badge and button styles on the chat and admin pages, in light and dark mode.
- **Contrast** of the other pairs: muted text 4.52:1 → 5.01:1 on the page, user bubble 5.17:1, Project B badge
  5.31:1, Helpful 5.40:1, Not helpful 6.05:1, and all dark-mode text above 4.5:1.
- **Accessibility:** every input has a label, icon buttons have an `aria-label`, the login error is announced
  (`role="alert"`), and Escape closes the sidebar and the source drawer.

## Comparison with the Assignment 1 mockups

Assignment 1 slides 8 and 9 were screenshots of the prototype; slide 10 held wireframes for the admin and meeting
screens.

| Screen                                | Assignment 1                                                              | MVP                                                                                | Difference                                                                                 |
| ------------------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Login (slide 8)                       | Username, password, two roles                                             | Same, plus clear messages for a wrong password, a server failure and no connection | Same layout                                                                                |
| Chat (slide 9)                        | Chat history, question box, answer with source chips, thumbs up/down      | Same, plus the source drawer, the "No answer found." explanation and phone layout  | Same layout                                                                                |
| Admin documents (slide 10, wireframe) | Columns Document · Project · Visible to; Upload button at the top right | Columns Name · Project · Characters · Delete; upload form above the table       | "Visible to" is shown only through the project badge; upload is a form instead of a button |
| Admin ratings                         | Not in the mockups (S1 said "visible to the admin")                       | Ratings section below the documents                                                | New screen                                                                                 |
| Meeting summary (slide 10, wireframe) | Upload transcript, decisions, action items                                | Not built                                                                          | Deferred with S3                                                                           |
