"""CLI entry point: scrape events and optionally store/email them."""

import argparse
import datetime
import json
import logging
import os
import sys

from dotenv import load_dotenv

from scraper.scraper import scrape_all_events

load_dotenv()  # reads .env file from project root

MONTHS = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape Helsinki GSE events")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only scrape the first N events (useful for testing)",
    )
    parser.add_argument(
        "--store", action="store_true",
        help="Upsert scraped events into Supabase (requires SUPABASE_URL and SUPABASE_KEY)",
    )
    parser.add_argument(
        "--send-test", metavar="EMAIL",
        help="Send a test digest email to this address (requires SENDGRID_API_KEY and EMAIL_FROM)",
    )
    parser.add_argument(
        "--preview-html", metavar="FILE",
        help="Write the digest HTML to a file for local preview (no email sent)",
    )
    parser.add_argument(
        "--send-digests", action="store_true",
        help="Send digest emails to all active subscribers (production mode)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    log = logging.getLogger(__name__)

    events = scrape_all_events(limit=args.limit)
    output = [e.to_dict() for e in events]
    print(json.dumps(output, indent=2))

    if args.store:
        from scraper.db import upsert_events
        upsert_events(events)

    if args.preview_html or args.send_test:
        from scraper.email_template import render_digest
        html = render_digest(events, unsubscribe_url="#")

        if args.preview_html:
            with open(args.preview_html, "w", encoding="utf-8") as f:
                f.write(html)
            log.info("Preview written to %s", args.preview_html)

        if args.send_test:
            from scraper.email_sender import send_digest
            today = datetime.date.today()
            subject = f"Helsinki GSE Seminars — Week of {today.day} {MONTHS[today.month]} {today.year}"
            ok = send_digest(args.send_test, subject, html)
            if ok:
                log.info("Test email sent to %s", args.send_test)
            else:
                log.error("Failed to send test email")
                sys.exit(1)

    if args.send_digests:
        from scraper.db import get_active_subscribers, get_unsent_events, mark_sent
        from scraper.email_sender import send_digest
        from scraper.email_template import render_digest
        from scraper.tokens import generate_token

        base_url = os.environ["APP_BASE_URL"].rstrip("/")
        today = datetime.date.today()
        subject = f"Helsinki GSE Seminars — Week of {today.day} {MONTHS[today.month]} {today.year}"
        subscribers = get_active_subscribers()
        log.info("Sending digests to %d active subscribers", len(subscribers))

        for sub in subscribers:
            unsent = get_unsent_events(sub.id)
            if not unsent:
                log.info("No unsent events for %s — skipping", sub.email)
                continue

            token = generate_token(sub.email, "unsubscribe")
            unsub_url = f"{base_url}/unsubscribe?email={sub.email}&token={token}"
            html = render_digest(unsent, unsubscribe_url=unsub_url)

            ok = send_digest(sub.email, subject, html, unsubscribe_url=unsub_url)
            if ok:
                mark_sent(sub.id, [e.event_hash for e in unsent])
                log.info("Sent %d events to %s", len(unsent), sub.email)
            else:
                log.error("Failed to send digest to %s", sub.email)


if __name__ == "__main__":
    main()
