import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, HttpUrl
from fastapi.responses import FileResponse

app = FastAPI(title="Assignment Tracker API", version="1.0.0")

DB_FILE = "assignments.db"

# --- Database Initialization ---
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Returns rows as dictionary-like objects
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                course TEXT NOT NULL,
                due_date TEXT NOT NULL,
                due_time TEXT,
                status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'done')),
                link TEXT
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_course ON assignments(course);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_due_date ON assignments(due_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON assignments(status);")

init_db()

# --- Pydantic Models (Validation) ---
class AssignmentCreate(BaseModel):
    title: str
    course: str
    due_date: str  # YYYY-MM-DD
    due_time: Optional[str] = None  # HH:MM
    status: Optional[str] = "not_started"
    link: Optional[str] = None

class AssignmentUpdate(BaseModel):
    title: Optional[str] = None
    course: Optional[str] = None
    due_date: Optional[str] = None
    due_time: Optional[str] = None
    status: Optional[str] = None
    link: Optional[str] = None

# --- API Endpoints ---
@app.get("/", include_in_schema=False)
def serve_ui():
    return FileResponse("static/index.html")

@app.get("/assignments")
def list_assignments(
    course: Optional[str] = Query(None, description="Filter by course"),
    status: Optional[str] = Query(None, description="Filter by status (not_started, in_progress, done)"),
    due_date: Optional[str] = Query(None, description="Filter by due date (YYYY-MM-DD)")
):
    query = "SELECT * FROM assignments WHERE 1=1"
    params = []

    if course:
        query += " AND course = ?"
        params.append(course)
    if status:
        query += " AND status = ?"
        params.append(status)
    if due_date:
        query += " AND due_date = ?"
        params.append(due_date)

    query += " ORDER BY due_date ASC, due_time ASC"

    with get_db() as conn:
        cursor = conn.cursor()
        rows = cursor.execute(query, params).fetchall()
        return [dict(row) for row in rows]

@app.post("/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(assignment: AssignmentCreate):
    valid_statuses = {"not_started", "in_progress", "done"}
    if assignment.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of {valid_statuses}")

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO assignments (title, course, due_date, due_time, status, link)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (assignment.title, assignment.course, assignment.due_date, assignment.due_time, assignment.status, assignment.link))
        new_id = cursor.lastrowid
        conn.commit()

        row = cursor.execute("SELECT * FROM assignments WHERE id = ?", (new_id,)).fetchone()
        return dict(row)

@app.get("/assignments/{assignment_id}")
def get_assignment(assignment_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Assignment not found")
        return dict(row)

@app.patch("/assignments/{assignment_id}")
def update_assignment(assignment_id: int, updates: AssignmentUpdate):
    update_data = updates.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    if "status" in update_data and update_data["status"] not in {"not_started", "in_progress", "done"}:
        raise HTTPException(status_code=400, detail="Invalid status value")

    set_clauses = [f"{field} = ?" for field in update_data.keys()]
    values = list(update_data.values())
    values.append(assignment_id)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE assignments SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Assignment not found")

        row = cursor.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone()
        return dict(row)

@app.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Assignment not found")