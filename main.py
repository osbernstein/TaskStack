import re
from datetime import datetime, date
import sqlite3
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
import httpx
from icalendar import Calendar
from urllib.parse import urlparse

app = FastAPI(title="TaskStack API", version="1.4.0")
DB_FILE = "assignments.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stacks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );
        """)

        # Table to store tags scoped to stacks
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stack_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stack_name TEXT NOT NULL,
                tag_name TEXT NOT NULL,
                UNIQUE(stack_name, tag_name)
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                course TEXT NOT NULL,
                stack_name TEXT NOT NULL DEFAULT 'General',
                due_date TEXT NOT NULL,
                due_time TEXT,
                status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'done')),
                link TEXT,
                external_id TEXT
            );
        """)

        cursor = conn.cursor()
        cols = [c[1] for c in cursor.execute("PRAGMA table_info(assignments)").fetchall()]
        if "stack_name" not in cols:
            cursor.execute("ALTER TABLE assignments ADD COLUMN stack_name TEXT NOT NULL DEFAULT 'General'")
        if "external_id" not in cols:
            cursor.execute("ALTER TABLE assignments ADD COLUMN external_id TEXT")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_stack_name ON assignments(stack_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_due_date ON assignments(due_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON assignments(status);")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_external_id ON assignments(external_id);")

init_db()

# --- Schemas ---

class StackCreate(BaseModel):
    name: str
    tags: Optional[List[str]] = []

class StackTagAdd(BaseModel):
    tag_name: str

class BatchUpdate(BaseModel):
    task_ids: List[int]
    status: Optional[str] = None
    course: Optional[str] = None

class BatchDelete(BaseModel):
    task_ids: List[int]

class MergeStacksRequest(BaseModel):
    source_stack: str
    target_stack: str
    task_ids: Optional[List[int]] = None

class CanvasSyncRequest(BaseModel):
    feed_url: str
    target_stack: str

class AssignmentCreate(BaseModel):
    title: str
    course: str
    stack_name: str
    due_date: str
    due_time: Optional[str] = None
    status: Optional[str] = "not_started"
    link: Optional[str] = None

class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    course: Optional[str] = None
    stack_name: Optional[str] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    status: Optional[str] = None
    link: Optional[str] = None

# --- UI Root ---

@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse("static/index.html")

# --- Stacks Endpoints ---

@app.get("/stacks")
def get_stacks():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM stacks ORDER BY name COLLATE NOCASE ASC").fetchall()
        return [dict(r) for r in rows]

@app.post("/stacks", status_code=status.HTTP_201_CREATED)
def create_stack(stack: StackCreate):
    clean_name = stack.name.strip()
    if not clean_name or clean_name.lower() == "all":
        raise HTTPException(status_code=400, detail="Invalid stack name.")
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO stacks (name) VALUES (?)", (clean_name,))
            stack_id = cursor.lastrowid
            if stack.tags:
                for t in stack.tags:
                    t_clean = t.strip()
                    if t_clean:
                        cursor.execute("INSERT OR IGNORE INTO stack_tags (stack_name, tag_name) VALUES (?, ?)", (clean_name, t_clean))
            conn.commit()
            return {"id": stack_id, "name": clean_name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="A stack with that name already exists.")

@app.delete("/stacks/{stack_name}", status_code=status.HTTP_200_OK)
def delete_stack(stack_name: str, delete_tasks: bool = False):
    if stack_name.lower() == "all":
        raise HTTPException(status_code=400, detail="Cannot delete 'All'.")
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stacks WHERE name = ?", (stack_name,))
        cursor.execute("DELETE FROM stack_tags WHERE stack_name = ?", (stack_name,))
        if delete_tasks:
            cursor.execute("DELETE FROM assignments WHERE stack_name = ?", (stack_name,))
        conn.commit()
        return {"detail": f"Stack '{stack_name}' deleted."}

# --- Stack Tags Endpoints ---

@app.get("/stacks/{stack_name}/tags")
def get_stack_tags(stack_name: str):
    with get_db() as conn:
        cursor = conn.cursor()
        if stack_name.lower() == "all":
            rows = cursor.execute("""
                SELECT DISTINCT tag_name FROM stack_tags 
                UNION 
                SELECT DISTINCT course FROM assignments WHERE course != ''
            """).fetchall()
        else:
            rows = cursor.execute("""
                SELECT DISTINCT tag_name FROM stack_tags WHERE stack_name = ?
                UNION
                SELECT DISTINCT course FROM assignments WHERE stack_name = ? AND course != ''
            """, (stack_name, stack_name)).fetchall()
        return [r[0] for r in rows]

@app.post("/stacks/{stack_name}/tags")
def add_stack_tag(stack_name: str, payload: StackTagAdd):
    clean = payload.tag_name.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Tag cannot be empty.")
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO stack_tags (stack_name, tag_name) VALUES (?, ?)", (stack_name, clean))
        conn.commit()
        return {"stack_name": stack_name, "tag_name": clean}

@app.delete("/stacks/{stack_name}/tags/{tag_name}")
def delete_stack_tag(stack_name: str, tag_name: str):
    with get_db() as conn:
        cursor = conn.cursor()
        
        # 1. Delete the tag registration from the stack
        cursor.execute("DELETE FROM stack_tags WHERE stack_name = ? AND tag_name = ?", (stack_name, tag_name))
        
        # 2. Check if any tasks currently belong to this tag in this stack
        tasks_count = cursor.execute(
            "SELECT COUNT(*) FROM assignments WHERE stack_name = ? AND course = ?",
            (stack_name, tag_name)
        ).fetchone()[0]

        reassigned_count = 0

        # 3. Only reassign if there are actually remaining tasks under this tag
        if tasks_count > 0:
            cursor.execute("INSERT OR IGNORE INTO stack_tags (stack_name, tag_name) VALUES (?, 'General')", (stack_name,))
            cursor.execute("""
                UPDATE assignments 
                SET course = 'General' 
                WHERE stack_name = ? AND course = ?
            """, (stack_name, tag_name))
            reassigned_count = cursor.rowcount

        conn.commit()
        return {
            "detail": f"Tag '{tag_name}' deleted.",
            "reassigned_to_general": reassigned_count
        }

# --- Merge Endpoints ---

@app.post("/stacks/merge", status_code=status.HTTP_200_OK)
def merge_stacks(payload: MergeStacksRequest):
    if payload.source_stack.lower() == "all" or payload.target_stack.lower() == "all":
        raise HTTPException(status_code=400, detail="Cannot merge to/from 'All'.")
    if payload.source_stack == payload.target_stack:
        raise HTTPException(status_code=400, detail="Source and target must be different.")

    with get_db() as conn:
        cursor = conn.cursor()
        if payload.task_ids:
            placeholders = ",".join(["?"] * len(payload.task_ids))
            cursor.execute(
                f"UPDATE assignments SET stack_name = ? WHERE stack_name = ? AND id IN ({placeholders})",
                [payload.target_stack, payload.source_stack, *payload.task_ids]
            )
        else:
            cursor.execute("UPDATE assignments SET stack_name = ? WHERE stack_name = ?", (payload.target_stack, payload.source_stack))
            cursor.execute("UPDATE OR IGNORE stack_tags SET stack_name = ? WHERE stack_name = ?", (payload.target_stack, payload.source_stack))

        conn.commit()
        return {"detail": "Merged successfully."}

# --- Canvas Sync Endpoint ---

@app.post("/canvas/sync", status_code=status.HTTP_200_OK)
async def sync_canvas_feed(payload: CanvasSyncRequest):
    feed_url = payload.feed_url.strip()
    target_stack = payload.target_stack.strip()

    if feed_url.startswith("webcal://"):
        feed_url = "https://" + feed_url[len("webcal://"):]

    if not feed_url.startswith("http://") and not feed_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid feed URL.")

    if not target_stack or target_stack.lower() == "all":
        raise HTTPException(status_code=400, detail="Select a valid destination stack.")

    # Extract canvas domain (e.g. canvas.northwestern.edu)
    parsed_feed = urlparse(feed_url)
    canvas_domain = parsed_feed.netloc

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(feed_url)
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Canvas returned code {resp.status_code}.")
            raw_ics = resp.text
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Canvas connection failed: {str(e)}")

    try:
        cal = Calendar.from_ical(raw_ics)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid iCal format: {str(e)}")

    imported_count = 0

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
            categories = str(component.get("CATEGORIES") or "").strip()

            course_tag = None
            title = raw_summary

            # 1. Match Northwestern/Standard Canvas brackets at the END:
            # "Title Here [2026FA_PERF_ST_103-0_SEC2]"
            bracket_end_match = re.search(r"\s*\[(.*?)\]\s*$", raw_summary)
            if bracket_end_match:
                full_course_code = bracket_end_match.group(1).strip()
                title = raw_summary[:bracket_end_match.start()].strip()
                
                clean_match = re.search(r"(?:[0-9]{4}[A-Z]{2}_)?([A-Za-z_]+_\d+)(?:-\d+.*)?", full_course_code)
                if clean_match:
                    course_tag = clean_match.group(1).strip()
                else:
                    course_tag = full_course_code.split("_SEC")[0].split("-")[0]

            # 2. Match brackets at the FRONT: "[CS 211] Homework 1"
            if not course_tag:
                bracket_front_match = re.match(r"^\[(.*?)\]\s*(.*)$", raw_summary)
                if bracket_front_match:
                    course_tag = bracket_front_match.group(1).strip()
                    title = bracket_front_match.group(2).strip() or raw_summary

            # 3. Fallbacks
            if not course_tag and categories and categories.lower() != "canvas":
                course_tag = categories

            if not course_tag:
                course_tag = "General"

            # Register tag
            cursor.execute("INSERT OR IGNORE INTO stack_tags (stack_name, tag_name) VALUES (?, ?)", (target_stack, course_tag))

            # Parse Due Date / Time
            dtend = component.get("DTEND") or component.get("DTSTART")
            due_date_str = None
            due_time_str = None

            if dtend:
                dt_val = dtend.dt
                if isinstance(dt_val, datetime):
                    due_date_str = dt_val.strftime("%Y-%m-%d")
                    due_time_str = dt_val.strftime("%H:%M")
                elif isinstance(dt_val, date):
                    due_date_str = dt_val.strftime("%Y-%m-%d")
                    due_time_str = "23:59"

            if not due_date_str:
                due_date_str = datetime.now().strftime("%Y-%m-%d")
                due_time_str = "23:59"

            # Direct Assignment URL resolution
            raw_url = str(component.get("URL") or "").strip()
            direct_link = None

            # 1. First, check if the full /courses/<cid>/assignments/<aid> link exists in raw_url or description
            full_match = re.search(r'https?://[^\s<>"\'?#]+/courses/(\d+)/assignments/(\d+)', raw_url) or \
                         re.search(r'https?://[^\s<>"\'?#]+/courses/(\d+)/assignments/(\d+)', description)

            if full_match:
                cid = full_match.group(1)
                aid = full_match.group(2)
                direct_link = f"https://{canvas_domain}/courses/{cid}/assignments/{aid}"
            else:
                # 2. Extract assignment_id from raw_url hash (#assignment_1803006) or UID (event-assignment-1803006)
                aid_match = re.search(r'assignment[_-](\d+)', raw_url) or re.search(r'assignment[_-](\d+)', uid)
                
                # Extract course_id from include_contexts=course_257726 or /courses/257726
                cid_match = re.search(r'course[_-](\d+)', raw_url) or \
                            re.search(r'course[_-](\d+)', description) or \
                            re.search(r'/courses/(\d+)', description)

                if aid_match and cid_match:
                    aid = aid_match.group(1)
                    cid = cid_match.group(1)
                    direct_link = f"https://{canvas_domain}/courses/{cid}/assignments/{aid}"
                elif aid_match:
                    # Fallback to direct assignment path without extra query params
                    direct_link = f"https://{canvas_domain}/courses/{aid_match.group(1)}"
                elif raw_url:
                    # Strip any '?return_to=...' calendar tracking parameters
                    direct_link = raw_url.split('?return_to=')[0]

            # Idempotent Upsert (Prevents duplicates and preserves task status)
            cursor.execute("""
                INSERT INTO assignments (title, course, stack_name, due_date, due_time, link, external_id, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'not_started')
                ON CONFLICT(external_id) DO UPDATE SET
                    title = excluded.title,
                    course = excluded.course,
                    due_date = excluded.due_date,
                    due_time = excluded.due_time,
                    link = excluded.link;
            """, (title, course_tag, target_stack, due_date_str, due_time_str, direct_link, uid))

            imported_count += 1

        conn.commit()

    return {"imported": imported_count, "target_stack": target_stack}

# --- Batch Operations Endpoints ---

@app.post("/assignments/batch/update")
def batch_update_assignments(payload: BatchUpdate):
    if not payload.task_ids:
        raise HTTPException(status_code=400, detail="No task IDs provided.")

    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(payload.task_ids))

        if payload.status:
            cursor.execute(f"UPDATE assignments SET status = ? WHERE id IN ({placeholders})", [payload.status, *payload.task_ids])
        if payload.course:
            cursor.execute(f"UPDATE assignments SET course = ? WHERE id IN ({placeholders})", [payload.course, *payload.task_ids])

        conn.commit()
        return {"updated": cursor.rowcount}

