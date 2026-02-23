# Event Calendar (Helsinki GSE seminars)

A lightweight service that sends a **weekly Monday email digest** of Helsinki GSE seminar events scraped from:

- https://www.helsinkigse.fi/events

The email is the product: subscribers receive a list of upcoming seminars and can click **Add to calendar** buttons that open their calendar with the event pre-filled.

Important limitation: there is no single universal “add this event to any calendar” action available from plain email. The practical approach is:

- **Google Calendar**: link opens Google Calendar with event details pre-filled.
- **Outlook (web)**: link opens Outlook on the web with a pre-filled event.
- **Apple Calendar / desktop clients**: fall back to an `.ics` link that opens the calendar app’s “add event” flow (no copy/paste; user typically just confirms).

## Product goals

- **Zero manual work after launch**: subscribe/unsubscribe must be fully self-serve.
- **Lightweight + low volume**: designed for 10s–100s of subscribers.
- **Reliable Monday delivery**: schedule-driven, idempotent, and deduplicated.
- **Zero cost**: stay within free tiers; no always-on servers.

## User experience (minimal, self-serve)

1. Subscriber visits a simple subscribe page and enters their email.
2. Service sends a **confirmation email** (double opt-in).
3. Every Monday, subscriber receives the digest email.
4. Each event in the digest has **Add to Google Calendar** / **Add to Outlook** buttons (and an Apple/other fallback).
5. Every email contains a one-click **unsubscribe** link.

No accounts, no dashboards, no ongoing admin work.

## MVP architecture

Serverless-first: no always-on web server. Everything runs as scheduled jobs or on-demand functions.

| Concern | Solution | Cost |
|---|---|---|
| Weekly scrape + email job | **GitHub Actions cron** (runs every Monday) | $0 |
| Subscribe / unsubscribe | **Cloudflare Worker** (or equivalent serverless function) | $0 |
| Subscriber + event storage | **SQLite** (checked into repo or on persistent volume) or **Supabase free tier** | $0 |
| Transactional email | **SendGrid** or **Postmark** free tier | $0 |
| Add-to-calendar links | Google/Outlook deep links + `.ics` fallback served by the worker | $0 |

### Why not FastAPI + managed Postgres + Render?

At 10–100 subscribers there is no need for an always-on server or a managed database. That stack is fine but adds cost and ops surface for no benefit at this scale. If usage grows beyond free-tier limits, migrating to an always-on service is straightforward.

### Components

- **GitHub Actions workflow** (`.github/workflows/digest.yml`)
	- Cron-triggered every Monday morning.
	- Runs a Python script that: scrapes events → deduplicates → builds digest email → sends via email provider API.
- **Serverless function** (Cloudflare Worker / AWS Lambda / Vercel function)
	- `POST /subscribe` — stores email, sends confirmation link.
	- `GET /confirm?token=…` — activates subscription.
	- `GET /unsubscribe?token=…` — deactivates subscription.
	- Serves a minimal HTML subscribe page.
- **Storage**
	- `subscribers` table: email, status (pending/active/unsubscribed), confirm_token, created_at.
	- `events` table: title, starts_at, ends_at, location, description, event_hash, first_seen_at.
	- `sent_log` table: subscriber_id, event_hash, sent_at (prevents re-sending).
- **Email provider** (transactional API)
	- Sends confirmation emails and weekly digests.
	- Includes `List-Unsubscribe` header for deliverability.
- **Add-to-calendar link generation**
	- Generate **Google Calendar** and **Outlook web** “create event” links per event.
	- Provide an `.ics` fallback endpoint for Apple Calendar and other clients.

## Key implementation notes

- **Deduplication**: hash of (title + start time + source URL) as stable event identifier. Only email upcoming, not-yet-sent events.
- **Timezone**: treat all times as `Europe/Helsinki` end-to-end.
- **Scraping etiquette**: rate-limit requests; cache responses where sensible; respect robots/terms.
- **Deliverability**: use a reputable transactional provider; include `List-Unsubscribe` headers.
- **Double opt-in**: required by GDPR / CAN-SPAM. Confirmation tokens should be signed (HMAC) and time-limited.

## Configuration (env vars / secrets)

Set as GitHub Actions secrets and/or serverless function env vars:

- `APP_BASE_URL` — base URL of the serverless function (for links in emails)
- `DATABASE_URL` — connection string (if using Supabase) or path to SQLite
- `EMAIL_API_KEY` — SendGrid / Postmark API key
- `EMAIL_FROM` — verified sender address
- `SECRET_KEY` — HMAC key for signing confirm/unsubscribe tokens
- `SCRAPE_SOURCE_URL` — default: `https://www.helsinkigse.fi/events`

## Status

Repository initialized; implementation in progress.
