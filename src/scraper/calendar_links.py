"""Generate 'Add to calendar' links for Google Calendar and Outlook web."""

from __future__ import annotations

import datetime
from urllib.parse import quote, urlencode

from scraper.models import Event

# Helsinki timezone offset for URL encoding (Google/Outlook want full datetimes)
TIMEZONE = "Europe/Helsinki"


def _event_datetimes(event: Event) -> tuple[datetime.datetime, datetime.datetime]:
    """Build start/end datetimes. Defaults to 1-hour event if times are missing."""
    start_time = event.start_time or datetime.time(12, 0)
    start = datetime.datetime.combine(event.date, start_time)

    if event.end_time:
        end = datetime.datetime.combine(event.date, event.end_time)
    else:
        end = start + datetime.timedelta(hours=1)

    return start, end


def _format_gcal_dt(dt: datetime.datetime) -> str:
    """Format as YYYYMMDDTHHmmSS (no separators, no Z — we specify timezone)."""
    return dt.strftime("%Y%m%dT%H%M%S")


def _event_description(event: Event) -> str:
    """Build a description string for calendar entries."""
    parts: list[str] = []
    if event.speaker:
        line = event.speaker
        if event.institution:
            line += f" ({event.institution})"
        parts.append(line)
    if event.description and event.description != event.title:
        parts.append(event.description)
    parts.append(f"Details: {event.url}")
    return "\n".join(parts)


def google_calendar_url(event: Event) -> str:
    """Generate a Google Calendar 'create event' link.

    Opens https://calendar.google.com/calendar/render with pre-filled fields.
    """
    start, end = _event_datetimes(event)
    params = {
        "action": "TEMPLATE",
        "text": event.title,
        "dates": f"{_format_gcal_dt(start)}/{_format_gcal_dt(end)}",
        "ctz": TIMEZONE,
        "details": _event_description(event),
    }
    if event.location:
        params["location"] = event.location

    return f"https://calendar.google.com/calendar/render?{urlencode(params, quote_via=quote)}"


def outlook_calendar_url(event: Event) -> str:
    """Generate an Outlook web 'create event' link.

    Opens https://outlook.office.com/calendar/0/action/compose with pre-filled fields.
    """
    start, end = _event_datetimes(event)
    # Outlook expects ISO 8601 format
    params = {
        "rru": "addevent",
        "subject": event.title,
        "startdt": start.isoformat(),
        "enddt": end.isoformat(),
        "body": _event_description(event),
    }
    if event.location:
        params["location"] = event.location

    return f"https://outlook.office.com/calendar/0/action/compose?{urlencode(params, quote_via=quote)}"


def calendar_links(event: Event) -> dict[str, str]:
    """Return all calendar links for an event."""
    return {
        "google": google_calendar_url(event),
        "outlook": outlook_calendar_url(event),
        "ics": event.ics_url,
    }
