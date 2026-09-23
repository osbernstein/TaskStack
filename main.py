import sqlite3
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI(title="TaskStack API", version="1.3.0")
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                course TEXT NOT NULL,
                stack_name TEXT NOT NULL DEFAULT 'General',
                due_date TEXT NOT NULL,
                due_time TEXT,
                status TEXT NOT NULL DEFAULT 'not_started' CHECK(status IN ('not_started', 'in_progress', 'done')),
                link TEXT
            );
        """)

        cursor = conn.cursor()
        cols = [c[1] for c in cursor.execute("PRAGMA table_info(assignments)").fetchall()]
        if "stack_name" not in cols:
            cursor.execute("ALTER TABLE assignments ADD COLUMN stack_name TEXT NOT NULL DEFAULT 'General'")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_stack_name ON assignments(stack_name);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_due_date ON assignments(due_date);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON assignments(status);")

init_db()

# --- Schemas ---

class StackCreate(BaseModel):
    name: str

class MergeStacksRequest(BaseModel):
    source_stack: str
    target_stack: str
    task_ids: Optional[List[int]] = None  # If provided, only merge selected tasks; otherwise merge all

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

# --- Stacks API Endpoints ---

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
            conn.commit()
            return {"id": cursor.lastrowid, "name": clean_name}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="A stack with that name already exists.")

@app.delete("/stacks/{stack_name}", status_code=status.HTTP_200_OK)
def delete_stack(stack_name: str, delete_tasks: bool = False):
    if stack_name.lower() == "all":
        raise HTTPException(status_code=400, detail="Cannot delete the 'All' default view.")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM stacks WHERE name = ?", (stack_name,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Stack not found.")
        
        if delete_tasks:
            cursor.execute("DELETE FROM assignments WHERE stack_name = ?", (stack_name,))
            
        conn.commit()
        return {"detail": f"Stack '{stack_name}' deleted successfully."}

@app.post("/stacks/merge", status_code=status.HTTP_200_OK)
def merge_stacks(payload: MergeStacksRequest):
    """Merges all or selected tasks from source_stack into target_stack."""
    if payload.source_stack.lower() == "all" or payload.target_stack.lower() == "all":
        raise HTTPException(status_code=400, detail="Cannot merge to or from the 'All' default stack.")
    if payload.source_stack == payload.target_stack:
        raise HTTPException(status_code=400, detail="Source and target stack cannot be the same.")

    with get_db() as conn:
        cursor = conn.cursor()
        
        # Verify target stack exists
        target = cursor.execute("SELECT id FROM stacks WHERE name = ?", (payload.target_stack,)).fetchone()
        if not target:
            raise HTTPException(status_code=404, detail=f"Target stack '{payload.target_stack}' does not exist.")

        if payload.task_ids:
            # Merge selected tasks
            placeholders = ",".join(["?"] * len(payload.task_ids))
            cursor.execute(
                f"UPDATE assignments SET stack_name = ? WHERE stack_name = ? AND id IN ({placeholders})",
                [payload.target_stack, payload.source_stack, *payload.task_ids]
            )
        else:
            # Merge all tasks
            cursor.execute(
                "UPDATE assignments SET stack_name = ? WHERE stack_name = ?",
                (payload.target_stack, payload.source_stack)
            )

        conn.commit()
        return {"detail": f"Tasks transferred to '{payload.target_stack}' successfully."}

# --- Assignments Endpoints ---

@app.get("/assignments")
def list_assignments(
    stack: Optional[str] = Query(None, description="Filter by stack name"),
    status: Optional[str] = Query(None, description="Filter by status")
):
    query = "SELECT * FROM assignments WHERE 1=1"
    params = []

    if stack and stack.lower() != "all":
        query += " AND stack_name = ?"
        params.append(stack)
    if status:
        query += " AND status = ?"
        params.append(status)

    query += " ORDER BY due_date ASC, due_time ASC"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]

@app.post("/assignments", status_code=status.HTTP_201_CREATED)
def create_assignment(assignment: AssignmentCreate):
    with get_db() as conn:
        cursor = conn.cursor()
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
        raise HTTPException(status_code=400, detail="No fields provided to update")

    set_clauses = [f"{field} = ?" for field in update_data.keys()]
    values = list(update_data.values())
    values.append(assignment_id)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE assignments SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Assignment not found")
        return dict(cursor.execute("SELECT * FROM assignments WHERE id = ?", (assignment_id,)).fetchone())

@app.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Assignment not found")