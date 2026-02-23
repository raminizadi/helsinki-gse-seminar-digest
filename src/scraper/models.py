from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import dataclass, field


@dataclass
class Event:
    """A single Helsinki GSE seminar event."""

    title: str
    speaker: str
    institution: str
    date: datetime.date
    url: str
    start_time: datetime.time | None = None
    end_time: datetime.time | None = None
    location: str | None = None
    description: str | None = None
    categories: list[str] = field(default_factory=list)
    organizer: str | None = None

    @property
    def ics_url(self) -> str:
        """The site already serves .ics files at {event_url}.ics."""
        return f"{self.url}.ics"

    @property
    def event_hash(self) -> str:
        """Stable identifier derived from the event URL (slug is unique per event)."""
        return hashlib.sha256(self.url.encode()).hexdigest()

    def to_dict(self) -> dict:
        """Serialize to a JSON-friendly dict."""
        return {
            "title": self.title,
            "speaker": self.speaker,
            "institution": self.institution,
            "date": self.date.isoformat(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "location": self.location,
            "description": self.description,
            "categories": self.categories,
            "organizer": self.organizer,
            "url": self.url,
            "ics_url": self.ics_url,
            "event_hash": self.event_hash,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


@dataclass
class Subscriber:
    """A newsletter subscriber."""

    id: int
    email: str
    status: str  # "pending", "active", "unsubscribed"
    confirm_token: str | None = None
    created_at: datetime.datetime | None = None
