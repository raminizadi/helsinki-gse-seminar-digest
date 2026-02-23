# Helsinki GSE Seminar Digest

A fully automated weekly email digest of Helsinki GSE seminar events.

**Subscribe:** https://helsinki-gse-seminar-digest.vercel.app/

Every Monday at 08:00 Helsinki time, subscribers receive an email listing that week's seminars with one-click **Add to Google Calendar**, **Add to Outlook**, and **Download .ics** buttons for each event.

## How it works

1. **Scraper** pulls events from [helsinkigse.fi/events](https://www.helsinkigse.fi/events) using BeautifulSoup
2. Events are stored in **Supabase** (Postgres)
3. **GitHub Actions** cron job runs every Monday — scrapes new events, then sends digests to all active subscribers
4. Subscribers manage themselves via the **Flask app on Vercel** (subscribe, confirm, unsubscribe)

## Architecture

| Component | Technology | Cost |
|---|---|---|
| Weekly scrape + email | GitHub Actions cron | $0 |
| Subscribe/unsubscribe | Flask on Vercel | $0 |
| Database | Supabase (Postgres) | $0 |
| Transactional email | SendGrid | $0 |
| Calendar links | Google/Outlook deep links + .ics | — |

## Project structure

```
src/scraper/
  scraper.py          # Scrapes event pages from helsinkigse.fi
  models.py           # Event and Subscriber dataclasses
  db.py               # Supabase CRUD (events, subscribers, sent_log)
  email_template.py   # HTML email rendering (inline CSS)
  email_sender.py     # SendGrid integration (digest + confirmation emails)
  calendar_links.py   # Google Calendar / Outlook URL generation
  tokens.py           # HMAC token generation for confirm/unsubscribe
  cli.py              # CLI entry point (scrape, store, send-test, send-digests)

api/
  index.py            # Flask app (Vercel entry point)

templates/            # HTML pages (subscribe, success, confirmed, unsubscribed, error)

.github/workflows/
  weekly-digest.yml   # Monday cron job

migrations/
  001_initial.sql     # Database schema
```

## Subscription flow

1. User enters email at the subscribe page
2. Confirmation email sent (double opt-in, GDPR compliant)
3. User clicks confirm link — subscription activated
4. Every Monday: digest email with that week's events
5. One-click unsubscribe link in every email footer

## CLI usage

```bash
# Scrape all events and print JSON
scrape-events

# Scrape and store in Supabase
scrape-events --store

# Preview digest as local HTML file
scrape-events --preview-html digest.html

# Send test digest to a specific email
scrape-events --send-test you@example.com

# Send weekly digests to all active subscribers (production)
scrape-events --send-digests
```

## Environment variables

Set in `.env` for local dev, in Vercel dashboard for production, and as GitHub Actions secrets for the cron job:

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | Supabase service role key |
| `SENDGRID_API_KEY` | SendGrid API key (Mail Send permission) |
| `EMAIL_FROM` | Verified sender email address |
| `SECRET_KEY` | HMAC key for signing confirm/unsubscribe tokens |
| `APP_BASE_URL` | Production URL (https://helsinki-gse-seminar-digest.vercel.app) |

## Email features

- Category badges per event (e.g., "Environmental Economics", "PhD Seminar")
- Calendar titles use "Series: Speaker" format (e.g., "Environmental Economics Seminar: Benjamin Hattemer")
- Google Calendar, Outlook, and .ics download buttons
- Per-subscriber unsubscribe links with HMAC tokens
- Digest scoped to current week (Monday–Sunday)

## Local development

```bash
# Install dependencies
pip install -e .

# Run Flask app locally
python -c "from api.index import app; app.run(debug=True)"
# → http://localhost:5000
```
