import sqlite3
from fastapi import APIRouter, HTTPException, status

from database import get_db
from schemas import StackCreate, StackTagAdd, MergeStacksRequest

router = APIRouter()

# --- Stacks Endpoints ---

@router.get("/stacks")
def get_stacks():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM stacks ORDER BY name COLLATE NOCASE ASC").fetchall()
        return [dict(r) for r in rows]

@router.post("/stacks", status_code=status.HTTP_201_CREATED)
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

@router.delete("/stacks/{stack_name}", status_code=status.HTTP_200_OK)
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

@router.get("/stacks/{stack_name}/tags")
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

@router.post("/stacks/{stack_name}/tags")
def add_stack_tag(stack_name: str, payload: StackTagAdd):
    clean = payload.tag_name.strip()
    if not clean:
        raise HTTPException(status_code=400, detail="Tag cannot be empty.")
    with get_db() as conn:
        conn.execute("INSERT OR IGNORE INTO stack_tags (stack_name, tag_name) VALUES (?, ?)", (stack_name, clean))
        conn.commit()
        return {"stack_name": stack_name, "tag_name": clean}

@router.delete("/stacks/{stack_name}/tags/{tag_name}")
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

@router.post("/stacks/merge", status_code=status.HTTP_200_OK)
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
