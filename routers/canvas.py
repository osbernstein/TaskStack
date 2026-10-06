from datetime import datetime
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, status

from database import get_db
from schemas import CanvasInspectRequest, CanvasSyncRequest
from services.canvas_parser import normalize_feed_url, get_categories, fetch_calendar, parse_due, extract_course_tag, resolve_link

router = APIRouter()


@router.post("/canvas/inspect")
async def inspect_canvas_feed(payload: CanvasInspectRequest):
    feed_url = normalize_feed_url(payload.feed_url)
    target_stack = payload.target_stack.strip()
    cal = await fetch_calendar(feed_url)

    # Fetch tags already registered to this stack
    with get_db() as conn:
        cursor = conn.cursor()
        existing_tags = {
            row[0] for row in cursor.execute(
                "SELECT tag_name FROM stack_tags WHERE stack_name = ?", (target_stack,)
            ).fetchall()
        }

    now = datetime.now()
    tag_counts = {}

    for component in cal.walk():
        if component.name != "VEVENT":
            continue

        raw_summary = str(component.get("SUMMARY") or "").strip()
        categories = get_categories(component)

        due = parse_due(component)
        if not due:
            continue
        due_dt, _, _ = due

        # Past-due filter: skip only if include_past_due is False
        if not payload.include_past_due and due_dt < now:
            continue

        course_tag, _ = extract_course_tag(raw_summary, categories)
        tag_counts[course_tag] = tag_counts.get(course_tag, 0) + 1

    return {
        "detected_tags": [
            {
                "tag": tag,
                "count": count,
                "already_in_stack": tag in existing_tags
            }
            for tag, count in tag_counts.items()
        ]
    }


@router.post("/canvas/sync", status_code=status.HTTP_200_OK)
async def sync_canvas_feed(payload: CanvasSyncRequest):
    feed_url = normalize_feed_url(payload.feed_url)
    target_stack = payload.target_stack.strip()
    allowed_tags = set(payload.allowed_tags)

    if not target_stack or target_stack.lower() == "all":
        raise HTTPException(status_code=400, detail="Select a valid destination stack.")

    canvas_domain = urlparse(feed_url).netloc
    cal = await fetch_calendar(feed_url)

    synced_items = []
    now = datetime.now()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO stacks (name) VALUES (?)", (target_stack,))

        for component in cal.walk():
            if component.name != "VEVENT":
                continue

            uid = str(component.get("UID") or "").strip()
            if not uid:
                continue

            raw_summary = str(component.get("SUMMARY") or "Canvas Assignment").strip()
            description = str(component.get("DESCRIPTION") or "")
            categories = get_categories(component)

            # Past-due filter check (respects include_past_due toggle)
            due = parse_due(component)
            if not due:
                continue
            due_dt, due_date_str, due_time_str = due
            if not payload.include_past_due and due_dt < now:
                continue

            course_tag, title = extract_course_tag(raw_summary, categories)

            # Drop tasks whose tags are NOT allowed by the user
            if allowed_tags and course_tag not in allowed_tags:
                continue

            cursor.execute("INSERT OR IGNORE INTO stack_tags (stack_name, tag_name) VALUES (?, ?)", (target_stack, course_tag))

            raw_url = str(component.get("URL") or "").strip()
            direct_link = resolve_link(raw_url, description, uid, canvas_domain)

            # Query existing task by external_id
            existing = cursor.execute("""
                SELECT id, title, course, due_date, due_time, link 
                FROM assignments 
                WHERE external_id = ?
            """, (uid,)).fetchone()

            if not existing:
                # 1. Brand New Task
                cursor.execute("""
                    INSERT INTO assignments (title, course, stack_name, due_date, due_time, link, external_id, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started')
                """, (title, course_tag, target_stack, due_date_str, due_time_str, direct_link, uid))

                synced_items.append({
                    "title": title,
                    "course": course_tag,
                    "due_date": due_date_str,
                    "due_time": due_time_str,
                    "change_type": "new"
                })
            else:
                # 2. Existing Task: Check if title, course, due_date, due_time, or link changed
                has_changed = (
                    (existing["title"] or "").strip() != title or
                    (existing["course"] or "").strip() != course_tag or
                    (existing["due_date"] or "").strip() != due_date_str or
                    (existing["due_time"] or "").strip() != (due_time_str or "") or
                    (existing["link"] or "").strip() != (direct_link or "")
                )

                if has_changed:
                    cursor.execute("""
                        UPDATE assignments 
                        SET title = ?, course = ?, due_date = ?, due_time = ?, link = ?
                        WHERE id = ?
                    """, (title, course_tag, due_date_str, due_time_str, direct_link, existing["id"]))

                    synced_items.append({
                        "title": title,
                        "course": course_tag,
                        "due_date": due_date_str,
                        "due_time": due_time_str,
                        "change_type": "updated"
                    })
                # If unchanged, do nothing and omit from synced_items
        conn.commit()

    return {
        "imported": len(synced_items),
        "target_stack": target_stack,
        "tasks": synced_items
    }
