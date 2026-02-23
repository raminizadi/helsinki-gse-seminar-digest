"""Render the weekly digest email as HTML."""

from __future__ import annotations

import datetime
from html import escape

from scraper.calendar_links import google_calendar_url, outlook_calendar_url
from scraper.models import Event

# Inline styles (email clients strip <style> tags)
BODY_STYLE = "font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 0;"
CONTAINER_STYLE = "max-width: 600px; margin: 0 auto; background: #ffffff;"
HEADER_STYLE = "background: #1a365d; color: #ffffff; padding: 24px 32px;"
HEADER_TITLE_STYLE = "margin: 0; font-size: 22px; font-weight: 600;"
HEADER_SUB_STYLE = "margin: 8px 0 0; font-size: 14px; color: #cbd5e0; font-weight: 400;"
CONTENT_STYLE = "padding: 16px 32px 32px;"
CARD_STYLE = "border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; margin-bottom: 16px;"
DATE_STYLE = "font-size: 13px; color: #718096; margin: 0 0 6px; text-transform: uppercase; letter-spacing: 0.5px;"
TITLE_STYLE = "font-size: 17px; font-weight: 600; color: #1a202c; margin: 0 0 6px; line-height: 1.4;"
META_STYLE = "font-size: 14px; color: #4a5568; margin: 0 0 4px;"
CATEGORY_STYLE = "display: inline-block; background: #ebf4ff; color: #2b6cb0; font-size: 12px; padding: 2px 8px; border-radius: 4px; margin-right: 4px;"
FILTER_BAR_STYLE = "padding: 12px 0 8px; margin-bottom: 8px; border-bottom: 1px solid #e2e8f0;"
FILTER_LABEL_STYLE = "font-size: 12px; color: #718096; margin: 0 0 8px; text-transform: uppercase; letter-spacing: 0.5px;"
FILTER_TAG_STYLE = "display: inline-block; background: #ebf4ff; color: #2b6cb0; font-size: 13px; padding: 4px 12px; border-radius: 16px; margin-right: 6px; margin-bottom: 6px; text-decoration: none;"
BUTTONS_STYLE = "margin-top: 14px;"
BTN_GOOGLE_STYLE = "display: inline-block; background: #4285f4; color: #ffffff; text-decoration: none; padding: 8px 14px; border-radius: 4px; font-size: 13px; font-weight: 500; margin-right: 8px;"
BTN_OUTLOOK_STYLE = "display: inline-block; background: #0078d4; color: #ffffff; text-decoration: none; padding: 8px 14px; border-radius: 4px; font-size: 13px; font-weight: 500; margin-right: 8px;"
BTN_ICS_STYLE = "display: inline-block; background: #e2e8f0; color: #4a5568; text-decoration: none; padding: 8px 14px; border-radius: 4px; font-size: 13px; font-weight: 500;"
FOOTER_STYLE = "padding: 24px 32px; text-align: center; font-size: 12px; color: #a0aec0; border-top: 1px solid #e2e8f0;"
FOOTER_LINK_STYLE = "color: #718096; text-decoration: underline;"

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def _format_date(event: Event) -> str:
    """Format as 'Mon 23 Feb, 12:15–13:00'."""
    d = event.date
    parts = [f"{WEEKDAYS[d.weekday()]} {d.day} {MONTHS[d.month]}"]
    if event.start_time:
        t = event.start_time.strftime("%H:%M")
        if event.end_time:
            t += f"–{event.end_time.strftime('%H:%M')}"
        parts.append(t)
    return ", ".join(parts)


def _render_event(event: Event, anchor_id: str = "") -> str:
    """Render a single event card."""
    gcal = google_calendar_url(event)
    outlook = outlook_calendar_url(event)
    ics = event.ics_url

    location_html = ""
    if event.location:
        location_html = f'<p style="{META_STYLE}">{escape(event.location)}</p>'

    category_html = ""
    if event.categories:
        badges = " ".join(
            f'<span style="{CATEGORY_STYLE}">{escape(c)}</span>'
            for c in event.categories
        )
        category_html = f"<div>{badges}</div>"

    speaker_line = escape(event.speaker)
    if event.institution:
        speaker_line += f" ({escape(event.institution)})"

    anchor = f' id="{anchor_id}"' if anchor_id else ""

    return f"""
    <div style="{CARD_STYLE}"{anchor}>
      {category_html}
      <p style="{DATE_STYLE}">{escape(_format_date(event))}</p>
      <p style="{TITLE_STYLE}">{escape(event.title)}</p>
      <p style="{META_STYLE}">{speaker_line}</p>
      {location_html}
      <div style="{BUTTONS_STYLE}">
        <a href="{gcal}" style="{BTN_GOOGLE_STYLE}" target="_blank">Google Calendar</a>
        <a href="{outlook}" style="{BTN_OUTLOOK_STYLE}" target="_blank">Outlook</a>
        <a href="{ics}" style="{BTN_ICS_STYLE}" target="_blank">Download .ics</a>
      </div>
    </div>
    """


def render_digest(
    events: list[Event],
    unsubscribe_url: str = "#",
) -> str:
    """Render the full weekly digest email as HTML.

    Args:
        events: List of events to include, already sorted by date/time.
        unsubscribe_url: One-click unsubscribe link for the footer.
    """
    today = datetime.date.today()
    week_label = f"Week of {today.day} {MONTHS[today.month]} {today.year}"

    # Build unique tag list and map each tag to an anchor ID
    tag_anchors: dict[str, str] = {}  # tag -> anchor id of first event with that tag
    for i, event in enumerate(events):
        for cat in event.categories:
            if cat not in tag_anchors:
                tag_anchors[cat] = f"event-{i}"

    # Render event cards with anchor IDs
    event_cards = "\n".join(
        _render_event(e, anchor_id=f"event-{i}")
        for i, e in enumerate(events)
    )

    # Render filter bar with clickable tag badges
    filter_bar = ""
    if tag_anchors:
        tag_links = " ".join(
            f'<a href="#{anchor}" style="{FILTER_TAG_STYLE}">{escape(tag)}</a>'
            for tag, anchor in tag_anchors.items()
        )
        filter_bar = f"""
      <div style="{FILTER_BAR_STYLE}">
        <p style="{FILTER_LABEL_STYLE}">This week's series</p>
        {tag_links}
      </div>"""

    no_events_msg = ""
    if not events:
        no_events_msg = '<p style="text-align: center; color: #718096; padding: 40px 0;">No upcoming seminars this week.</p>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="{BODY_STYLE}">
  <div style="{CONTAINER_STYLE}">
    <div style="{HEADER_STYLE}">
      <h1 style="{HEADER_TITLE_STYLE}">Helsinki GSE Seminars</h1>
      <p style="{HEADER_SUB_STYLE}">{escape(week_label)} &middot; {len(events)} upcoming event{"s" if len(events) != 1 else ""}</p>
    </div>
    <div style="{CONTENT_STYLE}">
      {filter_bar}
      {no_events_msg}
      {event_cards}
    </div>
    <div style="{FOOTER_STYLE}">
      <p>You're receiving this because you subscribed to Helsinki GSE seminar updates.</p>
      <p><a href="{unsubscribe_url}" style="{FOOTER_LINK_STYLE}">Unsubscribe</a></p>
    </div>
  </div>
</body>
</html>"""
