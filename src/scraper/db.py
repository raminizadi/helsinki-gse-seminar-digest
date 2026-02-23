"""Database layer — Supabase (Postgres) client and CRUD operations."""

from __future__ import annotations

import datetime
import logging
import os

from supabase import Client, create_client

from scraper.models import Event, Subscriber

logger = logging.getLogger(__name__)

_client: Client | None = None


def get_client() -> Client:
    """Return a cached Supabase client, initialised from env vars."""
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        _client = create_client(url, key)
    return _client


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def upsert_events(events: list[Event]) -> int:
    """Insert or update events. Returns the number of rows upserted.

    Uses event_hash as the conflict key. On conflict, all fields are updated
    EXCEPT first_seen_at (which stays at the original value).
    """
    if not events:
        return 0

    rows = []
    for e in events:
        rows.append({
            "event_hash": e.event_hash,
            "title": e.title,
            "speaker": e.speaker,
            "institution": e.institution,
            "date": e.date.isoformat(),
            "start_time": e.start_time.isoformat() if e.start_time else None,
            "end_time": e.end_time.isoformat() if e.end_time else None,
            "location": e.location,
            "description": e.description,
            "categories": e.categories,
            "organizer": e.organizer,
            "url": e.url,
        })

    client = get_client()
    result = (
        client.table("events")
        .upsert(rows, on_conflict="event_hash", ignore_duplicates=False)
        .execute()
    )
    count = len(result.data) if result.data else 0
    logger.info("Upserted %d events", count)
    return count


def get_upcoming_events(
    from_date: datetime.date | None = None,
    until_date: datetime.date | None = None,
) -> list[Event]:
    """Return events with date >= from_date (and <= until_date if given)."""
    if from_date is None:
        from_date = datetime.date.today()

    client = get_client()
    query = (
        client.table("events")
        .select("*")
        .gte("date", from_date.isoformat())
    )
    if until_date is not None:
        query = query.lte("date", until_date.isoformat())
    result = query.order("date").order("start_time").execute()
    return [_row_to_event(r) for r in (result.data or [])]


def get_week_events(
    from_date: datetime.date | None = None,
) -> list[Event]:
    """Return events for the week starting at from_date (Mon–Sun)."""
    if from_date is None:
        from_date = datetime.date.today()
    # Go to the Monday of this week
    monday = from_date - datetime.timedelta(days=from_date.weekday())
    sunday = monday + datetime.timedelta(days=6)
    return get_upcoming_events(from_date=monday, until_date=sunday)


def get_unsent_events(subscriber_id: int) -> list[Event]:
    """Return this week's events not yet sent to a given subscriber."""
    upcoming = get_week_events()
    if not upcoming:
        return []

    client = get_client()
    sent_result = (
        client.table("sent_log")
        .select("event_hash")
        .eq("subscriber_id", subscriber_id)
        .execute()
    )
    sent_hashes = {r["event_hash"] for r in (sent_result.data or [])}
    return [e for e in upcoming if e.event_hash not in sent_hashes]


# ---------------------------------------------------------------------------
# Sent log
# ---------------------------------------------------------------------------

def mark_sent(subscriber_id: int, event_hashes: list[str]) -> None:
    """Record that events were sent to a subscriber."""
    if not event_hashes:
        return

    rows = [
        {"subscriber_id": subscriber_id, "event_hash": h}
        for h in event_hashes
    ]
    client = get_client()
    client.table("sent_log").upsert(
        rows, on_conflict="subscriber_id,event_hash", ignore_duplicates=True
    ).execute()
    logger.info("Marked %d events as sent for subscriber %d", len(event_hashes), subscriber_id)


# ---------------------------------------------------------------------------
# Subscribers
# ---------------------------------------------------------------------------

def get_active_subscribers() -> list[Subscriber]:
    """Return all subscribers with status = 'active'."""
    client = get_client()
    result = (
        client.table("subscribers")
        .select("*")
        .eq("status", "active")
        .execute()
    )
    return [_row_to_subscriber(r) for r in (result.data or [])]


def create_or_reactivate_subscriber(email: str) -> str:
    """Create a new subscriber or reactivate an existing one.

    Returns:
        "created"        — new subscriber inserted as pending
        "already_active" — subscriber already active, no action
        "pending"        — subscriber already pending, re-send confirmation
        "reactivated"    — unsubscribed subscriber set back to pending
    """
    email = email.lower().strip()
    client = get_client()
    result = client.table("subscribers").select("*").eq("email", email).execute()

    if not result.data:
        client.table("subscribers").insert({"email": email, "status": "pending"}).execute()
        logger.info("Created new subscriber: %s", email)
        return "created"

    row = result.data[0]
    if row["status"] == "active":
        return "already_active"

    if row["status"] == "pending":
        return "pending"

    # unsubscribed → reactivate
    client.table("subscribers").update({"status": "pending"}).eq("email", email).execute()
    logger.info("Reactivated subscriber: %s", email)
    return "reactivated"


def activate_subscriber(email: str) -> bool:
    """Set subscriber status to 'active'. Returns True if a row was updated."""
    email = email.lower().strip()
    client = get_client()
    result = (
        client.table("subscribers")
        .update({"status": "active"})
        .eq("email", email)
        .execute()
    )
    ok = bool(result.data)
    if ok:
        logger.info("Activated subscriber: %s", email)
    return ok


def deactivate_subscriber(email: str) -> bool:
    """Set subscriber status to 'unsubscribed'. Returns True if a row was updated."""
    email = email.lower().strip()
    client = get_client()
    result = (
        client.table("subscribers")
        .update({"status": "unsubscribed"})
        .eq("email", email)
        .execute()
    )
    ok = bool(result.data)
    if ok:
        logger.info("Unsubscribed: %s", email)
    return ok


# ---------------------------------------------------------------------------
# Row → dataclass helpers
# ---------------------------------------------------------------------------

def _row_to_event(row: dict) -> Event:
    """Convert a Supabase row dict to an Event dataclass."""
    return Event(
        title=row["title"],
        speaker=row["speaker"],
        institution=row["institution"],
        date=datetime.date.fromisoformat(row["date"]),
        start_time=_parse_time(row.get("start_time")),
        end_time=_parse_time(row.get("end_time")),
        location=row.get("location"),
        description=row.get("description"),
        categories=row.get("categories", []),
        organizer=row.get("organizer"),
        url=row["url"],
    )


def _row_to_subscriber(row: dict) -> Subscriber:
    return Subscriber(
        id=row["id"],
        email=row["email"],
        status=row["status"],
        confirm_token=row.get("confirm_token"),
        created_at=datetime.datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None,
    )


def _parse_time(val: str | None) -> datetime.time | None:
    if not val:
        return None
    return datetime.time.fromisoformat(val)
