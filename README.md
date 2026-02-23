# Event Calendar (Helsinki GSE seminars)

A lightweight calendar tool that runs every **Monday**, scrapes seminar events from:

- https://www.helsinkigse.fi/events

…and emails subscribers a weekly digest where they can choose which events to add to their calendars (Outlook / Google Calendar / Apple Calendar).

## What it does

- Scrapes the events page and extracts seminar event details (title, date/time, location, description, link).
- Deduplicates events so the same seminar isn’t re-sent every week.
- Sends an email to subscribers with a list of upcoming seminars.
- Provides **Add to calendar** links via standard `.ics` files (works across Outlook, Google Calendar, and Apple Calendar).

## Planned high-level architecture

- **Scheduler**: weekly job (Monday) to fetch + parse events.
- **Storage**: persist subscribers and previously-seen events (DB or a lightweight store).
- **Mailer**: send email digests (SMTP or an email provider).
- **Calendar**: generate `.ics` per event (and/or a combined weekly `.ics`).

## Notes / constraints

- Be polite when scraping (rate-limit requests) and respect the website’s terms/robots policy.
- Times/timezones should be handled consistently (Europe/Helsinki).

## Setup (to be implemented)

When code is added, this project will likely need environment variables for:

- Email sending (SMTP host/user/pass or API key)
- Subscriber storage (database connection)
- App base URL (for links in emails)

## Status

Repository initialized; implementation in progress.