@app.post("/assignments/batch/delete")
def batch_delete_assignments(payload: BatchDelete):
    if not payload.task_ids:
        raise HTTPException(status_code=400, detail="No task IDs provided.")

    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(payload.task_ids))
        cursor.execute(f"DELETE FROM assignments WHERE id IN ({placeholders})", payload.task_ids)
        conn.commit()
        return {"deleted": cursor.rowcount}

# --- Standard Assignments CRUD ---

@app.get("/assignments")
def list_assignments(stack: Optional[str] = Query(None)):
    query = "SELECT * FROM assignments WHERE 1=1"
    params = []
    if stack and stack.lower() != "all":
        query += " AND stack_name = ?"
        params.append(stack)
    query += " ORDER BY due_date ASC, due_time ASC"
    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

@app.post("/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(assignment: AssignmentCreate):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO stack_tags (stack_name, tag_name) VALUES (?, ?)", (assignment.stack_name, assignment.course))
        cursor.execute("""
            INSERT INTO assignments (title, course, stack_name, due_date, due_time, status, link)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (assignment.title, assignment.course, assignment.stack_name, assignment.due_date, assignment.due_time, assignment.status, assignment.link))
        new_id = cursor.lastrowid
        conn.commit()
        return dict(cursor.execute("SELECT * FROM assignments WHERE id = ?", (new_id,)).fetchone())

@app.patch("/assignments/{assignment_id}")
def update_assignment(assignment_id: int, updates: AssignmentUpdate):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided.")
    set_clauses = [f"{field} = ?" for field in update_data.keys()]
    values = list(update_data.values()) + [assignment_id]

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE assignments SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        return dict(cursor.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone())

@app.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
        conn.commit()