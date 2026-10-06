"""Helpers shared by the Canvas inspect and sync endpoints."""
import re
from datetime import datetime, date

import httpx
from fastapi import HTTPException
from icalendar import Calendar


def normalize_feed_url(feed_url: str) -> str:
    feed_url = feed_url.strip()
    if feed_url.startswith("webcal://"):
        feed_url = "https://" + feed_url[len("webcal://"):]
    if not feed_url.startswith("http://") and not feed_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid feed URL.")
    return feed_url


async def fetch_calendar(feed_url: str) -> Calendar:
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(feed_url)
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Canvas returned code {resp.status_code}.")
            raw_ics = resp.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Canvas connection failed: {str(e)}")

    try:
        return Calendar.from_ical(raw_ics)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid iCal format: {str(e)}")


def get_categories(component) -> str:
    """Return an event's CATEGORIES as plain text, e.g. "Clubs" (multiple are comma-joined)."""
    values = component.get("CATEGORIES")
    if values is None:
        return ""
    if not isinstance(values, list):
        values = [values]
    names = [str(c).strip() for v in values for c in getattr(v, "cats", [v])]
    return ",".join(n for n in names if n)


def parse_due(component):
    """Return (due_datetime, "YYYY-MM-DD", "HH:MM") for an event, or None if it has no usable date.

    All-day events count as due at the end of the day (23:59)."""
    dtend = component.get("DTEND") or component.get("DTSTART")
    if not dtend:
        return None

    dt_val = dtend.dt
    if isinstance(dt_val, datetime):
        # Convert to naive local time for comparison
        if dt_val.tzinfo:
            dt_val = dt_val.astimezone().replace(tzinfo=None)
        return dt_val, dt_val.strftime("%Y-%m-%d"), dt_val.strftime("%H:%M")
    if isinstance(dt_val, date):
        return datetime.combine(dt_val, datetime.max.time()), dt_val.strftime("%Y-%m-%d"), "23:59"
    return None


def extract_course_tag(raw_summary: str, categories: str):
    """Return (course_tag, title) parsed from an event summary like "Essay 1 [2026FA_CS_101-01]"."""
    course_tag = None
    title = raw_summary

    bracket_end_match = re.search(r"\s*\[(.*?)\]\s*$", raw_summary)
    if bracket_end_match:
        full_course_code = bracket_end_match.group(1).strip()
        title = raw_summary[:bracket_end_match.start()].strip()
        clean_match = re.search(r"(?:[0-9]{4}[A-Z]{2}_)?([A-Za-z_]+_\d+)(?:-\d+.*)?", full_course_code)
        course_tag = clean_match.group(1).strip() if clean_match else full_course_code.split("_SEC")[0].split("-")[0]

    if not course_tag:
        bracket_front_match = re.match(r"^\[(.*?)\]\s*(.*)$", raw_summary)
        if bracket_front_match:
            course_tag = bracket_front_match.group(1).strip()
            title = bracket_front_match.group(2).strip() or raw_summary

    if not course_tag and categories and categories.lower() != "canvas":
        course_tag = categories

    if not course_tag:
        course_tag = "General"

    return course_tag, title


def resolve_link(raw_url: str, description: str, uid: str, canvas_domain: str):
    """Build a direct link to the Canvas assignment page, falling back to the event URL."""
    full_match = re.search(r'https?://[^\s<>"\'?#]+/courses/(\d+)/assignments/(\d+)', raw_url) or \
                 re.search(r'https?://[^\s<>"\'?#]+/courses/(\d+)/assignments/(\d+)', description)

    if full_match:
        cid, aid = full_match.group(1), full_match.group(2)
        return f"https://{canvas_domain}/courses/{cid}/assignments/{aid}"

    aid_match = re.search(r'assignment[_-](\d+)', raw_url) or re.search(r'assignment[_-](\d+)', uid)
    cid_match = re.search(r'course[_-](\d+)', raw_url) or \
                re.search(r'course[_-](\d+)', description) or \
                re.search(r'/courses/(\d+)', description)

    if aid_match and cid_match:
        aid, cid = aid_match.group(1), cid_match.group(1)
        return f"https://{canvas_domain}/courses/{cid}/assignments/{aid}"
    if aid_match:
        return f"https://{canvas_domain}/assignments/{aid_match.group(1)}"
    if raw_url:
        return raw_url.split('?return_to=')[0]
    return None
