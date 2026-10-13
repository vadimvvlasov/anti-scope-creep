# Product analytics

Which acquisition channel brings people who use the product and would pay for it. The
frontend sends a few funnel events to PostHog; the backend's database stays the source of
truth for accounts and analyses.

## The funnel

| Step | Event | Properties | Where it fires |
|---|---|---|---|
| Visit | `$pageview` | path only (no query string) | every route change |
| Sign-up | `signup_completed` | — | after a successful registration |
| Activation | `analysis_started` | `input`: `file`, `text` or `retry` | after the API accepts an upload or a retry |
| Value | `report_exported` | `format`: `pdf` or `docx` | after a report download |
| Interest in paying | `pro_cta_clicked` | `placement`: `header` or `daily_limit` | the Pro dialog opens |
| Intent to pay | `pro_waitlist_joined` | `placement`, `price_usd` | the waitlist button in the Pro dialog |

Every event also carries the attribution of the browser tab: `utm_source`, `utm_medium`,
`utm_campaign`, `utm_content` from the first page's URL, and `referrer_host` when the
visitor came from another site.

## What is never sent

Contract text, titles, file names, findings, email drafts, account emails, tokens. Events
are typed in `frontend/src/services/analytics.ts` and the properties above are the only
ones the code sends.

## How it is sent

- No SDK: one `POST` per event to PostHog's capture endpoint (`/i/v0/e/`), EU Cloud by
  default. No autocapture, no session recording, no cookies.
- IDs live in `sessionStorage`, so they end with the browser tab. A visitor is anonymous
  (`$process_person_profile: false`) until they sign up or log in; then the events use the
  account ID (a UUID, not the email), and the tab's anonymous ID is merged into it once.
- Off unless `VITE_POSTHOG_KEY` is set at build time: local runs, tests and e2e send
  nothing. A failed request never affects the app.

## The Pro plan is a demand test

There is no paid plan. The Pro button (header, and next to the daily-limit error) opens a
dialog with a price ($19/month) and planned features, says plainly that Pro is not
available and nothing is charged, and offers a waitlist. A click on the waitlist is the
signal. To write to the people on the waitlist, look up the account IDs of
`pro_waitlist_joined` events in the `users` table.

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

1. Create a PostHog project in the EU Cloud and copy its project API key (`phc_...`). It is
   a public key: it can only send events, so it lives in a variable, not a secret.
2. Set the GitHub variable `POSTHOG_KEY` in the environment that should send events (prod,
   and dev only for testing). `deploy.yml` passes it to the frontend build as
   `VITE_POSTHOG_KEY`; an empty variable turns analytics off.
3. In PostHog, build one funnel `$pageview` → `signup_completed` → `analysis_started` →
   `report_exported` → `pro_waitlist_joined`, broken down by `utm_source`.
