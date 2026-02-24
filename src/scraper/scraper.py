"""Scrape Helsinki GSE events from https://www.helsinkigse.fi/events."""

from __future__ import annotations

import datetime
import logging
import re
import time
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

from scraper.models import Event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.helsinkigse.fi"
EVENTS_URL = f"{BASE_URL}/events"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
REQUEST_DELAY = 1.5  # seconds between requests
USER_AGENT = "HelsinkiGSE-EventCalendar-Bot/0.1 (weekly digest service)"


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


# ---------------------------------------------------------------------------
# Step 1: Collect event URLs
# ---------------------------------------------------------------------------

def get_event_urls_from_listing(session: requests.Session) -> list[str]:
    """Try to extract event detail-page URLs from the main listing page."""
    resp = session.get(EVENTS_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    urls: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Normalize to full URL
        if href.startswith("/"):
            href = f"{BASE_URL}{href}"
        # Match .../events/<slug> but not the index page
        if re.match(rf"^{re.escape(BASE_URL)}/events/[^/]+$", href):
            if href not in urls:
                urls.append(href)

    logger.info("Listing page yielded %d event URLs", len(urls))
    return urls


def get_event_urls_from_sitemap(session: requests.Session) -> list[str]:
    """Fallback: extract event URLs from the sitemap XML."""
    resp = session.get(SITEMAP_URL, timeout=30)
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    # sitemap namespace
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    urls: list[str] = []
    for loc in root.findall(".//s:loc", ns):
        url = loc.text.strip() if loc.text else ""
        # Match event detail pages (not the /events index)
        if re.match(rf"^{re.escape(BASE_URL)}/events/[^/]+$", url):
            urls.append(url)

    logger.info("Sitemap yielded %d event URLs", len(urls))
    return urls


def get_event_urls(session: requests.Session) -> list[str]:
    """Get event URLs, trying the listing page first, then the sitemap."""
    urls = get_event_urls_from_listing(session)
    if urls:
        return urls

    logger.warning("Listing page returned no URLs; falling back to sitemap")
    return get_event_urls_from_sitemap(session)


# ---------------------------------------------------------------------------
# Step 2: Parse a single event detail page
# ---------------------------------------------------------------------------
#
# Observed page structure (text lines after extracting with BeautifulSoup):
#
#   0: Speaker Name          (h1, repeated later)
#   ...nav lines...
#   N:   Speaker Name        (repeated after nav)
#   N+1: Institution
#   N+2: Talk title / description
#   ...
#   "calendar"
#   "23.02.26"              (DD.MM.YY date)
#   "clock"
#   "12:15"                 (start time)
#   "–"                     (dash, may be on its own line)
#   "13:00"                 (end time)
#   "Organizer:"
#   "Type:"
#   "Lunch Seminar"         (category)
#   "Host:"
#   "First"
#   "Last"                  (host/organizer name, may span two lines)
#   "Venue:"
#   "Room, Building, Address"


def _parse_date(text: str) -> datetime.date | None:
    """Parse DD.MM.YY dates like '23.02.26'."""
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", text.strip())
    if not m:
        return None
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if year < 100:
        year += 2000
    return datetime.date(year, month, day)


def _parse_time(text: str) -> datetime.time | None:
    """Parse times like '12:15' or '14:30'."""
    m = re.match(r"(\d{1,2}):(\d{2})$", text.strip())
    if not m:
        return None
    return datetime.time(int(m.group(1)), int(m.group(2)))


def _get_field_after(lines: list[str], label: str) -> str | None:
    """Find a label line (e.g. 'Venue:') and return the next non-empty line."""
    for i, line in enumerate(lines):
        if line.lower().startswith(label.lower()):
            # Value might be on the same line after the colon
            rest = line.split(":", 1)[1].strip() if ":" in line else ""
            if rest:
                return rest
            # Otherwise take the next line
            if i + 1 < len(lines):
                return lines[i + 1]
    return None


def parse_event_page(html: str, url: str) -> Event | None:
    """Parse a single event detail page into an Event."""
    soup = BeautifulSoup(html, "lxml")

    body_text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in body_text.split("\n") if ln.strip()]

    # -- Speaker: the h1 tag --
    h1 = soup.find("h1")
    speaker = h1.get_text(strip=True) if h1 else ""

    # -- Find the second occurrence of the speaker name in the text lines.
    #    The lines immediately after it are: institution, then title.
    title = ""
    institution = ""
    if speaker:
        found_first = False
        for i, line in enumerate(lines):
            if line == speaker:
                if not found_first:
                    found_first = True
                    continue
                # Second occurrence — next lines are institution, then title
                if i + 1 < len(lines):
                    institution = lines[i + 1]
                if i + 2 < len(lines):
                    title = lines[i + 2]
                break

    # If title is empty or looks like a nav/metadata line, use speaker as title
    if not title or title.lower() in ("calendar", "clock", "organizer:", "type:", "host:", "venue:"):
        title = speaker

    # -- Date: look for DD.MM.YY pattern --
    event_date: datetime.date | None = None
    for line in lines:
        parsed = _parse_date(line)
        if parsed:
            event_date = parsed
            break

    if event_date is None:
        logger.warning("Could not parse date from %s", url)
        return None

    # -- Time: find "clock" label, then start time, optional dash, end time --
    start_time = None
    end_time = None
    for i, line in enumerate(lines):
        if line.lower() == "clock":
            if i + 1 < len(lines):
                start_time = _parse_time(lines[i + 1])
            # End time may be 2 or 3 lines after "clock" (dash may be separate)
            for j in range(i + 2, min(i + 5, len(lines))):
                t = _parse_time(lines[j])
                if t:
                    end_time = t
                    break
            break

    # -- Categories: extract from chip elements (Organizer group + Type) --
    categories: list[str] = []
    seen = set()
    for chip in soup.find_all("span", class_="chip"):
        text = chip.get_text(strip=True)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            categories.append(text)

    # Fallback: parse from text lines if no chips found
    if not categories:
        labels = {"type:", "host:", "hosts:", "venue:", "organizer:", "actions:"}
        category = _get_field_after(lines, "Type:")
        if category and category.lower() not in labels:
            categories.append(category)
        organizer_group = _get_field_after(lines, "Organizer:")
        if organizer_group and organizer_group.lower() not in labels:
            if not category or organizer_group.lower() != category.lower():
                categories.insert(0, organizer_group)

    # -- Host / Organizer: line(s) after "Host:" --
    host = _get_field_after(lines, "Host:")
    # Host name may span two lines (first + last name)
    if host:
        for i, line in enumerate(lines):
            if line.lower().startswith("host:"):
                idx = i + 1
                rest = line.split(":", 1)[1].strip() if ":" in line else ""
                if not rest and idx < len(lines):
                    first = lines[idx]
                    # Check if next line looks like a last name (short, no colon)
                    if idx + 1 < len(lines) and ":" not in lines[idx + 1] and len(lines[idx + 1]) < 30:
                        nxt = lines[idx + 1]
                        # Stop if it looks like a label or section
                        if nxt.lower() not in ("venue:", "actions:", "share", "add to calendar"):
                            host = f"{first} {nxt}"
                break

    # -- Venue: line after "Venue:" --
    venue = _get_field_after(lines, "Venue:")

    # -- Description: the title line often IS the talk title / description.
    #    Some pages have a longer abstract — look for long text lines
    #    that aren't navigation or metadata.
    description = None
    nav_words = {"menu", "research", "programs", "events", "news", "faculty",
                 "about", "job market", "for students", "courses", "faq",
                 "studies", "close drawer", "skip to main", "helsinki gse",
                 "actions", "share", "add to calendar", "twitter", "facebook", "email"}
    for line in lines:
        low = line.lower().strip()
        if len(line) > 80 and low not in nav_words and not low.endswith(":"):
            description = line
            break

    return Event(
        title=title,
        speaker=speaker,
        institution=institution,
        date=event_date,
        start_time=start_time,
        end_time=end_time,
        location=venue,
        description=description,
        categories=categories,
        organizer=host,
        url=url,
    )


# ---------------------------------------------------------------------------
# Step 3: Orchestrate
# ---------------------------------------------------------------------------

def scrape_all_events(limit: int | None = None) -> list[Event]:
    """Scrape upcoming events from the Helsinki GSE site.

    Args:
        limit: If set, only scrape the first N event URLs (useful for testing).
    """
    session = _session()
    urls = get_event_urls(session)
    if limit:
        urls = urls[:limit]
    logger.info("Scraping %d event URLs", len(urls))

    events: list[Event] = []
    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(REQUEST_DELAY)

        logger.info("Scraping %s (%d/%d)", url, i + 1, len(urls))
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            logger.error("Failed to fetch %s: %s", url, e)
            continue

        try:
            event = parse_event_page(resp.text, url)
        except Exception as e:
            logger.error("Failed to parse %s: %s", url, e)
            continue
        if event:
            events.append(event)
        else:
            logger.warning("Could not parse event from %s", url)

    events.sort(key=lambda e: (e.date, e.start_time or datetime.time()))
    logger.info("Successfully scraped %d events", len(events))
    return events
