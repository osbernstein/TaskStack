from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from database import get_db
from schemas import AssignmentCreate, AssignmentUpdate, BatchAssignmentCreate, BatchUpdate, BatchDelete

router = APIRouter()

# --- Batch Operations Endpoints ---

@router.post("/assignments/batch/update")
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

@router.post("/assignments/batch/delete")
def batch_delete_assignments(payload: BatchDelete):
    if not payload.task_ids:
        raise HTTPException(status_code=400, detail="No task IDs provided.")

    with get_db() as conn:
        cursor = conn.cursor()
        placeholders = ",".join(["?"] * len(payload.task_ids))
        cursor.execute(f"DELETE FROM assignments WHERE id IN ({placeholders})", payload.task_ids)
        conn.commit()
        return {"deleted": cursor.rowcount}

@router.post("/assignments/batch/create", status_code=status.HTTP_201_CREATED)
def batch_create_assignments(payload: BatchAssignmentCreate):
    stack_name = payload.stack_name.strip()
    if not stack_name or stack_name.lower() == "all":
        raise HTTPException(status_code=400, detail="Select a valid stack.")
    if not payload.tasks:
        raise HTTPException(status_code=400, detail="No tasks provided.")
    for t in payload.tasks:
        if not t.title.strip() or not t.due_date:
            raise HTTPException(status_code=400, detail="Every task needs a name and a due date.")

    with get_db() as conn:
        cursor = conn.cursor()
        new_ids = []
        for t in payload.tasks:
            course = (t.course or payload.course or "").strip() or "General"
            cursor.execute("INSERT OR IGNORE INTO stack_tags (stack_name, tag_name) VALUES (?, ?)", (stack_name, course))
            cursor.execute("""
                INSERT INTO assignments (title, course, stack_name, due_date, due_time, status, link)
                VALUES (?, ?, ?, ?, ?, 'not_started', ?)
            """, (t.title.strip(), course, stack_name, t.due_date, t.due_time, t.link))
            new_ids.append(cursor.lastrowid)
        conn.commit()
        placeholders = ",".join(["?"] * len(new_ids))
        rows = cursor.execute(f"SELECT * FROM assignments WHERE id IN ({placeholders}) ORDER BY id", new_ids).fetchall()
        return [dict(r) for r in rows]

# --- Standard Assignments CRUD ---

@router.get("/assignments")
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

@router.post("/assignments", status_code=status.HTTP_201_CREATED)
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

@router.patch("/assignments/{assignment_id}")
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

@router.delete("/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_assignment(assignment_id: int):
    with get_db() as conn:
        conn.execute("DELETE FROM assignments WHERE id = ?", (assignment_id,))
        conn.commit()
