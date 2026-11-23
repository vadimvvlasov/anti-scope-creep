# Product analytics

Which acquisition channel brings people who use the product and would pay for it. The
frontend sends a few funnel events to our own backend (`POST /events`), which stores them in
the `events` table next to the accounts. No third-party analytics service.

Why not PostHog or similar: its free tier would cover our volume, but ad blockers block
known analytics hosts, and the early audience (Hacker News, Indie Hackers, developers)
often runs one. The app's own API is not on those block lists, and no new data processor
appears in the data policy.

## The funnel

| Step | Event | Properties | Where it fires |
|---|---|---|---|
| Visit | `pageview` | — | every route change |
| Sign-up | `signup_completed` | — | after a successful registration |
| Activation | `analysis_started` | `input`: `file`, `text` or `retry`; `goal`: the answer to the goal question (`before_signing`, `negotiating`, `already_signed`, `just_curious`), left out when skipped | after the API accepts an upload or a retry |
| Value | `report_exported` | `format`: `pdf` or `docx` | after a report download |
| Interest in paying | `pro_cta_clicked` | `placement`: `header` or `daily_limit` | the Pro dialog opens |
| Intent to pay | `pro_waitlist_joined` | `placement`, `price_usd` | the waitlist button in the Pro dialog |
| Interest in photo scanning | `scan_photo_clicked` | `placement`: `scan_photo`, `screen`: `mobile` or `desktop` | the "Photograph a contract" dialog opens |

Every event also carries `path` (no query string) and the attribution of the browser tab:
`utm_source`, `utm_medium`, `utm_campaign`, `utm_content` from the first page's URL, and
`referrer_host` when the visitor came from another site. After sign-up or login, one
`identify` event (`anon_id`: the tab's anonymous ID) links the visitor to the account.

## What is never sent

Contract text, titles, file names, findings, email drafts, account emails, tokens. Events
are typed in `frontend/src/services/analytics.ts` and the properties above are the only
ones the code sends. The backend accepts only the event names and property keys above, with
values up to 100 characters (`input`, `format`, `placement`, `screen` and `goal` only from their fixed
values), and rejects anything else with `422`. IP addresses are not stored.

## How it is sent

- No SDK: one `POST /events` per event to the API the app already uses. No login needed,
  no autocapture, no session recording, no cookies. The backend answers `204`.
- IDs live in `sessionStorage`, so they end with the browser tab. A visitor is anonymous
  until they sign up or log in; then the events use the account ID (a UUID, not the email).
- Off unless `VITE_ANALYTICS=true` at build time, and always off with the mock API: local
  runs, tests and e2e send nothing. A failed request never affects the app.
- Spam limits: 30 events per client IP per minute and 5,000 per UTC day in total
  (`backend/app/event_limits.py`, in memory). Extra events are dropped quietly. The IP is
  read from the last `X-Forwarded-For` entry (set by the Tailscale proxy in front of the
  backend, which a client cannot forge) and only counted, never stored.

## The Pro plan is a demand test

There is no paid plan. The Pro button (header, and next to the daily-limit error) opens a
dialog with a price ($19/month) and planned features, says plainly that Pro is not
available and nothing is charged, and offers a waitlist. A click on the waitlist is the
signal. To write to the people on the waitlist, join the `distinct_id` of
`pro_waitlist_joined` events with `users.id`: the Pro button is only on signed-in pages, so
these events always carry an account ID.

## The photo scan is a demand test

There is no photo scanning. On narrow (phone) screens, New Analysis shows a "Photograph a
contract" button; it opens a dialog saying the feature is not available yet. No camera is
opened and nothing is uploaded. The click is `scan_photo_clicked` (`placement`:
`scan_photo`, `screen`: `mobile` or `desktop`). It feeds one decision: whether to open the
follow-up "photo scan through the PWA, with OCR quality measured on real phone photos"
(#169). The threshold (clicks as a share of mobile analyses, over how many weeks) is set by
the owner in #169 before the button ships; below it the button is removed.

## Links for channels

Every link to the app in a post, video or listing gets its own UTM parameters, so the
channel shows up in the funnel:

```text
https://anti-scope-creep.vadimvlasov.workers.dev/?utm_source=<site>&utm_medium=<post|video|listing|comment>&utm_campaign=<what>
```

Examples: `utm_source=reddit&utm_medium=comment&utm_campaign=teardown01`,
`utm_source=tiktok&utm_medium=video&utm_campaign=clause01`,
`utm_source=producthunt&utm_medium=listing&utm_campaign=launch`. Lowercase, no spaces.

## Setup

`deploy.yml` builds the frontend with `VITE_ANALYTICS=true` for dev and prod, and the
backend migration `0004` creates the `events` table. Nothing to register anywhere.

## Reading the funnel

`scripts/funnel.sql` counts, per `utm_source` (or `referrer_host` when there is no UTM),
the visitors who reached each step in the last 14 days. Anonymous visits are joined to the
account through `identify`. Run it against the database of the environment:

```bash
psql "$DATABASE_URL" -f scripts/funnel.sql
```

Its second query is for the guest sample (X1, issue #125): visitors split by whether they opened
`/sample/*` before signing up, with their sign-ups and first analyses. A `pageview` carries the path, so
no new event is needed.

`DATABASE_URL` here is the plain `postgresql://` form (without `+psycopg`). Use the dev or
prod Neon connection string; the query only reads.
